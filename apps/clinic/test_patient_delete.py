from django.test import TestCase
from rest_framework.test import APIClient
from apps.authentication.models import User
from datetime import timedelta
from django.utils import timezone
from apps.clinic.models import Treatment
from apps.calendars.models import Appointment


class PatientDeleteTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create(username='owner', full_name='Owner', phone_number='+998901112233', role=User.Roles.SUPERADMIN)
        self.other = User.objects.create(username='other', full_name='Other', phone_number='+998901112234', role=User.Roles.SUPERADMIN)
        self.admin = User.objects.create(username='adm', full_name='Adm', phone_number='+998901112235', role=User.Roles.ADMIN, clinic=self.owner)
        self.patient = User.objects.create(full_name='P', phone_number='+998901112236', role=User.Roles.PATIENT, clinic=self.owner)
        self.treatment = Treatment.objects.create(clinic=self.owner, patient=self.patient, total_treatment_cost=100, total_paid=50, visit_number=1, start_date='2026-10-01')
        self.doctor = User.objects.create(username='doc', full_name='Doc', phone_number='+998901112237', role=User.Roles.DOCTOR, clinic=self.owner)
        today = timezone.localdate()
        mk = lambda d, st: Appointment.objects.create(clinic=self.owner, patient=self.patient, doctor=self.doctor, date=d, time='10:00', status=st)
        self.future = mk(today + timedelta(days=3), Appointment.Status.IN_PROGRESS)
        self.past = mk(today - timedelta(days=3), Appointment.Status.IN_PROGRESS)
        self.done = mk(today + timedelta(days=1), Appointment.Status.COMPLETED)
        self.c = APIClient()
        self.url = f'/api/v1/clinic/patients/{self.patient.id}/'

    def test_superadmin_archives_patient_and_keeps_history(self):
        self.c.force_authenticate(self.owner)
        r = self.c.delete(self.url)
        self.assertEqual(r.status_code, 204)
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)
        self.treatment.refresh_from_db()
        self.assertEqual(self.treatment.patient_id, self.patient.id)
        self.assertFalse(Appointment.objects.filter(id=self.future.id).exists())
        self.assertTrue(Appointment.objects.filter(id=self.past.id).exists())
        self.assertTrue(Appointment.objects.filter(id=self.done.id).exists())
        self.assertEqual(self.c.get(self.url).status_code, 404)
        ids = [p['id'] for p in self.c.get('/api/v1/clinic/patients/').data['results']]
        self.assertNotIn(self.patient.id, ids)
        self.assertEqual(self.c.delete(self.url).status_code, 404)

    def test_other_clinic_gets_404(self):
        self.c.force_authenticate(self.other)
        self.assertEqual(self.c.delete(self.url).status_code, 404)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_active)

    def test_admin_forbidden(self):
        self.c.force_authenticate(self.admin)
        self.assertEqual(self.c.delete(self.url).status_code, 403)
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_active)
        self.assertTrue(Appointment.objects.filter(id=self.future.id).exists())

    def test_doctor_forbidden(self):
        self.c.force_authenticate(self.doctor)
        self.assertEqual(self.c.delete(self.url).status_code, 403)

    def test_anonymous_401(self):
        self.assertEqual(self.c.delete(self.url).status_code, 401)
