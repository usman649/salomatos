from rest_framework import serializers
from apps.calendars.models import Appointment
from apps.authentication.models import User

class AppointmentListSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    patient_id = serializers.IntegerField(read_only=True)
    patient = serializers.CharField(read_only=True)
    phone_number = serializers.CharField(source='patient.phone_number', read_only=True)
    doctor_id = serializers.IntegerField(read_only=True)
    doctor = serializers.CharField(read_only=True)
    date = serializers.DateField(read_only=True)
    time = serializers.TimeField(read_only=True)
    notes = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)

    treatment_type = serializers.SerializerMethodField()
    tooth_number = serializers.SerializerMethodField()

    def get_treatment_type(self, obj):
        if obj.patient:
            treatment = obj.patient.patient_treatments.first()
            if treatment and treatment.treatment_type:
                return treatment.treatment_type.name
        return None

    def get_tooth_number(self, obj):
        if obj.patient:
            treatment = obj.patient.patient_treatments.first()
            if treatment and treatment.tooth_number:
                return treatment.tooth_number
        return None

class AppointmentCreateUpdateSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True, required=False,allow_null=True)
    phone_number = serializers.CharField(write_only=True, required=False,allow_null=True)

    class Meta:
        model = Appointment
        fields = [
            'id',
            'full_name',
            'phone_number',
            'patient',
            'doctor',
            'date',
            'time',
            'notes',
            'status',
        ]
        extra_kwargs = {
            'patient': {'required': False, 'allow_null': True}
        }

    def create(self, validated_data):
        full_name = validated_data.pop('full_name', None)
        phone_number = validated_data.pop('phone_number', None)

        if full_name and phone_number:
            patient, _ = User.objects.get_or_create(
                phone_number=phone_number,
                defaults={
                    'full_name': full_name,
                    'role': User.Roles.PATIENT
                }
            )
            validated_data['patient'] = patient

        return super().create(validated_data)