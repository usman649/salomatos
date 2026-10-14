from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.authentication.models import DoctorType, User


@receiver(post_save, sender=User)
def create_default_doctor_type(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    if instance.role != User.Roles.SUPERADMIN:
        return

    DoctorType.objects.get_or_create(
        clinic=instance,
        name='Stomatolog',
    )