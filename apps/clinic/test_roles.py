"""Who may read and change what in the clinic's own records."""
from datetime import date, time

from django.test import TestCase

from apps.calendars.models import Appointment
from apps.clinic.models import Treatment
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

PATIENTS = "/api/v1/clinic/patients/"
TREATMENTS = "/api/v1/clinic/treatments/"
TREATMENT_TYPES = "/api/v1/clinic/treatment-types/"
DOCTORS = "/api/v1/clinic/doctors/"
ADMINS = "/api/v1/clinic/admins/"
APPOINTMENTS = "/api/v1/calendars/appointments/"
RECIPES = "/api/v1/core/recipes/"


def ids(response):
    data = response.data
    rows = data["results"] if isinstance(data, dict) and "results" in data else data
    return sorted(row["id"] for row in rows)


class ClinicRolesTests(TestCase):
    def setUp(self):
        self.clinic = make_clinic()
        self.doctor = make_doctor(self.clinic)
        self.colleague = make_doctor(self.clinic)
        self.mine = make_patient(self.clinic, doctor=self.doctor)
        self.treated = make_patient(self.clinic)
        self.theirs = make_patient(self.clinic, doctor=self.colleague)
        self.my_treatment = make_treatment(self.clinic, self.treated, self.doctor, cost=100)
        self.their_treatment = make_treatment(self.clinic, self.theirs, self.colleague, cost=100)
        self.my_visit = make_appointment(self.clinic, self.doctor, self.mine, date(2026, 3, 2))
        self.their_visit = make_appointment(self.clinic, self.colleague, self.theirs, date(2026, 3, 2))

        self.owner = client_for(self.clinic)
        self.admin = client_for(make_admin(self.clinic))
        self.me = client_for(self.doctor)

    def test_admin_sees_the_whole_clinic(self):
        self.assertEqual(ids(self.admin.get(PATIENTS)), sorted([self.mine.id, self.treated.id, self.theirs.id]))
        self.assertEqual(ids(self.admin.get(TREATMENTS)), sorted([self.my_treatment.id, self.their_treatment.id]))
        self.assertEqual(ids(self.admin.get(APPOINTMENTS)), sorted([self.my_visit.id, self.their_visit.id]))
        self.assertEqual(len(self.admin.get(DOCTORS).data), 2)

    def test_a_doctor_sees_only_their_own(self):
        self.assertEqual(ids(self.me.get(PATIENTS)), sorted([self.mine.id, self.treated.id]))
        self.assertEqual(ids(self.me.get(TREATMENTS)), [self.my_treatment.id])
        self.assertEqual(ids(self.me.get(APPOINTMENTS)), [self.my_visit.id])
        self.assertEqual(self.me.get(f"{PATIENTS}{self.theirs.id}/").status_code, 404)
        self.assertEqual(self.me.get(f"{PATIENTS}{self.mine.id}/").status_code, 200)

    def test_a_doctor_cannot_touch_a_colleagues_records(self):
        patched = self.me.patch(f"{TREATMENTS}{self.their_treatment.id}/", {"notes": "x"}, format="json")
        self.assertEqual(patched.status_code, 404)
        moved = self.me.patch(f"{APPOINTMENTS}{self.their_visit.id}/", {"notes": "x"}, format="json")
        self.assertEqual(moved.status_code, 404)
        self.assertEqual(self.me.delete(f"{APPOINTMENTS}{self.their_visit.id}/").status_code, 404)
        self.assertTrue(Appointment.objects.filter(pk=self.their_visit.pk).exists())

    def test_a_doctor_records_treatments_and_visits_only_as_themselves(self):
        body = {
            "patient": self.mine.id,
            "doctor": self.colleague.id,
            "total_treatment_cost": 100,
            "visit_number": 1,
            "start_date": "2026-03-01",
        }
        self.assertEqual(self.me.post(TREATMENTS, [body], format="json").status_code, 400)
        created = self.me.post(TREATMENTS, [{**body, "doctor": self.doctor.id}], format="json")
        self.assertEqual(created.status_code, 200, created.data)
        reassigned = self.me.patch(
            f"{TREATMENTS}{self.my_treatment.id}/", {"doctor": self.colleague.id}, format="json"
        )
        self.assertEqual(reassigned.status_code, 400)

        visit = {"patient": self.mine.id, "doctor": self.doctor.id, "date": "2026-03-03", "time": "10:00"}
        self.assertEqual(self.me.post(APPOINTMENTS, visit, format="json").status_code, 200)
        foreign = {**visit, "doctor": self.colleague.id, "time": "11:00"}
        self.assertEqual(self.me.post(APPOINTMENTS, foreign, format="json").status_code, 400)

    def test_writes_by_role(self):
        patient = {"full_name": "New Patient", "phone_number": "+998901112233"}
        self.assertEqual(self.me.post(PATIENTS, patient, format="json").status_code, 403)
        self.assertEqual(self.admin.post(PATIENTS, patient, format="json").status_code, 200)

        treatment = {
            "patient": self.mine.id,
            "doctor": self.doctor.id,
            "total_treatment_cost": 100,
            "visit_number": 1,
            "start_date": "2026-03-01",
        }
        self.assertEqual(self.admin.post(TREATMENTS, [treatment], format="json").status_code, 403)
        self.assertEqual(self.me.delete(f"{TREATMENTS}{self.my_treatment.id}/").status_code, 403)

        self.assertEqual(self.admin.post(TREATMENT_TYPES, {"name": "X"}, format="json").status_code, 403)
        self.assertEqual(self.admin.get(TREATMENT_TYPES).status_code, 200)
        self.assertEqual(self.admin.post(DOCTORS, {}, format="json").status_code, 403)
        self.assertEqual(self.admin.get(ADMINS).status_code, 403)
        self.assertEqual(self.me.get(ADMINS).status_code, 403)

    def test_patients_cannot_use_the_staff_api(self):
        patient = client_for(self.mine)
        for url in (PATIENTS, TREATMENTS, APPOINTMENTS, DOCTORS, RECIPES):
            self.assertEqual(patient.get(url).status_code, 403, url)

    def test_another_clinics_ids_do_not_exist(self):
        other = make_clinic()
        stranger = make_patient(other)
        other_type = make_treatment_type(other, "Foreign")
        body = {
            "patient": stranger.id,
            "doctor": self.doctor.id,
            "total_treatment_cost": 100,
            "visit_number": 1,
            "start_date": "2026-03-01",
        }
        refused = self.owner.post(TREATMENTS, [body], format="json")
        self.assertEqual(refused.status_code, 400)
        typed = {**body, "patient": self.mine.id, "treatment_type": other_type.id}
        self.assertEqual(self.owner.post(TREATMENTS, [typed], format="json").status_code, 400)
        self.assertFalse(Treatment.objects.filter(patient=stranger).exists())

        visit = {"patient": stranger.id, "doctor": self.doctor.id, "date": "2026-03-04", "time": "09:00"}
        self.assertEqual(self.admin.post(APPOINTMENTS, visit, format="json").status_code, 400)

    def test_the_owner_still_does_everything(self):
        self.assertEqual(len(ids(self.owner.get(TREATMENTS))), 2)
        visit = {"patient": self.theirs.id, "doctor": self.colleague.id, "date": "2026-03-05", "time": time(9).isoformat()}
        self.assertEqual(self.owner.post(APPOINTMENTS, visit, format="json").status_code, 200)


class StaffEditTests(TestCase):
    def test_the_owner_can_edit_an_admin(self):
        clinic = make_clinic()
        admin = make_admin(clinic)
        response = client_for(clinic).patch(f"{ADMINS}{admin.id}/", {"full_name": "Renamed"}, format="json")
        self.assertEqual(response.status_code, 200, getattr(response, "data", None))
        admin.refresh_from_db()
        self.assertEqual(admin.full_name, "Renamed")
