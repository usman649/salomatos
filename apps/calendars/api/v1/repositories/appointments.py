from apps.core.exceptions import ObjectNotFoundException
from apps.calendars.models import Appointment


class AppointmentRepository:
    def get_appointments(self,user):
        appointment = Appointment.objects.filter(clinic=user)
        return appointment


    def get_appointment(self,appointment_id):
        appointment = Appointment.objects.filter(id=appointment_id).first()
        if not appointment:
            raise ObjectNotFoundException(
                message='Appointment not found',
                message_key='appointment_not_found',
            )
        return appointment