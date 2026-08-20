from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.views import APIView
from apps.core.api.v1.services.telegram import TelegramService
from apps.authentication.api.v1.serializers.users import UserMeSerializer
from apps.clinic.api.v1.serializers.galleries import GalleryListSerializer
from apps.core.api.v1.serializers.recipes import RecipeListSerializer
from apps.calendars.api.v1.serializers.appointments import AppointmentListSerializer


class TelegramPatientListView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'phone_number': openapi.Schema(type=openapi.TYPE_STRING, description="Bemorning telefon raqami"),
                'telegram_chat_id': openapi.Schema(type=openapi.TYPE_STRING, description="Bemorning Telegram ID'si"),
            }
        ),
        responses={200: UserMeSerializer},
        tags=['Telegram'],
        operation_description='Patient Login / Check by Chat ID',
    )
    def post(self, request, *args, **kwargs):
        return TelegramService(request=request).get_telegram_patient(request, *args, **kwargs)

    @swagger_auto_schema(
        responses={200: GalleryListSerializer},
        tags=['Telegram'],
        operation_description='Gallery List',
    )
    def get(self, request, *args, **kwargs):
        return TelegramService(request=request).get_telegram_patient_gallery(request, *args, **kwargs)


class TelegramPatientRecipeListView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        responses={200: RecipeListSerializer(many=True)},
        tags=['Telegram'],
        operation_description='Patient Recipes List',
    )
    def get(self, request, *args, **kwargs):
        return TelegramService(request=request).get_telegram_patient_recipes(request, *args, **kwargs)


class TelegramRecipePDFDownloadView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        tags=['Telegram'],
        operation_description='Download Recipe PDF',
        responses={200: 'PDF File'}
    )
    def get(self, request, recipe_id, *args, **kwargs):
        return TelegramService(request=request).download_recipe_pdf(request, recipe_id=recipe_id)


class TelegramPatientAppointmentListView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'phone_number',
                openapi.IN_QUERY,
                description="Bemorning telefon raqami",
                type=openapi.TYPE_STRING
            ),
        ],
        responses={200: AppointmentListSerializer(many=True)},
        tags=['Telegram'],
        operation_description='Patient Appointments List',
    )
    def get(self, request, *args, **kwargs):
        return TelegramService(request=request).get_telegram_patient_appointments(request, *args, **kwargs)