from apps.core.exceptions import ObjectNotFoundException
from apps.authentication.models import User,DoctorType

class DoctorRepository:
    def get_doctors(self,clinic_id):
        doctor = User.objects.filter(role=User.Roles.DOCTOR,clinic=clinic_id)
        return doctor

    def get_doctor(self,user_id,clinic_id):
        doctor = User.objects.filter(id=user_id,role=User.Roles.DOCTOR,clinic=clinic_id).first()
        if not doctor:
            raise ObjectNotFoundException(
                message="Doctor not found",
                message_key="doctor_not_found",
            )
        return doctor

    def get_doctor_types(self,clinic_id):
        doctor_type = DoctorType.objects.filter(clinic=clinic_id)
        return doctor_type

    def get_doctor_type(self,doctor_type_id,clinic_id):
        doctor_type = DoctorType.objects.filter(id=doctor_type_id,clinic=clinic_id).first()
        if not doctor_type:
            raise ObjectNotFoundException(
                message="Doctor Type not found",
                message_key="doctor_type_not_found",
            )
        return doctor_type

