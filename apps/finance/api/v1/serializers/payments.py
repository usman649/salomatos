from rest_framework import serializers

from apps.authentication.models import User
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
        treatments = Treatment.objects.filter(clinic=self.context.get("clinic"))
        request = self.context.get("request")
        if request is not None and request.user.role == User.Roles.DOCTOR:
            treatments = treatments.filter(doctor=request.user)
        # A treatment the user may not take money for reads as "does not exist",
        # never as "forbidden", so its existence is not revealed.
        self.fields["treatment"].queryset = treatments

    def validate_note(self, value):
        return blank_to_none(value)

    def validate(self, attrs):
        if attrs["date"] < attrs["treatment"].start_date:
            raise serializers.ValidationError(
                {"date": "A payment cannot be dated before its treatment started."},
                code="before_treatment_start",
            )
        return attrs
