from apps.clinic.api.v1.repositories.clinics import ClinicRepository
from apps.clinic.api.v1.serializers.clinics import (
    ClinicCreateUpdateSerializer,
    ClinicListSerializer,
)
from apps.core.services import BaseService
from rest_framework import status


class ClinicService(BaseService):
    def __init__(self,request):
        super().__init__(request)
        self.db = ClinicRepository()

    def get_clinics(self,*args,**kwargs):
        clinics = self.db.get_clinics(user=self.request.user)
        return self.get_response(
            clinics,
            ClinicListSerializer,
            context={'request': self.request},
            many=True
        )

    def create_clinic(self, *args, **kwargs):
        serializer_class = ClinicCreateUpdateSerializer(
            data=self.request.data,
            context={'request': self.request}
        )
        serializer_class.is_valid(raise_exception=True)

        clinic = serializer_class.save(
            admin = self.request.user,
        )
        return self.get_response_object(
            clinic,
            ClinicListSerializer,
            context={'request': self.request},
        )

    def update_clinic(self,*args,**kwargs):
        clinic = self.db.get_clinic(clinic_id=kwargs.get('pk'))
        serializer_class = ClinicCreateUpdateSerializer(
            instance=clinic,
            data=self.request.data,
            partial=True,
            context={'request': self.request}
        )
        serializer_class.is_valid(raise_exception=True)
        serializer_class.save()
        return self.get_response_object(
            obj=clinic,
            response_serializer_class=ClinicListSerializer,
            context={'request': self.request}
        )

    def delete_clinic(self,*args,**kwargs):
        clinic = self.db.get_clinic(clinic_id=kwargs.get('pk'))
        clinic.delete()
        return self.get_response_object(
            context={'request': self.request},
            status_code=status.HTTP_204_NO_CONTENT,
        )




