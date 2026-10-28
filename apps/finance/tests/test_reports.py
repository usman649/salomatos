from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils.datastructures import MultiValueDict

from apps.core.exceptions import ValidationError
from apps.core.reporting import ReportRange, clinic_today, format_month, parse_range, shift_month
from apps.finance.models import DoctorCompensation, Expense, Payment
from apps.finance.tests.factories import (
    client_for,
    make_admin,
    make_clinic,
    make_doctor,
    make_patient,
    make_treatment,
    make_treatment_type,
)

OVERVIEW_URL = "/api/v1/finance/overview/"
PAYROLL_URL = "/api/v1/finance/payroll/"
ME_URL = "/api/v1/finance/me/"


def pay(treatment, amount, day, method="cash"):
    """A ledger payment as the API records it: the row plus the raised total."""
    Payment.objects.create(
        clinic=treatment.clinic,
        treatment=treatment,
        patient=treatment.patient,
        doctor=treatment.doctor,
        amount=amount,
        method=method,
        date=day,
    )
    treatment.total_paid += amount
    treatment.save(update_fields=["total_paid"])


class ReportRangeTests(SimpleTestCase):
    def test_bucket_follows_the_length(self):
        self.assertEqual(ReportRange(date(2026, 3, 1), date(2026, 3, 7)).bucket, "day")
        self.assertEqual(ReportRange(date(2026, 3, 1), date(2026, 3, 30)).bucket, "day")
        self.assertEqual(ReportRange(date(2026, 1, 1), date(2026, 4, 1)).bucket, "week")
        self.assertEqual(ReportRange(date(2025, 3, 2), date(2026, 3, 1)).bucket, "month")

    def test_weeks_step_from_from_and_months_start_on_the_first(self):
        starts = ReportRange(date(2025, 11, 15), date(2026, 2, 10)).bucket_starts()
        self.assertEqual(starts[:3], [date(2025, 11, 15), date(2025, 11, 22), date(2025, 11, 29)])

        yearly = ReportRange(date(2025, 3, 2), date(2026, 3, 1))
        self.assertEqual(
            yearly.bucket_starts()[:3], [date(2025, 3, 2), date(2025, 4, 1), date(2025, 5, 1)]
        )
        self.assertEqual(yearly.bucket_starts()[-1], date(2026, 3, 1))

    def test_previous_window_has_the_same_length(self):
        previous = ReportRange(date(2026, 3, 1), date(2026, 3, 7)).previous()
        self.assertEqual((previous.start, previous.end), (date(2026, 2, 22), date(2026, 2, 28)))

    def test_parse_range_validates(self):
        def params(**values):
            return MultiValueDict({key: [value] for key, value in values.items()})

        with self.assertRaises(ValidationError):
            parse_range(params(**{"from": "2026-03-01"}))
        with self.assertRaises(ValidationError):
            parse_range(params(**{"from": "2026-03-10", "to": "2026-03-01"}))
        with self.assertRaises(ValidationError):
            parse_range(params(**{"from": "2024-01-01", "to": "2026-01-01"}))
        with self.assertRaises(ValidationError):
            parse_range(params(**{"from": "01.03.2026", "to": "2026-03-01"}))
        self.assertEqual(parse_range(params(**{"from": "2026-03-01", "to": "2026-03-01"})).days, 1)


class FinanceOverviewTests(TestCase):
    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic, full_name="Doctor A")
        self.other_doctor = make_doctor(self.clinic, full_name="Doctor B")
        self.alice = make_patient(self.clinic, full_name="Alice", doctor=self.doctor)
        self.bob = make_patient(self.clinic, full_name="Bob")
        self.filling = make_treatment_type(self.clinic, "Plomba")
        self.owner = client_for(self.clinic)

    def overview(self, start="2026-03-01", end="2026-03-07"):
        return self.owner.get(OVERVIEW_URL, {"from": start, "to": end})

    def test_totals_series_and_breakdowns(self):
        old = make_treatment(self.clinic, self.alice, self.doctor, cost=1_000_000, start_date=date(2026, 2, 1))
        new = make_treatment(
            self.clinic, self.bob, self.other_doctor, cost=600_000, start_date=date(2026, 3, 2),
            treatment_type=self.filling,
        )
        pay(old, 400_000, date(2026, 3, 3), method="card")
        pay(new, 100_000, date(2026, 3, 2))

        response = self.overview()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["totals"],
            {
                "billed": 600_000,
                "collected": 500_000,
                "new_debt": 500_000,
                "outstanding_debt": 1_100_000,
                "debtors_count": 2,
            },
        )
        self.assertEqual(response.data["bucket"], "day")
        self.assertEqual(len(response.data["series"]), 7)
        self.assertEqual(
            response.data["series"][1], {"start": "2026-03-02", "billed": 600_000, "collected": 100_000}
        )
        methods = {row["method"]: row["amount"] for row in response.data["payment_methods"]}
        self.assertEqual(methods, {"cash": 100_000, "card": 400_000, "click": 0, "payme": 0, "transfer": 0})
        self.assertEqual(
            [(row["doctor"], row["collected"]) for row in response.data["doctors"]],
            [("Doctor A", 400_000), ("Doctor B", 100_000)],
        )
        self.assertEqual(
            response.data["treatment_types"],
            [{"treatment_type_id": self.filling.id, "treatment_type": "Plomba", "billed": 600_000}],
        )
        self.assertEqual(
            response.data["top_debtors"][0],
            {
                "patient_id": self.alice.id,
                "patient": "Alice",
                "debt": 600_000,
                "last_payment_date": "2026-03-03",
                "doctor": "Doctor A",
            },
        )

    def test_debt_is_counted_as_it_stood_at_the_end_of_the_period(self):
        treatment = make_treatment(self.clinic, self.alice, self.doctor, cost=1_000_000, start_date=date(2026, 2, 1))
        pay(treatment, 1_000_000, date(2026, 3, 20))

        march_first_week = self.overview()
        self.assertEqual(march_first_week.data["totals"]["outstanding_debt"], 1_000_000)
        self.assertEqual(march_first_week.data["totals"]["debtors_count"], 1)

        after = self.overview("2026-03-15", "2026-03-21")
        self.assertEqual(after.data["totals"]["outstanding_debt"], 0)
        self.assertEqual(after.data["top_debtors"], [])

    def test_amounts_paid_before_the_ledger_count_as_paid(self):
        make_treatment(
            self.clinic, self.alice, self.doctor, cost=1_000_000, paid=700_000, start_date=date(2026, 1, 5)
        )
        response = self.overview()
        self.assertEqual(response.data["totals"]["outstanding_debt"], 300_000)
        self.assertEqual(response.data["totals"]["collected"], 0)

    def test_a_patients_treatments_are_netted(self):
        owed = make_treatment(self.clinic, self.alice, self.doctor, cost=500_000, start_date=date(2026, 2, 1))
        make_treatment(
            self.clinic, self.alice, self.doctor, cost=300_000, paid=400_000, start_date=date(2026, 2, 2)
        )
        make_treatment(self.clinic, self.bob, self.doctor, cost=100_000, start_date=date(2026, 2, 3))
        owed.patient = None
        owed.save(update_fields=["patient"])
        make_treatment(self.clinic, self.alice, self.doctor, cost=200_000, start_date=date(2026, 2, 4))

        totals = self.overview().data["totals"]

        # Alice: 200 000 owed less 100 000 overpaid; Bob 100 000; the orphan 500 000.
        self.assertEqual(totals["outstanding_debt"], 700_000)
        self.assertEqual(totals["debtors_count"], 2)

    def test_voided_payments_are_left_out(self):
        treatment = make_treatment(self.clinic, self.alice, self.doctor, cost=1_000_000, start_date=date(2026, 3, 1))
        pay(treatment, 300_000, date(2026, 3, 2))
        Payment.objects.update(voided_at="2026-03-02T10:00:00Z")
        treatment.total_paid = 0
        treatment.save(update_fields=["total_paid"])

        self.assertEqual(self.overview().data["totals"]["collected"], 0)

    def test_previous_totals_cover_the_window_before(self):
        treatment = make_treatment(self.clinic, self.alice, self.doctor, cost=500_000, start_date=date(2026, 2, 25))
        response = self.overview()
        self.assertEqual(response.data["previous_totals"]["billed"], 500_000)
        self.assertEqual(response.data["totals"]["billed"], 0)
        self.assertEqual(treatment.total_paid, 0)

    def test_other_clinics_money_never_shows(self):
        other = make_clinic()
        other_doctor = make_doctor(other)
        treatment = make_treatment(other, make_patient(other), other_doctor, cost=9_000_000, start_date=date(2026, 3, 2))
        pay(treatment, 1_000_000, date(2026, 3, 2))

        totals = self.overview().data["totals"]
        self.assertEqual(totals["billed"], 0)
        self.assertEqual(totals["collected"], 0)
        self.assertEqual(totals["outstanding_debt"], 0)

    def test_only_the_owner_sees_the_overview(self):
        for user in (make_admin(self.clinic), self.doctor, self.alice):
            response = client_for(user).get(OVERVIEW_URL, {"from": "2026-03-01", "to": "2026-03-07"})
            self.assertEqual(response.status_code, 403, user.role)


class PayrollTests(TestCase):
    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic, full_name="Doctor A")
        self.patient = make_patient(self.clinic)
        self.owner = client_for(self.clinic)

    def terms(self, effective_from, percent, fixed=0, base="collected", deduct_lab=True):
        return DoctorCompensation.objects.create(
            clinic=self.clinic,
            doctor=self.doctor,
            percent=Decimal(percent),
            fixed=fixed,
            base=base,
            deduct_lab=deduct_lab,
            effective_from=effective_from,
        )

    def expense(self, category, amount, day):
        return Expense.objects.create(
            clinic=self.clinic, category=category, amount=amount, method="cash", date=day, doctor=self.doctor
        )

    def payroll(self, month):
        response = self.owner.get(PAYROLL_URL, {"month": month})
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_percent_of_collected_minus_lab_rounded_to_thousands(self):
        self.terms(date(2026, 3, 1), "35")
        treatment = make_treatment(self.clinic, self.patient, self.doctor, cost=30_000_000, start_date=date(2026, 3, 2))
        pay(treatment, 20_001_300, date(2026, 3, 10))
        self.expense("lab", 3_000_000, date(2026, 3, 12))
        self.expense("doctor_share", 2_000_000, date(2026, 3, 15))

        row = self.payroll("2026-03")["rows"][0]

        self.assertEqual(row["collected"], 20_001_300)
        self.assertEqual(row["billed"], 30_000_000)
        self.assertEqual(row["lab"], 3_000_000)
        self.assertEqual(row["base_amount"], 17_001_300)
        # 35% of 17 001 300 = 5 950 455, kept to whole thousands.
        self.assertEqual(row["accrued"], 5_950_000)
        self.assertEqual(row["paid"], 2_000_000)
        self.assertEqual(row["opening"], 0)
        self.assertEqual(row["balance"], 3_950_000)
        self.assertEqual(row["compensation"]["percent"], 35.0)
        self.assertEqual(row["compensation"]["effective_from"], "2026-03")

    def test_billed_base_fixed_salary_and_no_lab_deduction(self):
        self.terms(date(2026, 3, 1), "10", fixed=2_000_000, base="billed", deduct_lab=False)
        make_treatment(self.clinic, self.patient, self.doctor, cost=5_000_000, start_date=date(2026, 3, 2))
        self.expense("lab", 1_000_000, date(2026, 3, 3))

        row = self.payroll("2026-03")["rows"][0]
        self.assertEqual(row["base_amount"], 5_000_000)
        self.assertEqual(row["accrued"], 2_500_000)

    def test_unpaid_balance_carries_into_the_next_month(self):
        self.terms(date(2026, 1, 1), "50")
        treatment = make_treatment(self.clinic, self.patient, self.doctor, cost=10_000_000, start_date=date(2026, 1, 2))
        pay(treatment, 4_000_000, date(2026, 1, 10))
        self.expense("doctor_share", 1_500_000, date(2026, 1, 28))
        # Paid ahead in February, with nothing earned.
        self.expense("doctor_share", 1_000_000, date(2026, 2, 5))

        february = self.payroll("2026-02")["rows"][0]
        self.assertEqual(february["opening"], 500_000)
        self.assertEqual(february["balance"], -500_000)
        march = self.payroll("2026-03")
        self.assertEqual(march["rows"][0]["opening"], -500_000)
        self.assertEqual(march["totals"]["balance"], -500_000)

    def test_later_terms_apply_from_their_month_only(self):
        self.terms(date(2026, 1, 1), "30")
        self.terms(date(2026, 3, 1), "40")
        for month in (1, 3):
            treatment = make_treatment(
                self.clinic, self.patient, self.doctor, cost=1_000_000, start_date=date(2026, month, 2)
            )
            pay(treatment, 1_000_000, date(2026, month, 3))

        self.assertEqual(self.payroll("2026-01")["rows"][0]["accrued"], 300_000)
        march = self.payroll("2026-03")["rows"][0]
        self.assertEqual(march["accrued"], 400_000)
        self.assertEqual(march["opening"], 300_000)

    def test_a_doctor_without_terms_accrues_nothing(self):
        row = self.payroll("2026-03")["rows"][0]
        self.assertIsNone(row["compensation"])
        self.assertEqual(row["accrued"], 0)

    def test_voided_payouts_do_not_count(self):
        payout = self.expense("doctor_share", 1_000_000, date(2026, 3, 5))
        payout.voided_at = "2026-03-06T00:00:00Z"
        payout.save()
        self.assertEqual(self.payroll("2026-03")["rows"][0]["paid"], 0)

    def test_compensation_history_and_create(self):
        url = f"/api/v1/finance/doctors/{self.doctor.id}/compensation/"
        this_month = clinic_today().replace(day=1)
        now, later = format_month(this_month), format_month(shift_month(this_month, 2))
        created = self.owner.post(
            url,
            {"percent": 32.5, "fixed": 0, "base": "collected", "deduct_lab": True, "effective_from": now},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["percent"], 32.5)
        self.owner.post(
            url,
            {"percent": 0, "fixed": 3_000_000, "base": "collected", "deduct_lab": True, "effective_from": later},
            format="json",
        )

        history = self.owner.get(url)
        self.assertEqual([entry["effective_from"] for entry in history.data], [later, now])

        neither = self.owner.post(
            url,
            {"percent": 0, "fixed": 0, "base": "collected", "deduct_lab": True, "effective_from": later},
            format="json",
        )
        self.assertEqual(neither.status_code, 400)
        over = self.owner.post(
            url,
            {"percent": 101, "fixed": 0, "base": "collected", "deduct_lab": True, "effective_from": later},
            format="json",
        )
        self.assertEqual(over.status_code, 400)

    def test_terms_cannot_rewrite_past_months(self):
        url = f"/api/v1/finance/doctors/{self.doctor.id}/compensation/"
        last_month = format_month(shift_month(clinic_today().replace(day=1), -1))
        response = self.owner.post(
            url,
            {"percent": 30, "base": "collected", "deduct_lab": False, "effective_from": last_month},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errors"]["effective_from"], "past_month")

    def test_compensation_of_another_clinics_doctor_is_not_found(self):
        foreign = make_doctor(make_clinic())
        response = self.owner.get(f"/api/v1/finance/doctors/{foreign.id}/compensation/")
        self.assertEqual(response.status_code, 404)

    def test_payroll_looks_at_most_a_year_ahead(self):
        this_month = clinic_today().replace(day=1)
        self.payroll(format_month(shift_month(this_month, 12)))
        response = self.owner.get(PAYROLL_URL, {"month": format_month(shift_month(this_month, 13))})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["errors"]["month"], "too_far")

    def test_only_the_owner_sees_payroll(self):
        for user in (make_admin(self.clinic), self.doctor):
            self.assertEqual(client_for(user).get(PAYROLL_URL, {"month": "2026-03"}).status_code, 403)


class DoctorOwnMonthTests(TestCase):
    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic, full_name="Doctor A")
        self.colleague = make_doctor(self.clinic, full_name="Doctor B")
        patient = make_patient(self.clinic)
        for doctor, amount in ((self.doctor, 1_000_000), (self.colleague, 5_000_000)):
            DoctorCompensation.objects.create(
                clinic=self.clinic, doctor=doctor, percent=Decimal(20), effective_from=date(2026, 3, 1)
            )
            treatment = make_treatment(self.clinic, patient, doctor, cost=amount, start_date=date(2026, 3, 2))
            pay(treatment, amount, date(2026, 3, 2))

    def test_a_doctor_sees_their_own_month_only(self):
        response = client_for(self.doctor).get(ME_URL, {"month": "2026-03"})

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["doctor_id"], self.doctor.id)
        self.assertEqual(response.data["month"], "2026-03")
        self.assertEqual(response.data["collected"], 1_000_000)
        self.assertEqual(response.data["accrued"], 200_000)

    def test_the_month_defaults_to_the_current_one(self):
        response = client_for(self.doctor).get(ME_URL)
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.data["month"], r"^\d{4}-\d{2}$")

    def test_only_doctors_use_it(self):
        self.assertEqual(client_for(self.clinic).get(ME_URL).status_code, 403)
        self.assertEqual(client_for(make_admin(self.clinic)).get(ME_URL).status_code, 403)
        self.assertEqual(client_for(make_doctor(None)).get(ME_URL).status_code, 403)
