from django.db.models import Q
from apps.core.exceptions import ObjectNotFoundException
from apps.authentication.models import User


def doctor_patients(queryset, doctor):
    # A doctor's patients: assigned to them, or treated or booked by them.
    return queryset.filter(
        Q(doctor=doctor)
        | Q(patient_treatments__doctor=doctor)
        | Q(patient_appointments__doctor=doctor)
    ).distinct()


class PatientRepository:
    def get_patients(self,clinic_id,doctor=None):
        patients = User.objects.filter(role=User.Roles.PATIENT,clinic=clinic_id,is_active=True)
        if doctor is not None:
            patients = doctor_patients(patients, doctor)
        return patients


    def get_patient(self,user_id,clinic_id,doctor=None):
        patient = self.get_patients(clinic_id, doctor).filter(id=user_id).first()
        if not patient:
            raise ObjectNotFoundException(
                message="Patient not found",
                message_key="patient_not_found",
            )
        return patient


