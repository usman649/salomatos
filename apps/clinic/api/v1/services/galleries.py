from apps.clinic.api.v1.repositories.galleries import GalleryRepository
from apps.clinic.api.v1.serializers.galleries import (
    GalleryCreateUpdateSerializer,
    GalleryListSerializer
)
from apps.core.services import BaseService
from rest_framework import status
from apps.core.permissions import get_clinic, own_doctor


class GalleryService(BaseService):
    def __init__(self,request):
        super().__init__(request)
        self.db = GalleryRepository()
        self.clinic = get_clinic(request.user)
        # A doctor works only with their own records; others see the whole clinic.
        self.doctor = own_doctor(request.user)

    def create_gallery(self,*args,**kwargs):
        serializer_class = GalleryCreateUpdateSerializer(
            data=self.request.data,context={'request': self.request},
        )
        serializer_class.is_valid(raise_exception=True)
        gallery = serializer_class.save(clinic = self.clinic)
        return self.get_response_object(
            gallery,
            GalleryListSerializer,
            context={'request': self.request}
        )

    def get_galleries(self, *args, **kwargs):
        gallery = self.db.get_galleries(clinic_id=self.clinic, doctor=self.doctor)
        return self.get_response(
            gallery,
            GalleryListSerializer,
            context={'request': self.request},
            many=True
        )

    def update_gallery(self, *args, **kwargs):
        gallery = self.db.get_gallery(gallery_id=kwargs.get('pk'), clinic_id=self.clinic, doctor=self.doctor)
        serializer_class = GalleryCreateUpdateSerializer(
            instance=gallery,
            data=self.request.data,
            partial=True,
            context={'request': self.request}
        )
        serializer_class.is_valid(raise_exception=True)
        serializer_class.save()
        return self.get_response_object(
            obj=gallery,
            response_serializer_class=GalleryListSerializer,
            context={'request': self.request}
        )

    def delete_gallery(self, *args, **kwargs):
        gallery = self.db.get_gallery(gallery_id=kwargs.get('pk'), clinic_id=self.clinic, doctor=self.doctor)
        gallery.delete()
        return self.get_response_object(
            context={'request': self.request},
            status_code=status.HTTP_204_NO_CONTENT,
        )






