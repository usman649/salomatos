import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('config')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat sozlamasi (Har 5 daqiqada tekshirib turish uchun)
app.conf.beat_schedule = {
    'send-appointment-reminders-every-5-minutes': {
        'task': 'apps.core.tasks.send_appointment_reminders',
        'schedule': crontab(minute='*/5'),
    },
}