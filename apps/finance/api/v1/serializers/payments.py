from rest_framework import serializers

from apps.clinic.models import Treatment
from apps.finance.api.v1.serializers.common import (
    NOTE_MAX,
    AmountField,
    blank_to_none,
    validate_not_future,
)
from apps.finance.models import Payment


class PaymentListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    date = serializers.DateField()
    treatment_id = serializers.IntegerField()
    treatment_type = serializers.CharField(source="treatment.treatment_type.name", default=None)
    patient_id = serializers.IntegerField()
    patient = serializers.CharField(source="patient.full_name", default=None)
    doctor_id = serializers.IntegerField()
    doctor = serializers.CharField(source="doctor.full_name", default=None)
    amount = serializers.IntegerField()
    method = serializers.CharField()
    note = serializers.CharField()
    is_void = serializers.BooleanField()
    void_reason = serializers.CharField()
    created_by = serializers.CharField(source="created_by.full_name", default=None)


class PaymentCreateSerializer(serializers.ModelSerializer):
    treatment = serializers.PrimaryKeyRelatedField(queryset=Treatment.objects.none())
    amount = AmountField()
    date = serializers.DateField(validators=[validate_not_future])
    note = serializers.CharField(
        max_length=NOTE_MAX, required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = Payment
        fields = ["treatment", "amount", "method", "date", "note"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clinic = self.context.get("clinic")
        # Another clinic's treatment reads as "does not exist", never as "forbidden".
        self.fields["treatment"].queryset = Treatment.objects.filter(clinic=clinic)

    def validate_note(self, value):
        return blank_to_none(value)
