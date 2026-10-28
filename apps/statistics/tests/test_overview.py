from datetime import date, time, timedelta
from django.test import TestCase

from apps.calendars.models import Appointment
from apps.clinic.models import Treatment
from apps.core.reporting import clinic_today
from apps.finance.models import Payment
from apps.finance.tests.factories import (
    client_for,
    make_admin,
    make_appointment,
    make_clinic,
    make_doctor,
    make_patient,
    make_treatment,
    make_treatment_type,
)

URL = "/api/v1/statistics/overview/"
ME_URL = "/api/v1/statistics/me/"
TREATMENTS_URL = "/api/v1/clinic/treatments/"


class CompletedDateTests(TestCase):
    """The treatments API carries the completion date the statistics count by."""

    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic)
        self.patient = make_patient(self.clinic)
        self.owner = client_for(self.clinic)

    def create(self, **fields):
        body = {
            "patient": self.patient.id,
            "doctor": self.doctor.id,
            "total_treatment_cost": 100,
            "total_paid": 0,
            "visit_number": 1,
            "start_date": "2026-03-01",
            **fields,
        }
        return self.owner.post(TREATMENTS_URL, [body], format="json")

    def test_a_completed_treatment_keeps_its_date(self):
        response = self.create(status="completed", completed_date="2026-03-09")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Treatment.objects.get().completed_date, date(2026, 3, 9))

    def test_a_date_without_completion_is_dropped(self):
        self.create(status="in_progress", completed_date="2026-03-09")
        self.assertIsNone(Treatment.objects.get().completed_date)

    def test_reopening_clears_the_date(self):
        self.create(status="completed", completed_date="2026-03-09")
        treatment = Treatment.objects.get()
        response = self.owner.patch(
            f"{TREATMENTS_URL}{treatment.id}/", {"status": "in_progress"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        treatment.refresh_from_db()
        self.assertIsNone(treatment.completed_date)

    def test_completing_without_a_date_takes_today(self):
        self.create()
        treatment = Treatment.objects.get()
        self.owner.patch(f"{TREATMENTS_URL}{treatment.id}/", {"status": "completed"}, format="json")
        treatment.refresh_from_db()
        self.assertEqual(treatment.completed_date, clinic_today())

    def test_editing_a_completed_treatment_keeps_its_date(self):
        self.create(status="completed", completed_date="2026-03-09")
        treatment = Treatment.objects.get()
        self.owner.patch(f"{TREATMENTS_URL}{treatment.id}/", {"notes": "Checked"}, format="json")
        treatment.refresh_from_db()
        self.assertEqual(treatment.completed_date, date(2026, 3, 9))

    def test_a_future_completion_is_refused(self):
        future = (clinic_today() + timedelta(days=1)).isoformat()
        response = self.create(status="completed", completed_date=future)
        self.assertEqual(response.status_code, 400)

    def test_a_treatment_booked_ahead_may_complete_on_its_start(self):
        start = (clinic_today() + timedelta(days=3)).isoformat()
        response = self.create(start_date=start, status="completed", completed_date=start)
        self.assertEqual(response.status_code, 200, response.data)

    def test_completion_before_the_start_is_refused(self):
        response = self.create(status="completed", completed_date="2026-02-28")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Treatment.objects.exists())


class TreatmentPaidTotalTests(TestCase):
    """Money reaches a treatment only through finance payments."""

    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic)
        self.patient = make_patient(self.clinic)
        self.owner = client_for(self.clinic)

    def test_the_amount_paid_up_front_becomes_a_payment_of_today(self):
        body = {
            "patient": self.patient.id,
            "doctor": self.doctor.id,
            "total_treatment_cost": 1_000_000,
            "visit_number": 1,
            "start_date": "2026-03-01",
        }
        response = self.owner.post(
            TREATMENTS_URL, [{**body, "total_paid": 500_000}, body], format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        paid, unpaid = Treatment.objects.order_by("id")
        self.assertEqual(paid.total_paid, 500_000)
        self.assertEqual(unpaid.total_paid, 0)
        payment = Payment.objects.get()
        self.assertEqual(
            (payment.treatment, payment.patient, payment.doctor, payment.amount, payment.date),
            (paid, self.patient, self.doctor, 500_000, clinic_today()),
        )
        self.assertEqual(payment.created_by, self.clinic)

    def test_paying_more_than_the_cost_up_front_is_refused(self):
        body = {
            "patient": self.patient.id,
            "doctor": self.doctor.id,
            "total_treatment_cost": 100,
            "total_paid": 101,
            "visit_number": 1,
            "start_date": "2026-03-01",
        }
        self.assertEqual(self.owner.post(TREATMENTS_URL, [body], format="json").status_code, 400)
        self.assertFalse(Treatment.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_an_edit_never_overwrites_what_payments_set(self):
        treatment = make_treatment(self.clinic, self.patient, self.doctor, cost=1_000, start_date=date(2026, 3, 1))
        paid = self.owner.post(
            "/api/v1/finance/payments/",
            {"treatment": treatment.id, "amount": 400, "date": "2026-03-02"},
            format="json",
        )
        self.assertEqual(paid.status_code, 201, paid.data)

        response = self.owner.patch(
            f"{TREATMENTS_URL}{treatment.id}/", {"total_paid": 0, "notes": "Stale form"}, format="json"
        )

        self.assertEqual(response.status_code, 200, response.data)
        treatment.refresh_from_db()
        self.assertEqual(treatment.total_paid, 400)
        self.assertEqual(treatment.notes, "Stale form")


class StatisticsOverviewTests(TestCase):
    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic, full_name="Doctor A")
        self.colleague = make_doctor(self.clinic, full_name="Doctor B")
        self.returning = make_patient(self.clinic)
        self.newcomer = make_patient(self.clinic)
        self.filling = make_treatment_type(self.clinic, "Plomba")
        self.owner = client_for(self.clinic)

        make_appointment(self.clinic, self.doctor, self.returning, date(2026, 2, 10))
        # 2026-03-02 is a Monday.
        make_appointment(
            self.clinic, self.doctor, self.returning, date(2026, 3, 2), at=time(10, 30),
            status=Appointment.Status.COMPLETED,
        )
        make_appointment(self.clinic, self.colleague, self.newcomer, date(2026, 3, 3), at=time(15, 0))
        make_appointment(self.clinic, self.colleague, None, date(2026, 3, 3), at=time(15, 0), guest_name="Guest")

        make_treatment(
            self.clinic, self.returning, self.doctor, cost=100, start_date=date(2026, 2, 20),
            treatment_type=self.filling, tooth_number=36,
            status=Treatment.Status.COMPLETED, completed_date=date(2026, 3, 4),
        )
        make_treatment(self.clinic, self.newcomer, self.colleague, cost=100, start_date=date(2026, 3, 3))

    def overview(self, client=None, url=URL, start="2026-03-01", end="2026-03-07"):
        response = (client or self.owner).get(url, {"from": start, "to": end})
        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        return response.data

    def test_totals(self):
        totals = self.overview()["totals"]
        self.assertEqual(
            totals,
            {
                "appointments": 3,
                "appointments_completed": 1,
                "new_patients": 1,
                "returning_patients": 1,
                "treatments_completed": 1,
                "treatments_started": 1,
                "treatments_in_progress": 1,
            },
        )

    def test_in_progress_is_counted_as_it_stood_at_the_end(self):
        february = self.overview(start="2026-02-01", end="2026-02-28")["totals"]
        # Started in February, completed only in March: still open at the end of February.
        self.assertEqual(february["treatments_in_progress"], 1)
        self.assertEqual(february["treatments_completed"], 0)

    def test_series_doctors_types_hours_and_teeth(self):
        data = self.overview()

        self.assertEqual(data["bucket"], "day")
        self.assertEqual(data["appointments_series"][1], {"start": "2026-03-02", "total": 1, "completed": 1})
        self.assertEqual(data["appointments_series"][2]["total"], 2)
        self.assertEqual(data["treatments_series"][3], {"start": "2026-03-04", "completed": 1})
        self.assertEqual(
            [(row["doctor"], row["appointments"], row["treatments_completed"]) for row in data["doctors"]],
            [("Doctor B", 2, 0), ("Doctor A", 1, 1)],
        )
        self.assertEqual(
            data["treatment_types"],
            [{"treatment_type_id": self.filling.id, "treatment_type": "Plomba", "count": 1}],
        )
        self.assertEqual(
            data["busy_hours"],
            [{"weekday": 1, "hour": 10, "appointments": 1}, {"weekday": 2, "hour": 15, "appointments": 2}],
        )
        self.assertEqual(len(data["teeth"]), 32)
        self.assertEqual({row["tooth"]: row["count"] for row in data["teeth"]}["36"], 1)

    def test_a_completed_treatment_without_a_date_counts_on_its_start(self):
        make_treatment(
            self.clinic, self.newcomer, self.doctor, cost=100, start_date=date(2026, 3, 5),
            status=Treatment.Status.COMPLETED,
        )
        self.assertEqual(self.overview()["totals"]["treatments_completed"], 2)

    def test_previous_totals_cover_the_window_before(self):
        previous = self.overview()["previous_totals"]
        self.assertEqual(previous["appointments"], 0)
        self.assertEqual(previous["treatments_started"], 0)

    def test_a_doctor_sees_only_their_own_work(self):
        data = self.overview(client=client_for(self.colleague), url=ME_URL)

        self.assertEqual(data["totals"]["appointments"], 2)
        self.assertEqual(data["totals"]["treatments_completed"], 0)
        self.assertEqual(data["totals"]["new_patients"], 1)
        self.assertEqual(data["totals"]["returning_patients"], 0)
        self.assertEqual([row["doctor_id"] for row in data["doctors"]], [self.colleague.id])

    def test_other_clinics_are_never_counted(self):
        data = self.overview(client=client_for(make_clinic()))
        self.assertEqual(data["totals"]["appointments"], 0)
        self.assertEqual(data["doctors"], [])

    def test_who_may_read_which_report(self):
        params = {"from": "2026-03-01", "to": "2026-03-07"}
        for user in (make_admin(self.clinic), self.doctor, self.returning):
            self.assertEqual(client_for(user).get(URL, params).status_code, 403, user.role)
        for user in (self.clinic, make_admin(self.clinic), self.returning):
            self.assertEqual(client_for(user).get(ME_URL, params).status_code, 403, user.role)

    def test_range_is_required(self):
        self.assertEqual(self.owner.get(URL).status_code, 400)
