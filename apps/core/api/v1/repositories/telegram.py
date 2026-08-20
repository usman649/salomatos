from apps.core.exceptions import ObjectNotFoundException
from apps.authentication.models import User
from apps.authentication.models import Gallery
from apps.core.models import Recipe
from django.utils import timezone
from apps.calendars.models import Appointment


class TelegramRepository():
    def get_telegram_patient_by_chat_id(self, chat_id):
        if not chat_id:
            return None

        patient = User.objects.filter(
            telegram_chat_id=chat_id,
            role=User.Roles.PATIENT,
        ).first()
        return patient

    def get_telegram_patient(self, phone_number):
        if not phone_number:
            raise ObjectNotFoundException(
                message="Phone number not found.",
                message_key="phone_not_found",
            )
        patient = User.objects.filter(
            phone_number=phone_number,
            role=User.Roles.PATIENT,
        ).first()

        if not patient:
            raise ObjectNotFoundException(
                message="Patient not found.",
                message_key="patient_not_found",
            )
        return patient

    def link_chat_id_to_patient(self, patient, chat_id):
        if chat_id and patient.telegram_chat_id != str(chat_id):
            patient.telegram_chat_id = str(chat_id)
            patient.save(update_fields=['telegram_chat_id', 'updated_at'])
        return patient

    def get_telegram_patient_gallery(self, phone_number):
        patient = self.get_telegram_patient(phone_number=phone_number)
        gallery = Gallery.objects.filter(user=patient)
        return gallery

    def get_telegram_patient_recipes(self, phone_number):
        patient = self.get_telegram_patient(phone_number=phone_number)

        recipes = Recipe.objects.filter(patient=patient).prefetch_related(
            'medicines', 'doctor', 'clinic'
        )
        return recipes

    def get_recipe_by_id(self, recipe_id):
        recipe = Recipe.objects.filter(id=recipe_id).prefetch_related(
            'medicines', 'doctor', 'patient', 'clinic'
        ).first()

        if not recipe:
            raise ObjectNotFoundException(
                message="Recipe not found.",
                message_key="recipe_not_found",
            )
        return recipe

    def get_telegram_patient_appointments(self, phone_number):
        # 1. Avval siz yozgan tayyor funksiya orqali bemorni topib olamiz
        patient = self.get_telegram_patient(phone_number=phone_number)

        now = timezone.localtime(timezone.now())

        # 2. Bemorga tegishli faol va bugungi/kelajakdagi qabullarni olamiz
        appointments = Appointment.objects.filter(
            patient=patient,
            date__gte=now.date(),
            status=Appointment.Status.IN_PROGRESS
        ).select_related('clinic', 'doctor').order_by('date', 'time')

        return appointments