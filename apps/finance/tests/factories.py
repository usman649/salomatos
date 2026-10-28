"""Small builders for tests of the new apps. No fixtures: every test states its own data."""
import itertools
from datetime import date, time

from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.calendars.models import Appointment
from apps.clinic.models import Treatment, TreatmentType

_sequence = itertools.count(1)


def make_user(role, clinic=None, **fields):
    number = next(_sequence)
    return User.objects.create(
        username=f"{role}{number}",
        full_name=fields.pop("full_name", f"{role.title()} {number}"),
        phone_number=f"+99890{number:07d}",
        role=role,
        clinic=clinic,
        **fields,
    )


def make_clinic(**fields):
    return make_user(User.Roles.SUPERADMIN, **fields)


def make_doctor(clinic, **fields):
    return make_user(User.Roles.DOCTOR, clinic=clinic, **fields)


def make_admin(clinic, **fields):
    return make_user(User.Roles.ADMIN, clinic=clinic, **fields)


def make_patient(clinic, **fields):
    return make_user(User.Roles.PATIENT, clinic=clinic, **fields)


def make_treatment_type(clinic, name="Plomba", price=None):
    return TreatmentType.objects.create(clinic=clinic, name=name, price=price)


def make_treatment(clinic, patient, doctor, cost, paid=0, start_date=date(2026, 1, 10), **fields):
    return Treatment.objects.create(
        clinic=clinic,
        patient=patient,
        doctor=doctor,
        total_treatment_cost=cost,
        total_paid=paid,
        visit_number=fields.pop("visit_number", 1),
        start_date=start_date,
        **fields,
    )


def make_appointment(clinic, doctor, patient, day, at=time(10, 0), **fields):
    return Appointment.objects.create(
        clinic=clinic, doctor=doctor, patient=patient, date=day, time=at, **fields
    )


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client
