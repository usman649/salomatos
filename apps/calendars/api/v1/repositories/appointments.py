from apps.core.exceptions import ObjectNotFoundException
from apps.calendars.models import Appointment


class AppointmentRepository:
    def get_appointments(self,clinic_id,doctor=None):
        appointment = Appointment.objects.filter(clinic=clinic_id)
        if doctor is not None:
            appointment = appointment.filter(doctor=doctor)
        return appointment


    def get_appointment(self,appointment_id,clinic_id,doctor=None):
        appointment = self.get_appointments(clinic_id, doctor).filter(id=appointment_id).first()
        if not appointment:
            raise ObjectNotFoundException(
                message='Appointment not found',
                message_key='appointment_not_found',
            )
        return appointment