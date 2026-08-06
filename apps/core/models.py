from django.db import models

class CreatedUpdatedAbstractModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True,null=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']


class Recipe(CreatedUpdatedAbstractModel):
    clinic = models.ForeignKey(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='clinic_recipes',
        limit_choices_to={'role':'superadmin'},
        null=True,
    )
    patient = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        related_name='patient_recipes',
        limit_choices_to={'role': 'patient'},
        null = True,
    )
    doctor = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        related_name='doctor_recipes',
        limit_choices_to={'role': 'doctor'},
        null = True,
    )
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.notes

class Medicine(CreatedUpdatedAbstractModel):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name='medicines',
    )
    name = models.CharField(max_length=255)
    dose = models.PositiveIntegerField()
    type = models.CharField(max_length=255)
    frequency = models.CharField(max_length=255)
    duration = models.PositiveIntegerField()
    meal = models.CharField(max_length=255)
    minutes = models.PositiveIntegerField()


    def __str__(self):
        return self.name

