from django.db.models import Count, Sum

from apps.authentication.models import User
from apps.core.exceptions import ObjectNotFoundException
from apps.finance.models import (
    DoctorCompensation,
    Expense,
    RecurringExpense,
    RecurringExpenseSkip,
)


class ExpenseRepository:
    def get_expenses(self, clinic_id):
        return (
            Expense.objects.filter(clinic=clinic_id)
            .select_related("doctor", "created_by")
            .order_by("-date", "-id")
        )

    def get_expense_for_update(self, expense_id, clinic_id):
        expense = (
            Expense.objects.select_for_update()
            .filter(id=expense_id, clinic=clinic_id)
            .first()
        )
        if not expense:
            raise ObjectNotFoundException(
                message="Expense not found", message_key="expense_not_found"
            )
        return expense

    def get_active_expenses_between(self, clinic_id, start, end):
        return Expense.objects.active().filter(clinic=clinic_id, date__range=(start, end))

    def sum_by_category(self, clinic_id, start, end):
        """`[(category, amount, count)]` of live expenses in the range."""
        return list(
            self.get_active_expenses_between(clinic_id, start, end)
            .values_list("category")
            .annotate(amount=Sum("amount"), count=Count("id"))
            .order_by()
        )

    def sum_by_date(self, clinic_id, start, end):
        return dict(
            self.get_active_expenses_between(clinic_id, start, end)
            .values_list("date")
            .annotate(amount=Sum("amount"))
            .order_by()
        )

    def get_recurring_expenses(self, clinic_id):
        return RecurringExpense.objects.filter(clinic=clinic_id).order_by("day_of_month", "id")

    def get_recurring_expense(self, recurring_id, clinic_id, for_update=False):
        queryset = RecurringExpense.objects.filter(id=recurring_id, clinic=clinic_id)
        if for_update:
            queryset = queryset.select_for_update()
        recurring = queryset.first()
        if not recurring:
            raise ObjectNotFoundException(
                message="Recurring expense not found",
                message_key="recurring_expense_not_found",
            )
        return recurring

    def get_due_payments(self, recurring_ids, month):
        """The live payment of each bill for one month, keyed by bill."""
        payments = Expense.objects.active().filter(
            recurring_id__in=recurring_ids, due_month=month
        )
        return {payment.recurring_id: payment for payment in payments}

    def get_active_due_payment(self, recurring_id, month):
        return (
            Expense.objects.active()
            .filter(recurring_id=recurring_id, due_month=month)
            .first()
        )

    def get_skipped_ids(self, recurring_ids, month):
        return set(
            RecurringExpenseSkip.objects.filter(
                recurring_id__in=recurring_ids, month=month
            ).values_list("recurring_id", flat=True)
        )

    def delete_skip(self, recurring_id, month):
        RecurringExpenseSkip.objects.filter(recurring_id=recurring_id, month=month).delete()

    def get_doctor(self, doctor_id, clinic_id):
        doctor = User.objects.filter(
            id=doctor_id, role=User.Roles.DOCTOR, clinic=clinic_id
        ).first()
        if not doctor:
            raise ObjectNotFoundException(
                message="Doctor not found", message_key="doctor_not_found"
            )
        return doctor

    def get_compensations(self, doctor_id, clinic_id):
        return (
            DoctorCompensation.objects.filter(doctor=doctor_id, clinic=clinic_id)
            .select_related("created_by")
            .order_by("-effective_from", "-id")
        )
