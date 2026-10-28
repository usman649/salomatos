from decimal import ROUND_HALF_UP, Decimal

from apps.core.permissions import get_clinic
from apps.core.exceptions import ValidationError
from apps.core.reporting import (
    clinic_today,
    month_end,
    parse_range,
    require_month,
    shift_month,
)
from apps.core.services import BaseService
from apps.finance.api.v1.repositories.reports import FinanceReportRepository
from apps.finance.api.v1.serializers.reports import (
    DoctorMonthSerializer,
    FinanceOverviewSerializer,
    PayrollSerializer,
)
from apps.finance.models import DoctorCompensation, ExpenseCategory, Payment

TOP_DEBTORS = 10

# Payroll looks at most a year ahead; further out there is nothing to plan.
PAYROLL_MONTHS_AHEAD = 12

# Nobody hands out the last 437 so'm of a percent.
ACCRUAL_STEP = Decimal(1000)


def accrue(terms, collected, billed, lab):
    """A month's pay under one set of terms: `(base_amount, accrued)`."""
    if terms is None:
        return 0, 0
    gross = collected if terms.base == DoctorCompensation.Base.COLLECTED else billed
    base_amount = max(0, gross - (lab if terms.deduct_lab else 0))
    share = (Decimal(base_amount) * terms.percent / 100 / ACCRUAL_STEP).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    ) * ACCRUAL_STEP
    return base_amount, int(share) + terms.fixed


def terms_for(history, month):
    """The terms in force in `month`: the latest entry starting on or before it."""
    current = None
    for terms in history:
        if terms.effective_from <= month:
            current = terms
    return current


class FinanceReportService(BaseService):
    def __init__(self, request):
        super().__init__(request)
        self.db = FinanceReportRepository()
        self.clinic = get_clinic(request.user)

    # Overview

    def _totals(self, report_range):
        debts = self.db.patient_debts(self.clinic, as_of=report_range.end)
        new_debts = self.db.patient_debts(
            self.clinic, as_of=report_range.end, started_from=report_range.start
        )
        return {
            "billed": self.db.billed_total(self.clinic, report_range.start, report_range.end),
            "collected": self.db.collected_total(self.clinic, report_range.start, report_range.end),
            "new_debt": sum(row["debt"] for row in new_debts),
            "outstanding_debt": sum(row["debt"] for row in debts),
            "debtors_count": len({row["patient_id"] for row in debts if row["patient_id"]}),
        }, debts

    def _top_debtors(self, debts, as_of):
        by_patient = [(row["patient_id"], row["debt"]) for row in debts if row["patient_id"] is not None]
        top = sorted(by_patient, key=lambda item: (-item[1], item[0]))[:TOP_DEBTORS]
        ids = [patient_id for patient_id, _debt in top]
        patients = self.db.get_patients(self.clinic, ids)
        last_payments = self.db.last_payment_dates(self.clinic, ids, as_of)
        return [
            {
                "patient_id": patient_id,
                "patient": patients[patient_id].full_name,
                "debt": debt,
                "last_payment_date": last_payments.get(patient_id),
                "doctor": (
                    patients[patient_id].doctor.full_name
                    if patients[patient_id].doctor
                    else None
                ),
            }
            for patient_id, debt in top
            if patient_id in patients
        ]

    def get_overview(self, *args, **kwargs):
        report_range = parse_range(self.request.query_params)
        start, end = report_range.start, report_range.end

        totals, debts = self._totals(report_range)
        previous_totals, _previous_debts = self._totals(report_range.previous())

        collected = self.db.collected_by_date(self.clinic, start, end)
        billed = self.db.billed_by_date(self.clinic, start, end)
        daily = {}
        for day, amount in billed.items():
            daily.setdefault(day, {})["billed"] = amount
        for day, amount in collected.items():
            daily.setdefault(day, {})["collected"] = amount

        by_method = self.db.collected_by_method(self.clinic, start, end)
        by_doctor = self.db.collected_by_doctor(self.clinic, start, end)
        doctors = self.db.get_doctors(self.clinic)

        overview = {
            "from": start,
            "to": end,
            "bucket": report_range.bucket,
            "totals": totals,
            "previous_totals": previous_totals,
            "series": report_range.series(daily, ["billed", "collected"]),
            "payment_methods": [
                {"method": method, "amount": by_method.get(method, 0)}
                for method in Payment.Method.values
            ],
            "doctors": sorted(
                (
                    {
                        "doctor_id": doctor.id,
                        "doctor": doctor.full_name,
                        "collected": by_doctor.get(doctor.id, 0),
                    }
                    for doctor in doctors
                ),
                key=lambda row: (-row["collected"], row["doctor"]),
            ),
            "treatment_types": self.db.billed_by_treatment_type(self.clinic, start, end),
            "top_debtors": self._top_debtors(debts, as_of=end),
        }
        return self.get_response_object(overview, FinanceOverviewSerializer)

    # Doctor pay

    def _payroll_month(self):
        month = require_month(self.request.query_params)
        if month > shift_month(clinic_today().replace(day=1), PAYROLL_MONTHS_AHEAD):
            raise ValidationError(
                message=f"Payroll covers at most {PAYROLL_MONTHS_AHEAD} months ahead.",
                message_key="invalid_month",
                errors={"month": "too_far"},
            )
        return month

    def _payroll_rows(self, month, doctor_id=None):
        doctors = self.db.get_doctors(self.clinic, doctor_id=doctor_id)
        ids = [doctor.id for doctor in doctors]
        history = self.db.get_compensations(self.clinic, ids)
        first_payouts = self.db.first_payout_dates(self.clinic, ids)

        # A doctor's ledger starts with their first terms or first payout,
        # whichever came first; `opening` carries everything since then.
        starts = {}
        for pk in ids:
            candidates = []
            if history.get(pk):
                candidates.append(history[pk][0].effective_from)
            if pk in first_payouts:
                candidates.append(first_payouts[pk].replace(day=1))
            starts[pk] = min(candidates) if candidates else month
        ledger_start = min([*starts.values(), month])
        period_end = month_end(month)

        collected = self.db.collected_by_doctor_month(self.clinic, ids, ledger_start, period_end)
        billed = self.db.billed_by_doctor_month(self.clinic, ids, ledger_start, period_end)
        lab = self.db.expenses_by_doctor_month(
            self.clinic, ids, ExpenseCategory.LAB, ledger_start, period_end
        )
        paid = self.db.expenses_by_doctor_month(
            self.clinic, ids, ExpenseCategory.DOCTOR_SHARE, ledger_start, period_end
        )

        def figures(pk, cursor):
            return (
                collected.get(pk, {}).get(cursor, 0),
                billed.get(pk, {}).get(cursor, 0),
                lab.get(pk, {}).get(cursor, 0),
            )

        rows = []
        for doctor in doctors:
            doctor_history = history.get(doctor.id, [])
            opening = 0
            cursor = starts[doctor.id]
            while cursor < month:
                _base, accrued = accrue(
                    terms_for(doctor_history, cursor), *figures(doctor.id, cursor)
                )
                opening += accrued - paid.get(doctor.id, {}).get(cursor, 0)
                cursor = shift_month(cursor, 1)

            terms = terms_for(doctor_history, month)
            month_collected, month_billed, month_lab = figures(doctor.id, month)
            base_amount, accrued = accrue(terms, month_collected, month_billed, month_lab)
            month_paid = paid.get(doctor.id, {}).get(month, 0)
            rows.append(
                {
                    "doctor_id": doctor.id,
                    "doctor": doctor.full_name,
                    "compensation": terms,
                    "collected": month_collected,
                    "billed": month_billed,
                    "lab": month_lab,
                    "base_amount": base_amount,
                    "accrued": accrued,
                    "opening": opening,
                    "paid": month_paid,
                    "balance": opening + accrued - month_paid,
                }
            )
        return rows

    def get_payroll(self, *args, **kwargs):
        month = self._payroll_month()
        rows = self._payroll_rows(month)
        payroll = {
            "month": month,
            "rows": rows,
            "totals": {
                "accrued": sum(row["accrued"] for row in rows),
                "paid": sum(row["paid"] for row in rows),
                "balance": sum(row["balance"] for row in rows),
            },
        }
        return self.get_response_object(payroll, PayrollSerializer)

    def get_my_month(self, *args, **kwargs):
        """A doctor's own month: what they earned, were paid and are still owed."""
        if self.request.query_params.get("month"):
            month = self._payroll_month()
        else:
            month = clinic_today().replace(day=1)
        [row] = self._payroll_rows(month, doctor_id=self.request.user.id)
        return self.get_response_object({"month": month, **row}, DoctorMonthSerializer)
