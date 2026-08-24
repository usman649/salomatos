from rest_framework import status
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML

from apps.core.api.v1.repositories.telegram import TelegramRepository
from apps.core.services import BaseService
from apps.authentication.api.v1.serializers.users import UserMeSerializer
from apps.clinic.api.v1.serializers.galleries import GalleryListSerializer
from apps.core.api.v1.serializers.recipes import RecipeListSerializer
from apps.core.exceptions import ObjectNotFoundException
from apps.calendars.api.v1.serializers.appointments import AppointmentListSerializer

class TelegramService(BaseService):
    def __init__(self, request):
        super().__init__(request)
        self.db = TelegramRepository()

    def get_telegram_patient(self, request):
        chat_id = request.data.get('telegram_chat_id')
        phone_number = request.data.get('phone_number')

        if chat_id and not phone_number:
            patient = self.db.get_telegram_patient_by_chat_id(chat_id)
            if not patient:
                raise ObjectNotFoundException(
                    message="Patient not found by chat ID.",
                    message_key="patient_not_found",
                )
            return self.get_response_object(
                patient,
                UserMeSerializer,
                context={'request': request}
            )

        patient = self.db.get_telegram_patient(phone_number=phone_number)

        if chat_id:
            self.db.link_chat_id_to_patient(patient, chat_id)

        return self.get_response_object(
            patient,
            UserMeSerializer,
            context={'request': request}
        )

    def get_telegram_patient_gallery(self, request):
        gallery = self.db.get_telegram_patient_gallery(phone_number=request.data.get('phone_number'))
        return self.get_response(
            gallery,
            GalleryListSerializer,
            context={'request': request},
            many=True
        )

    def get_telegram_patient_recipes(self, request):
        phone_number = request.query_params.get('phone_number')

        recipes = self.db.get_telegram_patient_recipes(phone_number=phone_number)

        return self.get_response(
            recipes,
            RecipeListSerializer,
            context={'request': request},
            many=True
        )

    def download_recipe_pdf(self, request, recipe_id):
        recipe = self.db.get_recipe_by_id(recipe_id=recipe_id)

        context = {
            'recipe': recipe,
            'medicines': recipe.medicines.all(),
        }

        html_string = render_to_string('recipe_pdf.html', context)
        html = HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()

        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Tibbiy_Retsept_{recipe.id}.pdf"'

        return response

    def get_telegram_patient_appointments(self, request):
        phone_number = request.query_params.get('phone_number')

        appointments = self.db.get_telegram_patient_appointments(phone_number=phone_number)

        return self.get_response(
            appointments,
            AppointmentListSerializer,
            context={'request': request},
            many=True
        )
