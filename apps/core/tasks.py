import os
import requests
from datetime import timedelta
from dotenv import load_dotenv

from celery import shared_task
from django.utils import timezone
from apps.calendars.models import Appointment

load_dotenv()

@shared_task
def send_appointment_reminders():
    now = timezone.localtime(timezone.now())

    current_time = now.time()
    max_reminder_time = (now + timedelta(hours=2, minutes=5)).time()

    appointments = Appointment.objects.filter(
        date=now.date(),
        time__gte=current_time,
        time__lte=max_reminder_time,
        is_reminded=False,
        status=Appointment.Status.IN_PROGRESS
    ).select_related('patient', 'doctor', 'clinic')

    bot_token = os.getenv("BOT_TOKEN")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    sent_count = 0

    for app in appointments:
        chat_id = app.patient.telegram_chat_id

        if chat_id:
            clinic_name = app.clinic.full_name if app.clinic else "Klinika"
            time_str = app.time.strftime('%H:%M')

            text = (
                f"🔔 **Eslatma!**\n\n"
                f"Hurmatli {app.patient.full_name}, sizning qabulingizga **2 soat** vaqt qoldi.\n\n"
                f"🏥 **Klinika:** {clinic_name}\n"
                f"👨‍⚕️ **Shifokor:** {app.doctor.full_name}\n"
                f"⏰ **Vaqti:** {time_str}\n\n"
                f"Iltimos, belgilangan vaqtda kelishingizni so'raymiz."
            )

            payload = {
                "chat_id": str(chat_id),
                "text": text,
                "parse_mode": "Markdown"
            }

            try:
                response = requests.post(url, json=payload, timeout=5)
                if response.status_code == 200:
                    app.is_reminded = True
                    app.save(update_fields=['is_reminded'])
                    sent_count += 1
                else:
                    print(f"Xabar yuborishda xato: {response.text}")
            except Exception as e:
                print(f"Telegram bilan ulanishda xato: {e}")

    return f"{sent_count} ta bemorga eslatma yuborildi."