from django.db import models

from apps.core.models import CreatedUpdatedAbstractModel


class TreatmentCompletion(CreatedUpdatedAbstractModel):
    """
    The day a treatment was marked completed. `Treatment` has no such date,
    so it is recorded here, beside it, when the status changes (see
    `signals.py`). Treatments completed before this existed, or created
    already completed in bulk, have no row and count on their `start_date`.
    """

    treatment = models.OneToOneField(
        "clinic.Treatment",
        on_delete=models.CASCADE,
        related_name="completion",
    )
    completed_on = models.DateField()

    def __str__(self):
        return f"{self.treatment_id} ({self.completed_on})"
