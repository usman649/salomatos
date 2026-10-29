from apps.calendars.models import Appointment
from apps.calendars.api.v1.serializers.appointments import (
    AppointmentListSerializer,
    AppointmentCreateUpdateSerializer
)
from apps.calendars.api.v1.repositories.appointments import AppointmentRepository
from apps.core.services import BaseService
from apps.core.permissions import get_clinic, own_doctor
from apps.calendars.api.v1.filters.appointments import AppointmentFilter
from rest_framework import status

class AppointmentService(BaseService):
    def __init__(self,request):
        super().__init__(request)
        self.db = AppointmentRepository()
        self.clinic = get_clinic(request.user)
        # A doctor works only with their own records; others see the whole clinic.
        self.doctor = own_doctor(request.user)

    def get_appointments(self,*args,**kwargs):
        unfiltered_appointments = self.db.get_appointments(clinic_id=self.clinic, doctor=self.doctor)
        filtered_appointments = AppointmentFilter(
            data=self.request.query_params,
            queryset=unfiltered_appointments,
            request=self.request,
        ).qs

        return self.get_paginated_response(
            filtered_appointments,
            AppointmentListSerializer,
            context={'request': self.request},
        )

    def create_appointment(self,*args,**kwargs):
        serializer_class = AppointmentCreateUpdateSerializer(
            data=self.request.data,context={'request': self.request}
        )
        serializer_class.is_valid(raise_exception=True)
        appointment = serializer_class.save(
            clinic = self.clinic,
            # A doctor books only for themselves.
            **({'doctor': self.doctor} if self.doctor else {}),

        )
        return self.get_response_object(
            appointment,
            AppointmentListSerializer,
            context={'request': self.request},
        )

    def update_appointment(self,*args,**kwargs):
        appointment = self.db.get_appointment(appointment_id=kwargs.get('pk'),clinic_id=self.clinic, doctor=self.doctor)
        serializer_class = AppointmentCreateUpdateSerializer(
            instance=appointment,
            data=self.request.data,
            partial=True,
            context={'request': self.request}
        )
        serializer_class.is_valid(raise_exception=True)
        serializer_class.save()
        return self.get_response_object(
            obj=appointment,
            response_serializer_class=AppointmentListSerializer,
            context={'request': self.request}
        )

    def delete_appointment(self,*args,**kwargs):
        appointment = self.db.get_appointment(appointment_id=kwargs.get('pk'),clinic_id=self.clinic, doctor=self.doctor)
        appointment.delete()
        return self.get_response_object(
            context={'request': self.request},
            status_code=status.HTTP_204_NO_CONTENT,
        )