from apps.clinic.api.v1.repositories.patients import PatientRepository
from apps.clinic.api.v1.serializers.patients import (
    PatientListSerializer,
    PatientCreateUpdateSerializer,
    PatientDetailSerializer,
)
from apps.core.services import BaseService
from rest_framework import status
from django.db import transaction
from django.utils import timezone
from apps.calendars.models import Appointment
from apps.core.permissions import get_clinic, own_doctor
from apps.clinic.api.v1.filters.patients import PatientFilter
from apps.authentication.models import User
from apps.core.exceptions import (
ObjectNotFoundException,
PermissionDeniedException
)



class PatientService(BaseService):
    def __init__(self,request):
        super().__init__(request)
        self.db = PatientRepository()
        self.clinic = get_clinic(request.user)
        # A doctor works only with their own records; others see the whole clinic.
        self.doctor = own_doctor(request.user)

    def get_patients(self,*args,**kwargs):
        unfiltered_patients = self.db.get_patients(clinic_id=self.clinic, doctor=self.doctor)
        filtered_patients = PatientFilter(
            data=self.request.query_params,
            queryset=unfiltered_patients,
            request=self.request,
        ).qs

        return self.get_paginated_response(
            filtered_patients,
            PatientListSerializer,
            context={'request': self.request},

        )

    def create_patient(self,*args,**kwargs):
        serializer_class = PatientCreateUpdateSerializer(
            data=self.request.data,context={'request': self.request},
        )
        serializer_class.is_valid(raise_exception=True)
        patient = serializer_class.save(
            role=User.Roles.PATIENT,
            clinic=self.clinic,

        )
        return self.get_response_object(
            patient,
            PatientListSerializer,
            context={'request': self.request}
        )

    def get_patient(self,*args,**kwargs):
        patient = self.db.get_patient(user_id=kwargs.get('pk'),clinic_id=self.clinic, doctor=self.doctor)
        return self.get_response(
            patient,
            PatientDetailSerializer,
            context={'request': self.request}
        )

    def update_patient(self, *args, **kwargs):
        patient = self.db.get_patient(user_id=kwargs.get('pk'),clinic_id=self.clinic, doctor=self.doctor)
        serializer_class = PatientCreateUpdateSerializer(
            instance=patient,
            data=self.request.data,
            partial=True,
            context={'request': self.request}
        )
        serializer_class.is_valid(raise_exception=True)
        serializer_class.save()
        return self.get_response_object(
            obj=patient,
            response_serializer_class=PatientListSerializer,
            context={'request': self.request}
        )

    def delete_patient(self, *args, **kwargs):
        patient = self.db.get_patient(user_id=kwargs.get('pk'),clinic_id=self.clinic)
        # Archive instead of deleting: treatments and recipes keep their patient,
        # so medical history and finance totals stay intact and the record can be restored.
        with transaction.atomic():
            patient.is_active = False
            patient.save(update_fields=['is_active'])
            # Upcoming visits would keep holding calendar slots and still trigger Telegram reminders.
            Appointment.objects.filter(
                patient=patient,
                clinic=self.clinic,
                status=Appointment.Status.IN_PROGRESS,
                date__gte=timezone.localdate(),
            ).delete()
        return self.get_response_object(
            context={'request': self.request},
            status_code=status.HTTP_204_NO_CONTENT,
        )
