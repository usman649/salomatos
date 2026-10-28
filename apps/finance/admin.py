from django.contrib import admin

from apps.finance.models import (
    DoctorCompensation,
    Expense,
    Payment,
    RecurringExpense,
    RecurringExpenseSkip,
)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "date", "amount", "doctor", "voided_at"]
    list_display_links = ["id", "date"]
    raw_id_fields = ["clinic", "treatment", "patient", "doctor", "created_by", "voided_by"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ["id", "date", "category", "amount", "method", "voided_at"]
    list_display_links = ["id", "date"]
    list_filter = ["category", "method"]
    raw_id_fields = ["clinic", "doctor", "recurring", "created_by", "voided_by"]


@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "category", "amount", "day_of_month", "is_active"]
    list_display_links = ["id", "name"]
    raw_id_fields = ["clinic", "created_by"]


@admin.register(RecurringExpenseSkip)
class RecurringExpenseSkipAdmin(admin.ModelAdmin):
    list_display = ["id", "recurring", "month"]
    raw_id_fields = ["recurring", "created_by"]


@admin.register(DoctorCompensation)
class DoctorCompensationAdmin(admin.ModelAdmin):
    list_display = ["id", "doctor", "percent", "fixed", "base", "effective_from"]
    list_display_links = ["id", "doctor"]
    raw_id_fields = ["clinic", "doctor", "created_by"]
