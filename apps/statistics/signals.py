from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.clinic.models import Treatment
from apps.core.reporting import clinic_today
from apps.statistics.models import TreatmentCompletion


@receiver(pre_save, sender=Treatment)
def remember_previous_status(sender, instance, raw=False, **kwargs):
    if raw or instance.pk is None:
        instance._previous_status = None
        return
    instance._previous_status = (
        Treatment.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )


@receiver(post_save, sender=Treatment)
def record_completion(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    previous = getattr(instance, "_previous_status", None)
    completed = Treatment.Status.COMPLETED
    if instance.status == completed and (created or previous != completed):
        TreatmentCompletion.objects.update_or_create(
            treatment=instance, defaults={"completed_on": clinic_today()}
        )
    elif instance.status != completed and previous == completed:
        TreatmentCompletion.objects.filter(treatment=instance).delete()
