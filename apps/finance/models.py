from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.authentication.models import User
from apps.core.models import CreatedUpdatedAbstractModel

# Money is whole so'm, as everywhere else in the project. Sums of it and a
# year's expenses outgrow a 32-bit integer, so new money columns are 64-bit.


class VoidableQuerySet(models.QuerySet):
    def active(self):
        return self.filter(voided_at__isnull=True)


class VoidableModel(CreatedUpdatedAbstractModel):
    """
    Money records are never deleted: a mistaken one is voided with a reason,
    stays in the journal and drops out of every total.
    """

    voided_at = models.DateTimeField(blank=True, null=True)
    voided_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    void_reason = models.CharField(max_length=200, blank=True, null=True)

    objects = VoidableQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    @property
    def is_void(self):
        return self.voided_at is not None


class Payment(VoidableModel):
    """
    One payment a patient made for a treatment. Recording one raises
    `Treatment.total_paid` in the same transaction, so the existing screens
    keep showing the right balance. The clinic does not track how a patient
    paid (cash, card, ...), so a payment has no method.
    """

    clinic = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clinic_payments",
        limit_choices_to={"role": User.Roles.SUPERADMIN},
    )
    # SET_NULL, not PROTECT: the existing treatment delete must keep working,
    # and money that was received stays in the ledger either way. Patient and
    # doctor are kept on the row for the same reason.
    treatment = models.ForeignKey(
        "clinic.Treatment",
        on_delete=models.SET_NULL,
        related_name="payments",
        blank=True,
        null=True,
    )
    patient = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="patient_payments",
        limit_choices_to={"role": User.Roles.PATIENT},
        blank=True,
        null=True,
    )
    doctor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="doctor_payments",
        limit_choices_to={"role": User.Roles.DOCTOR},
        blank=True,
        null=True,
    )
    amount = models.PositiveBigIntegerField()
    date = models.DateField()
    note = models.CharField(max_length=500, blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )

    class Meta(VoidableModel.Meta):
        indexes = [models.Index(fields=["clinic", "date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="finance_payment_amount_positive"
            ),
        ]

    def __str__(self):
        return f"{self.amount} ({self.date})"


class ExpenseCategory(models.TextChoices):
    DOCTOR_SHARE = "doctor_share", _("Doctor share")
    STAFF_SALARY = "staff_salary", _("Staff salary")
    RENT = "rent", _("Rent")
    UTILITIES = "utilities", _("Utilities")
    COMMUNICATION = "communication", _("Communication and software")
    MATERIALS = "materials", _("Materials and medicines")
    LAB = "lab", _("Dental lab")
    EQUIPMENT = "equipment", _("Equipment")
    MARKETING = "marketing", _("Marketing")
    TAXES_FEES = "taxes_fees", _("Taxes and bank fees")
    OTHER = "other", _("Other")


# What people cost, what is owed every month regardless of patients, and what
# moves with the work: the three groups an owner reads costs in.
PAYROLL = "payroll"
FIXED = "fixed"
VARIABLE = "variable"

EXPENSE_CATEGORY_KIND = {
    ExpenseCategory.DOCTOR_SHARE: PAYROLL,
    ExpenseCategory.STAFF_SALARY: PAYROLL,
    ExpenseCategory.RENT: FIXED,
    ExpenseCategory.UTILITIES: FIXED,
    ExpenseCategory.COMMUNICATION: FIXED,
    ExpenseCategory.TAXES_FEES: FIXED,
    ExpenseCategory.MATERIALS: VARIABLE,
    ExpenseCategory.LAB: VARIABLE,
    ExpenseCategory.EQUIPMENT: VARIABLE,
    ExpenseCategory.MARKETING: VARIABLE,
    ExpenseCategory.OTHER: VARIABLE,
}


class ExpenseMethod(models.TextChoices):
    CASH = "cash", _("Cash")
    CARD = "card", _("Card")
    TRANSFER = "transfer", _("Bank transfer")


class RecurringExpense(CreatedUpdatedAbstractModel):
    """
    A bill the clinic owes every month. Only a reminder: each month is still
    paid by hand, at its real amount. Switched off, never deleted.
    """

    clinic = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clinic_recurring_expenses",
        limit_choices_to={"role": User.Roles.SUPERADMIN},
    )
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=30, choices=ExpenseCategory.choices)
    amount = models.PositiveBigIntegerField()
    method = models.CharField(max_length=20, choices=ExpenseMethod.choices)
    payee = models.CharField(max_length=120, blank=True, null=True)
    # 1-28, so every month has the day.
    day_of_month = models.PositiveSmallIntegerField()
    is_active = models.BooleanField(default=True)
    # The first month the bill is due in.
    since = models.DateField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )

    class Meta(CreatedUpdatedAbstractModel.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(day_of_month__gte=1, day_of_month__lte=28),
                name="finance_recurring_day_of_month_range",
            ),
            models.CheckConstraint(
                condition=~models.Q(category=ExpenseCategory.DOCTOR_SHARE),
                name="finance_recurring_not_doctor_share",
            ),
        ]

    def __str__(self):
        return self.name


class Expense(VoidableModel):
    """One payment the clinic made, entered by hand. No patient data belongs here."""

    clinic = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clinic_expenses",
        limit_choices_to={"role": User.Roles.SUPERADMIN},
    )
    date = models.DateField()
    category = models.CharField(max_length=30, choices=ExpenseCategory.choices)
    amount = models.PositiveBigIntegerField()
    method = models.CharField(max_length=20, choices=ExpenseMethod.choices)
    payee = models.CharField(max_length=120, blank=True, null=True)
    note = models.CharField(max_length=500, blank=True, null=True)
    doctor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="doctor_expenses",
        limit_choices_to={"role": User.Roles.DOCTOR},
        blank=True,
        null=True,
    )
    # Set when the expense settles one month of a recurring bill.
    recurring = models.ForeignKey(
        RecurringExpense,
        on_delete=models.PROTECT,
        related_name="payments",
        blank=True,
        null=True,
    )
    due_month = models.DateField(blank=True, null=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )

    class Meta(VoidableModel.Meta):
        indexes = [models.Index(fields=["clinic", "date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="finance_expense_amount_positive"
            ),
            # One live payment per bill per month; a voided one frees the month again.
            models.UniqueConstraint(
                fields=["recurring", "due_month"],
                condition=models.Q(voided_at__isnull=True),
                name="finance_expense_one_payment_per_due_month",
            ),
        ]

    def __str__(self):
        return f"{self.category} {self.amount} ({self.date})"


class RecurringExpenseSkip(CreatedUpdatedAbstractModel):
    """'Not this month' for a recurring bill (a holiday, a waived bill). Nothing is posted."""

    recurring = models.ForeignKey(
        RecurringExpense, on_delete=models.CASCADE, related_name="skips"
    )
    month = models.DateField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )

    class Meta(CreatedUpdatedAbstractModel.Meta):
        constraints = [
            models.UniqueConstraint(
                fields=["recurring", "month"], name="finance_recurring_skip_once_per_month"
            ),
        ]


class DoctorCompensation(CreatedUpdatedAbstractModel):
    """
    A doctor's pay terms from one month on. A change is a new row, never an
    edit, so months already settled keep the terms they were settled under.
    """

    class Base(models.TextChoices):
        COLLECTED = "collected", _("Collected")
        BILLED = "billed", _("Billed")

    clinic = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="clinic_doctor_compensations",
        limit_choices_to={"role": User.Roles.SUPERADMIN},
    )
    doctor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="compensations",
        limit_choices_to={"role": User.Roles.DOCTOR},
    )
    percent = models.DecimalField(max_digits=5, decimal_places=2)
    fixed = models.PositiveBigIntegerField(default=0)
    base = models.CharField(max_length=20, choices=Base.choices, default=Base.COLLECTED)
    deduct_lab = models.BooleanField(default=True)
    # The first day of the month the terms start in.
    effective_from = models.DateField()
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )

    class Meta(CreatedUpdatedAbstractModel.Meta):
        ordering = ["-effective_from", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(percent__gte=0, percent__lte=100),
                name="finance_compensation_percent_range",
            ),
        ]
