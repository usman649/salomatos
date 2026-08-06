from apps.clinic.api.v1.repositories.galleries import GalleryRepository
from apps.clinic.api.v1.serializers.galleries import (
    GalleryCreateUpdateSerializer,
    GalleryListSerializer
)
from apps.core.services import BaseService


class GalleryService(BaseService):
    def __init__(self,request):
        super().__init__(request)
        self.db = GalleryRepository()

    def create_gallery(self,*args,**kwargs):
        serializer_class = GalleryCreateUpdateSerializer(
            data=self.request.data,context={'request': self.request},
        )
        serializer_class.is_valid(raise_exception=True)
        gallery = serializer_class.save(clinic = self.request.user)
        return self.get_response_object(
            gallery,
            GalleryListSerializer,
            context={'request': self.request}
        )




