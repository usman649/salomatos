from apps.core.exceptions import ObjectNotFoundException
from apps.authentication.models import User

class PatientRepository:
    def get_patients(self,user):
        patients = User.objects.filter(role=User.Roles.PATIENT,clinic=user)
        return patients


    def get_patient(self,user_id,user):
        patient = User.objects.filter(id=user_id,role=User.Roles.PATIENT,clinic=user).first()
        if not patient:
            raise ObjectNotFoundException(
                message="Patient not found",
                message_key="patient_not_found",
            )
        return patient


