from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.core.exceptions import ValidationError
from apps.core.permissions import get_clinic
from apps.core.reporting import parse_date
from apps.core.services import BaseService
from apps.finance.api.v1.repositories.payments import PaymentRepository
from apps.finance.api.v1.serializers.common import VoidSerializer
from apps.finance.api.v1.serializers.payments import (
    PaymentCreateSerializer,
    PaymentListSerializer,
)
from apps.finance.models import Payment


class PaymentService(BaseService):
    def __init__(self, request):
        super().__init__(request)
        self.db = PaymentRepository()
        self.clinic = get_clinic(request.user)

    def get_payments(self, *args, **kwargs):
        payments = self.db.get_payments(clinic_id=self.clinic)
        params = self.request.query_params
        if params.get("from"):
            payments = payments.filter(date__gte=parse_date(params["from"], "from"))
        if params.get("to"):
            payments = payments.filter(date__lte=parse_date(params["to"], "to"))
        for param, field in (("patient_id", "patient_id"), ("treatment_id", "treatment_id")):
            value = params.get(param)
            if value:
                if not value.isdigit():
                    raise ValidationError(
                        message=f"`{param}` must be a number.",
                        message_key="invalid_params",
                        errors={param: "invalid"},
                    )
                payments = payments.filter(**{field: int(value)})
        method = params.get("method")
        if method:
            if method not in Payment.Method.values:
                raise ValidationError(
                    message="Unknown payment method.",
                    message_key="invalid_params",
                    errors={"method": "invalid_choice"},
                )
            payments = payments.filter(method=method)

        return self.get_paginated_response(
            payments,
            PaymentListSerializer,
            context={"request": self.request},
        )

    @transaction.atomic
    def create_payment(self, *args, **kwargs):
        serializer_class = PaymentCreateSerializer(
            data=self.request.data,
            context={"request": self.request, "clinic": self.clinic},
        )
        serializer_class.is_valid(raise_exception=True)

        treatment = self.db.get_treatment_for_update(
            treatment_id=serializer_class.validated_data["treatment"].id,
            clinic_id=self.clinic,
        )
        amount = serializer_class.validated_data["amount"]
        owed = treatment.total_treatment_cost - treatment.total_paid
        if amount > owed:
            raise ValidationError(
                message="The payment is more than the treatment still owes.",
                message_key="payment_exceeds_debt",
                errors={"amount": "exceeds_debt"},
            )

        payment = serializer_class.save(
            clinic=self.clinic,
            treatment=treatment,
            patient=treatment.patient,
            doctor=treatment.doctor,
            created_by=self.request.user,
        )
        treatment.total_paid += amount
        treatment.save(update_fields=["total_paid", "updated_at"])

        return self.get_response_object(
            payment,
            PaymentListSerializer,
            context={"request": self.request},
            status_code=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def void_payment(self, *args, **kwargs):
        serializer_class = VoidSerializer(data=self.request.data)
        serializer_class.is_valid(raise_exception=True)

        payment = self.db.get_payment_for_update(payment_id=kwargs.get("pk"), clinic_id=self.clinic)
        if payment.is_void:
            raise ValidationError(
                message="The payment is already voided.",
                message_key="already_voided",
            )

        if payment.treatment_id is not None:
            treatment = self.db.get_treatment_for_update(
                treatment_id=payment.treatment_id, clinic_id=self.clinic
            )
            if treatment.total_paid < payment.amount:
                # `total_paid` was lowered by hand after this payment: taking the
                # payment off as well would push it below zero.
                raise ValidationError(
                    message="The treatment's paid total no longer includes this payment.",
                    message_key="paid_total_mismatch",
                )
            treatment.total_paid -= payment.amount
            treatment.save(update_fields=["total_paid", "updated_at"])

        payment.voided_at = timezone.now()
        payment.voided_by = self.request.user
        payment.void_reason = serializer_class.validated_data["reason"]
        payment.save(update_fields=["voided_at", "voided_by", "void_reason", "updated_at"])

        return self.get_response_object(
            payment,
            PaymentListSerializer,
            context={"request": self.request},
        )
