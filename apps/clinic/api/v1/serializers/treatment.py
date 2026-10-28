from rest_framework import serializers
from apps.clinic.models import Treatment, TreatmentType
from django.db import transaction
from django.utils import timezone

class TreatmentListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    patient = serializers.CharField()
    patient_id = serializers.IntegerField()
    doctor = serializers.CharField()
    treatment_type = serializers.CharField()
    total_treatment_cost = serializers.IntegerField()
    total_paid = serializers.IntegerField()
    remaining = serializers.SerializerMethodField()
    visit_number = serializers.IntegerField()
    tooth_number = serializers.IntegerField()
    start_date = serializers.DateField()
    completed_date = serializers.DateField()
    notes = serializers.CharField()
    status = serializers.CharField()

    def get_remaining(self, obj):
        return obj.total_treatment_cost - obj.total_paid

class TreatmentBulkCreateListSerializer(serializers.ListSerializer):
    @transaction.atomic
    def create(self, validated_data):
        treatments = [Treatment(**item) for item in validated_data]
        return Treatment.objects.bulk_create(treatments)

class TreatmentCreateUpdateSerializer(serializers.ModelSerializer):
    # Money comes in only through finance payments, which keep `total_paid` in
    # step: a new treatment starts unpaid and an edit never overwrites the sum.
    total_paid = serializers.IntegerField(min_value=0, default=0)

    class Meta:
        model = Treatment
        list_serializer_class = TreatmentBulkCreateListSerializer
        fields = [
            'patient',
            'doctor',
            'treatment_type',
            'total_treatment_cost',
            'total_paid',
            'visit_number',
            'tooth_number',
            'start_date',
            'completed_date',
            'notes',
            'status',
        ]

    def validate_total_paid(self, value):
        if self.instance is None and value:
            raise serializers.ValidationError(
                'Record the money as a payment.', code='use_payments'
            )
        return value

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop('total_paid', None)
        status = attrs.get('status', getattr(self.instance, 'status', None))
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        completed_date = attrs.get('completed_date', getattr(self.instance, 'completed_date', None))
        was_completed = getattr(self.instance, 'status', None) == Treatment.Status.COMPLETED
        if status != Treatment.Status.COMPLETED:
            # Reopened or never finished: there is no completion date to keep.
            attrs['completed_date'] = None
            return attrs
        # A treatment booked ahead and closed early completes on its start date;
        # a date after both today and the start is a typo.
        latest = max(timezone.localdate(), start_date) if start_date else timezone.localdate()
        if completed_date is None and not was_completed:
            # Finished just now by a client that sent no date.
            completed_date = attrs['completed_date'] = latest
        if completed_date is not None:
            if completed_date > latest:
                raise serializers.ValidationError(
                    {'completed_date': 'Completion date cannot be in the future.'}
                )
            if start_date and completed_date < start_date:
                raise serializers.ValidationError(
                    {'completed_date': 'Completion date cannot be before the start date.'}
                )
        return attrs

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        # Only the fields sent are written, so a payment recorded meanwhile
        # keeps the `total_paid` it set.
        instance.save(update_fields=[*validated_data, 'updated_at'])
        return instance

class TreatmentTypeListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    price = serializers.IntegerField()
    doctor_type = serializers.CharField()

class TreatmentTypeCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TreatmentType
        fields = [
            'name',
            'price',
            'doctor_type'
        ]
