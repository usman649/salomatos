from apps.core.exceptions import ObjectNotFoundException
from apps.clinic.models import Clinic

class ClinicRepository:
    def get_clinics(self,user):
        clinics = Clinic.objects.filter(admin=user)
        return clinics

    def get_clinic(self,clinic_id):
        clinic = Clinic.objects.filter(id=clinic_id).first()
        if not clinic:
            raise ObjectNotFoundException(
                message="Clinic not found",
                message_key="clinic_not_found",
            )
        return clinic





