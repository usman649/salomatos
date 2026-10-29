from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status

from apps.core.exceptions import ValidationError
from apps.core.permissions import get_clinic
from apps.core.reporting import clinic_today, parse_range, require_month
from apps.core.services import BaseService
from apps.finance.api.v1.repositories.expenses import ExpenseRepository
from apps.finance.api.v1.serializers.common import VoidSerializer
from apps.finance.api.v1.serializers.expenses import (
    CompensationCreateSerializer,
    CompensationListSerializer,
    DueMonthSerializer,
    ExpenseCreateUpdateSerializer,
    ExpenseListSerializer,
    ExpenseSummarySerializer,
    PayDueSerializer,
    RecurringExpenseCreateUpdateSerializer,
    RecurringExpenseListSerializer,
    SkipDueSerializer,
)
from apps.finance.models import (
    EXPENSE_CATEGORY_KIND,
    FIXED,
    PAYROLL,
    VARIABLE,
    Expense,
    ExpenseCategory,
    RecurringExpenseSkip,
)


def _already_voided():
    return ValidationError(
        message="The expense is already voided.", message_key="already_voided"
    )


def _already_paid():
    return ValidationError(
        message="This month of the bill is already paid.", message_key="already_paid"
    )


def _check_bill_month(recurring, month):
    # Months before the bill was set up are not in its due list, so a payment
    # or skip there could never be seen again.
    if month < recurring.since:
        raise ValidationError(
            message="The bill did not exist in that month yet.",
            message_key="before_bill_start",
            errors={"month": "before_start"},
        )


def _expense_totals(expenses):
    totals = {"total": 0, "count": 0, PAYROLL: 0, FIXED: 0, VARIABLE: 0}
    for category, amount, count in expenses:
        totals["total"] += amount
        totals["count"] += count
        totals[EXPENSE_CATEGORY_KIND[category]] += amount
    return totals


class ExpenseService(BaseService):
    def __init__(self, request):
        super().__init__(request)
        self.db = ExpenseRepository()
        self.clinic = get_clinic(request.user)

    def _context(self):
        return {"request": self.request, "clinic": self.clinic}

    # Journal

    def get_expenses(self, *args, **kwargs):
        report_range = parse_range(self.request.query_params)
        expenses = self.db.get_expenses(clinic_id=self.clinic).filter(
            date__range=(report_range.start, report_range.end)
        )
        category = self.request.query_params.get("category")
        if category:
            if category not in ExpenseCategory.values:
                raise ValidationError(
                    message="Unknown expense category.",
                    message_key="invalid_params",
                    errors={"category": "invalid_choice"},
                )
            expenses = expenses.filter(category=category)

        return self.get_paginated_response(
            expenses,
            ExpenseListSerializer,
            context={"request": self.request},
        )

    def create_expense(self, *args, **kwargs):
        serializer_class = ExpenseCreateUpdateSerializer(
            data=self.request.data, context=self._context()
        )
        serializer_class.is_valid(raise_exception=True)
        expense = serializer_class.save(clinic=self.clinic, created_by=self.request.user)
        return self.get_response_object(
            expense,
            ExpenseListSerializer,
            context={"request": self.request},
            status_code=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def update_expense(self, *args, **kwargs):
        expense = self.db.get_expense_for_update(expense_id=kwargs.get("pk"), clinic_id=self.clinic)
        if expense.is_void:
            raise _already_voided()
        serializer_class = ExpenseCreateUpdateSerializer(
            instance=expense,
            data=self.request.data,
            partial=True,
            context=self._context(),
        )
        serializer_class.is_valid(raise_exception=True)
        serializer_class.save()
        return self.get_response_object(
            expense,
            ExpenseListSerializer,
            context={"request": self.request},
        )

    @transaction.atomic
    def void_expense(self, *args, **kwargs):
        serializer_class = VoidSerializer(data=self.request.data)
        serializer_class.is_valid(raise_exception=True)
        expense = self.db.get_expense_for_update(expense_id=kwargs.get("pk"), clinic_id=self.clinic)
        if expense.is_void:
            raise _already_voided()
        expense.voided_at = timezone.now()
        expense.voided_by = self.request.user
        expense.void_reason = serializer_class.validated_data["reason"]
        expense.save(update_fields=["voided_at", "voided_by", "void_reason", "updated_at"])
        return self.get_response_object(
            expense,
            ExpenseListSerializer,
            context={"request": self.request},
        )

    def get_summary(self, *args, **kwargs):
        report_range = parse_range(self.request.query_params)
        previous_range = report_range.previous()

        current = self.db.sum_by_category(self.clinic, report_range.start, report_range.end)
        previous = self.db.sum_by_category(self.clinic, previous_range.start, previous_range.end)
        amounts = {category: amount for category, amount, _count in current}
        daily = {
            day: {"amount": amount}
            for day, amount in self.db.sum_by_date(
                self.clinic, report_range.start, report_range.end
            ).items()
        }

        summary = {
            "from": report_range.start,
            "to": report_range.end,
            "bucket": report_range.bucket,
            "totals": _expense_totals(current),
            "previous_totals": _expense_totals(previous) if previous else None,
            "by_category": [
                {"category": category, "amount": amounts[category]}
                for category in ExpenseCategory.values
                if amounts.get(category)
            ],
            "series": report_range.series(daily, ["amount"]),
        }
        return self.get_response_object(summary, ExpenseSummarySerializer)

    # Recurring bills

    def get_recurring_expenses(self, *args, **kwargs):
        return self.get_response(
            self.db.get_recurring_expenses(clinic_id=self.clinic),
            RecurringExpenseListSerializer,
            many=True,
        )

    def create_recurring_expense(self, *args, **kwargs):
        serializer_class = RecurringExpenseCreateUpdateSerializer(
            data=self.request.data, context=self._context()
        )
        serializer_class.is_valid(raise_exception=True)
        recurring = serializer_class.save(
            clinic=self.clinic,
            created_by=self.request.user,
            since=clinic_today().replace(day=1),
        )
        return self.get_response_object(
            recurring,
            RecurringExpenseListSerializer,
            status_code=status.HTTP_201_CREATED,
        )

    def update_recurring_expense(self, *args, **kwargs):
        recurring = self.db.get_recurring_expense(
            recurring_id=kwargs.get("pk"), clinic_id=self.clinic
        )
        serializer_class = RecurringExpenseCreateUpdateSerializer(
            instance=recurring,
            data=self.request.data,
            partial=True,
            context=self._context(),
        )
        serializer_class.is_valid(raise_exception=True)
        serializer_class.save()
        return self.get_response_object(recurring, RecurringExpenseListSerializer)

    def get_due_month(self, *args, **kwargs):
        month = require_month(self.request.query_params)
        today = clinic_today()
        templates = [
            template
            for template in self.db.get_recurring_expenses(clinic_id=self.clinic)
            if template.since <= month
        ]
        ids = [template.id for template in templates]
        payments = self.db.get_due_payments(ids, month)
        skipped = self.db.get_skipped_ids(ids, month)

        items = []
        for template in templates:
            payment = payments.get(template.id)
            due_date = month.replace(day=template.day_of_month)
            if payment is not None:
                due_status = "paid"
            elif template.id in skipped:
                due_status = "skipped"
            elif due_date < today:
                due_status = "overdue"
            else:
                due_status = "due"
            # A paused bill stays in the months it was settled in, and nowhere else.
            if not template.is_active and due_status != "paid":
                continue
            items.append(
                {
                    "recurring_id": template.id,
                    "name": template.name,
                    "category": template.category,
                    "amount": template.amount,
                    "payee": template.payee,
                    "due_date": due_date,
                    "status": due_status,
                    "expense_id": payment.id if payment else None,
                    "paid_amount": payment.amount if payment else None,
                    "paid_date": payment.date if payment else None,
                }
            )
        items.sort(key=lambda item: (item["due_date"], item["recurring_id"]))

        due_month = {
            "month": month,
            "totals": {
                "expected": sum(item["amount"] for item in items if item["status"] != "skipped"),
                "paid": sum(item["paid_amount"] or 0 for item in items),
                "remaining": sum(
                    item["amount"] for item in items if item["status"] in ("due", "overdue")
                ),
            },
            "items": items,
        }
        return self.get_response_object(due_month, DueMonthSerializer)

    @transaction.atomic
    def pay_due(self, *args, **kwargs):
        recurring = self.db.get_recurring_expense(
            recurring_id=kwargs.get("pk"), clinic_id=self.clinic, for_update=True
        )
        serializer_class = PayDueSerializer(data=self.request.data)
        serializer_class.is_valid(raise_exception=True)
        data = serializer_class.validated_data
        month = data["month"]
        _check_bill_month(recurring, month)

        if self.db.get_active_due_payment(recurring.id, month) is not None:
            raise _already_paid()
        try:
            # The savepoint keeps the outer transaction usable if the unique
            # constraint catches a concurrent payment of the same month.
            with transaction.atomic():
                expense = Expense.objects.create(
                    clinic=self.clinic,
                    date=data["date"],
                    category=recurring.category,
                    amount=data["amount"],
                    payee=recurring.payee,
                    note=data.get("note"),
                    recurring=recurring,
                    due_month=month,
                    created_by=self.request.user,
                )
        except IntegrityError:
            raise _already_paid() from None
        self.db.delete_skip(recurring.id, month)

        return self.get_response_object(
            expense,
            ExpenseListSerializer,
            context={"request": self.request},
            status_code=status.HTTP_201_CREATED,
        )

    @transaction.atomic
    def skip_due(self, *args, **kwargs):
        recurring = self.db.get_recurring_expense(
            recurring_id=kwargs.get("pk"), clinic_id=self.clinic, for_update=True
        )
        serializer_class = SkipDueSerializer(data=self.request.data)
        serializer_class.is_valid(raise_exception=True)
        month = serializer_class.validated_data["month"]
        _check_bill_month(recurring, month)

        if self.db.get_active_due_payment(recurring.id, month) is not None:
            raise _already_paid()
        RecurringExpenseSkip.objects.get_or_create(
            recurring=recurring,
            month=month,
            defaults={"created_by": self.request.user},
        )
        return self.get_response_object(status_code=status.HTTP_204_NO_CONTENT)

    # Doctor pay terms

    def get_compensations(self, *args, **kwargs):
        doctor = self.db.get_doctor(doctor_id=kwargs.get("doctor_id"), clinic_id=self.clinic)
        return self.get_response(
            self.db.get_compensations(doctor_id=doctor.id, clinic_id=self.clinic),
            CompensationListSerializer,
            many=True,
        )

    def create_compensation(self, *args, **kwargs):
        doctor = self.db.get_doctor(doctor_id=kwargs.get("doctor_id"), clinic_id=self.clinic)
        serializer_class = CompensationCreateSerializer(
            data=self.request.data, context=self._context()
        )
        serializer_class.is_valid(raise_exception=True)
        compensation = serializer_class.save(
            clinic=self.clinic, doctor=doctor, created_by=self.request.user
        )
        return self.get_response_object(
            compensation,
            CompensationListSerializer,
            status_code=status.HTTP_201_CREATED,
        )

