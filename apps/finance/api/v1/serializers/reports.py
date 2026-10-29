from rest_framework import serializers

from apps.finance.api.v1.serializers.common import MonthField
from apps.finance.api.v1.serializers.expenses import CompensationListSerializer


class RangeSerializer(serializers.Serializer):
    """Adds `from`, which cannot be declared as a class attribute."""

    to = serializers.DateField()
    bucket = serializers.CharField()

    def get_fields(self):
        fields = super().get_fields()
        return {"from": serializers.DateField(), **fields}


class FinanceTotalsSerializer(serializers.Serializer):
    billed = serializers.IntegerField()
    collected = serializers.IntegerField()
    new_debt = serializers.IntegerField()
    outstanding_debt = serializers.IntegerField()
    debtors_count = serializers.IntegerField()


class FinancePointSerializer(serializers.Serializer):
    start = serializers.DateField()
    billed = serializers.IntegerField()
    collected = serializers.IntegerField()


class DoctorCollectedSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField()
    doctor = serializers.CharField()
    collected = serializers.IntegerField()


class TreatmentTypeBilledSerializer(serializers.Serializer):
    treatment_type_id = serializers.IntegerField()
    treatment_type = serializers.CharField()
    billed = serializers.IntegerField()


class DebtorSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    patient = serializers.CharField()
    debt = serializers.IntegerField()
    last_payment_date = serializers.DateField(allow_null=True)
    doctor = serializers.CharField(allow_null=True)


class FinanceOverviewSerializer(RangeSerializer):
    totals = FinanceTotalsSerializer()
    previous_totals = FinanceTotalsSerializer(allow_null=True)
    series = FinancePointSerializer(many=True)
    doctors = DoctorCollectedSerializer(many=True)
    treatment_types = TreatmentTypeBilledSerializer(many=True)
    top_debtors = DebtorSerializer(many=True)


class PayrollRowSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField()
    doctor = serializers.CharField()
    compensation = CompensationListSerializer(allow_null=True)
    collected = serializers.IntegerField()
    billed = serializers.IntegerField()
    lab = serializers.IntegerField()
    base_amount = serializers.IntegerField()
    accrued = serializers.IntegerField()
    opening = serializers.IntegerField()
    paid = serializers.IntegerField()
    balance = serializers.IntegerField()


class PayrollTotalsSerializer(serializers.Serializer):
    accrued = serializers.IntegerField()
    paid = serializers.IntegerField()
    balance = serializers.IntegerField()


class PayrollSerializer(serializers.Serializer):
    month = MonthField()
    rows = PayrollRowSerializer(many=True)
    totals = PayrollTotalsSerializer()


class DoctorMonthSerializer(PayrollRowSerializer):
    """A doctor's own month, the same figures the owner sees in their payroll row."""

    month = MonthField()
