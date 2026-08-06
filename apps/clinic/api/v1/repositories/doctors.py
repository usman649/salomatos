from apps.core.exceptions import ObjectNotFoundException
from apps.authentication.models import User

class DoctorRepository:
    def get_doctors(self,user):
        doctor = User.objects.filter(role=User.Roles.DOCTOR,clinic=user)
        return doctor

    def get_doctor(self,user_id):
        doctor = User.objects.filter(id=user_id,role=User.Roles.DOCTOR).first()
        if not doctor:
            raise ObjectNotFoundException(
                message="Doctor not found",
                message_key="doctor_not_found",
            )
        return doctor

