from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_yasg.utils import swagger_auto_schema
from drf_yasg  import openapi
from rest_framework.views import APIView
from apps.clinic.api.v1.serializers.galleries import (
    GalleryListSerializer,
    GalleryCreateUpdateSerializer,
)
from apps.clinic.api.v1.services.galleries import GalleryService

class GalleryCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=GalleryCreateUpdateSerializer,
        responses={200: GalleryListSerializer},
        tags=['Gallery'],
        operation_description='Gallery Create',
    )
    def post(self,request,*args,**kwargs):
        return GalleryService(request=request).create_gallery(*args,**kwargs)





