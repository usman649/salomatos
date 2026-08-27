from apps.core.exceptions import ObjectNotFoundException
from apps.authentication.models import User,DoctorType

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

    def get_doctor_types(self,user):
        doctor_type = DoctorType.objects.filter(clinic=user)
        return doctor_type

    def get_doctor_type(self,doctor_type_id):
        doctor_type = DoctorType.objects.filter(id=doctor_type_id).first()
        if not doctor_type:
            raise ObjectNotFoundException(
                message="Doctor Type not found",
                message_key="doctor_type_not_found",
            )
        return doctor_type

