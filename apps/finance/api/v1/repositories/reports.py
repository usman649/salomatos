from collections import defaultdict

from django.db.models import BigIntegerField, ExpressionWrapper, F, Max, Min, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, TruncMonth

from apps.authentication.models import User
from apps.clinic.models import Treatment
from apps.finance.models import DoctorCompensation, Expense, ExpenseCategory, Payment


def _sum_by(queryset, key, amount):
    return {
        row["key"]: row["amount"] or 0
        for row in queryset.values(key=F(key)).annotate(amount=Sum(amount)).order_by()
    }


def _sum_by_doctor_month(queryset, date_field, amount):
    """`{doctor_id: {month_start: amount}}`."""
    result = defaultdict(dict)
    rows = (
        queryset.annotate(month=TruncMonth(date_field))
        .values("doctor_id", "month")
        .annotate(amount=Sum(amount))
        .order_by()
    )
    for row in rows:
        result[row["doctor_id"]][row["month"]] = row["amount"] or 0
    return result


class FinanceReportRepository:
    """
    Money read straight from the database, grouped and summed there. Billed
    work is a treatment's price on its `start_date`, the only date a treatment
    has; collected money is the payment ledger by payment date.
    """

    def _payments(self, clinic_id, start, end, doctor_id=None):
        queryset = Payment.objects.active().filter(clinic=clinic_id, date__range=(start, end))
        if doctor_id is not None:
            queryset = queryset.filter(doctor=doctor_id)
        return queryset

    def _treatments(self, clinic_id, start, end, doctor_id=None):
        queryset = Treatment.objects.filter(clinic=clinic_id, start_date__range=(start, end))
        if doctor_id is not None:
            queryset = queryset.filter(doctor=doctor_id)
        return queryset

    def collected_total(self, clinic_id, start, end, doctor_id=None):
        result = self._payments(clinic_id, start, end, doctor_id).aggregate(total=Sum("amount"))
        return result["total"] or 0

    def billed_total(self, clinic_id, start, end, doctor_id=None):
        result = self._treatments(clinic_id, start, end, doctor_id).aggregate(
            total=Sum("total_treatment_cost")
        )
        return result["total"] or 0

    def collected_by_date(self, clinic_id, start, end):
        return _sum_by(self._payments(clinic_id, start, end), "date", "amount")

    def billed_by_date(self, clinic_id, start, end):
        return _sum_by(self._treatments(clinic_id, start, end), "start_date", "total_treatment_cost")

    def collected_by_doctor(self, clinic_id, start, end):
        return _sum_by(
            self._payments(clinic_id, start, end).filter(doctor__isnull=False),
            "doctor_id",
            "amount",
        )

    def billed_by_treatment_type(self, clinic_id, start, end):
        rows = (
            self._treatments(clinic_id, start, end)
            .filter(treatment_type__isnull=False)
            .values("treatment_type_id", "treatment_type__name")
            .annotate(billed=Sum("total_treatment_cost"))
            .order_by("-billed", "treatment_type__name")
        )
        return [
            {
                "treatment_type_id": row["treatment_type_id"],
                "treatment_type": row["treatment_type__name"],
                "billed": row["billed"] or 0,
            }
            for row in rows
        ]

    def patient_debts(self, clinic_id, as_of, started_from=None):
        """
        What was still owed at the end of `as_of`, as `[{"patient_id", "debt"}]`
        with positive debts only. A patient's treatments are netted, so an
        overpaid one offsets another's debt; a treatment whose patient was
        deleted stands on its own under `patient_id=None`. `total_paid` is
        today's figure, so payments made after `as_of` are added back; amounts
        paid before the ledger existed have no date and count as paid from the start.
        """
        paid_later = (
            Payment.objects.active()
            .filter(treatment=OuterRef("pk"), date__gt=as_of)
            .values("treatment")
            .annotate(total=Sum("amount"))
            .values("total")
        )
        queryset = Treatment.objects.filter(clinic=clinic_id, start_date__lte=as_of)
        if started_from is not None:
            queryset = queryset.filter(start_date__gte=started_from)
        queryset = queryset.annotate(
            debt=ExpressionWrapper(
                F("total_treatment_cost")
                - F("total_paid")
                + Coalesce(Subquery(paid_later), Value(0), output_field=BigIntegerField()),
                output_field=BigIntegerField(),
            )
        )
        by_patient = (
            queryset.filter(patient__isnull=False)
            .values("patient_id")
            .annotate(total=Sum("debt"))
            .filter(total__gt=0)
            .order_by()
        )
        orphans = queryset.filter(patient__isnull=True, debt__gt=0).values_list("debt", flat=True)
        return [
            *({"patient_id": row["patient_id"], "debt": row["total"]} for row in by_patient),
            *({"patient_id": None, "debt": debt} for debt in orphans),
        ]

    def last_payment_dates(self, clinic_id, patient_ids, as_of):
        rows = (
            Payment.objects.active()
            .filter(clinic=clinic_id, patient_id__in=patient_ids, date__lte=as_of)
            .values("patient_id")
            .annotate(last=Max("date"))
            .order_by()
        )
        return {row["patient_id"]: row["last"] for row in rows}

    def get_patients(self, clinic_id, patient_ids):
        return {
            patient.id: patient
            for patient in User.objects.filter(
                id__in=patient_ids, clinic=clinic_id, role=User.Roles.PATIENT
            ).select_related("doctor")
        }

    def get_doctors(self, clinic_id, doctor_id=None):
        queryset = User.objects.filter(clinic=clinic_id, role=User.Roles.DOCTOR)
        if doctor_id is not None:
            queryset = queryset.filter(id=doctor_id)
        return list(queryset.order_by("full_name", "id"))

    # Payroll: everything grouped by doctor and month, so a year of history is a
    # handful of queries rather than one per month.

    def collected_by_doctor_month(self, clinic_id, doctor_ids, start, end):
        return _sum_by_doctor_month(
            Payment.objects.active().filter(
                clinic=clinic_id, doctor_id__in=doctor_ids, date__range=(start, end)
            ),
            "date",
            "amount",
        )

    def billed_by_doctor_month(self, clinic_id, doctor_ids, start, end):
        return _sum_by_doctor_month(
            Treatment.objects.filter(
                clinic=clinic_id, doctor_id__in=doctor_ids, start_date__range=(start, end)
            ),
            "start_date",
            "total_treatment_cost",
        )

    def expenses_by_doctor_month(self, clinic_id, doctor_ids, category, start, end):
        return _sum_by_doctor_month(
            Expense.objects.active().filter(
                clinic=clinic_id,
                category=category,
                doctor_id__in=doctor_ids,
                date__range=(start, end),
            ),
            "date",
            "amount",
        )

    def get_compensations(self, clinic_id, doctor_ids):
        """`{doctor_id: [terms, oldest first]}`."""
        result = defaultdict(list)
        queryset = (
            DoctorCompensation.objects.filter(clinic=clinic_id, doctor_id__in=doctor_ids)
            .select_related("created_by")
            .order_by("effective_from", "id")
        )
        for terms in queryset:
            result[terms.doctor_id].append(terms)
        return result

    def first_payout_dates(self, clinic_id, doctor_ids):
        """The earliest doctor's-share payout per doctor: payroll history starts there at the latest."""
        rows = (
            Expense.objects.active()
            .filter(
                clinic=clinic_id,
                category=ExpenseCategory.DOCTOR_SHARE,
                doctor_id__in=doctor_ids,
            )
            .values("doctor_id")
            .annotate(first=Min("date"))
            .order_by()
        )
        return {row["doctor_id"]: row["first"] for row in rows}
