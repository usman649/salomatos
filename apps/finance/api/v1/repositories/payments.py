from apps.clinic.models import Treatment
from apps.core.exceptions import ObjectNotFoundException
from apps.finance.models import Payment


class PaymentRepository:
    def get_payments(self, clinic_id):
        return (
            Payment.objects.filter(clinic=clinic_id)
            .select_related("patient", "doctor", "created_by", "treatment__treatment_type")
            .order_by("-date", "-id")
        )

    def get_payment_for_update(self, payment_id, clinic_id):
        payment = (
            Payment.objects.select_for_update()
            .filter(id=payment_id, clinic=clinic_id)
            .first()
        )
        if not payment:
            raise ObjectNotFoundException(
                message="Payment not found", message_key="payment_not_found"
            )
        return payment

    def get_treatment_for_update(self, treatment_id, clinic_id):
        # Row lock: two cashiers taking money for the same treatment must not
        # both pass the "not more than owed" check.
        treatment = (
            Treatment.objects.select_for_update()
            .filter(id=treatment_id, clinic=clinic_id)
            .first()
        )
        if not treatment:
            raise ObjectNotFoundException(
                message="Treatment not found", message_key="treatment_not_found"
            )
        return treatment
