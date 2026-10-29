from django.db.models import Count, F, Min, Q
from django.db.models.functions import Coalesce, ExtractHour, ExtractIsoWeekDay

from apps.authentication.models import User
from apps.calendars.models import Appointment
from apps.clinic.models import Treatment

# Treatments completed before `completed_date` existed have none; they count
# on the day they started, the only date they have.
COMPLETED_ON = Coalesce("completed_date", "start_date")


class StatisticsRepository:
    """
    Counts only: no names of patients, no phones, no money. Every query is
    scoped to one clinic and, for a doctor's own view, to one doctor.
    """

    def __init__(self, clinic_id, doctor_id=None):
        self.clinic_id = clinic_id
        self.doctor_id = doctor_id

    def _appointments(self):
        queryset = Appointment.objects.filter(clinic=self.clinic_id)
        if self.doctor_id is not None:
            queryset = queryset.filter(doctor=self.doctor_id)
        return queryset

    def _treatments(self):
        queryset = Treatment.objects.filter(clinic=self.clinic_id)
        if self.doctor_id is not None:
            queryset = queryset.filter(doctor=self.doctor_id)
        return queryset

    def _completed_treatments(self, start, end):
        return (
            self._treatments()
            .filter(status=Treatment.Status.COMPLETED)
            .annotate(completed_on=COMPLETED_ON)
            .filter(completed_on__range=(start, end))
        )

    # Appointments

    def appointment_counts(self, start, end):
        return self._appointments().filter(date__range=(start, end)).aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status=Appointment.Status.COMPLETED)),
        )

    def appointments_by_date(self, start, end):
        rows = (
            self._appointments()
            .filter(date__range=(start, end))
            .values("date")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(status=Appointment.Status.COMPLETED)),
            )
            .order_by()
        )
        return {row["date"]: {"total": row["total"], "completed": row["completed"]} for row in rows}

    def appointments_by_doctor(self, start, end):
        rows = (
            self._appointments()
            .filter(date__range=(start, end))
            .values("doctor_id")
            .annotate(count=Count("id"))
            .order_by()
        )
        return {row["doctor_id"]: row["count"] for row in rows}

    def busy_hours(self, start, end):
        rows = (
            self._appointments()
            .filter(date__range=(start, end))
            .annotate(weekday=ExtractIsoWeekDay("date"), hour=ExtractHour("time"))
            .values("weekday", "hour")
            .annotate(appointments=Count("id"))
            .order_by("weekday", "hour")
        )
        return list(rows)

    # Patients

    def visiting_patients(self, start, end):
        """`(new, returning)`: patients seen in the range, by whether it was their first visit."""
        seen = (
            self._appointments()
            .filter(date__range=(start, end), patient__isnull=False)
            .values("patient_id")
            .distinct()
        )
        firsts = (
            self._appointments()
            .filter(patient_id__in=seen)
            .values("patient_id")
            .annotate(first=Min("date"))
            .order_by()
        )
        new = returning = 0
        for row in firsts:
            if row["first"] >= start:
                new += 1
            else:
                returning += 1
        return new, returning

    # Treatments

    def treatments_started(self, start, end):
        return self._treatments().filter(start_date__range=(start, end)).count()

    def treatments_completed(self, start, end):
        return self._completed_treatments(start, end).count()

    def treatments_in_progress(self, as_of):
        """Open at the end of `as_of`: started by then and not completed by then."""
        return (
            self._treatments()
            .filter(start_date__lte=as_of)
            .annotate(completed_on=COMPLETED_ON)
            .exclude(status=Treatment.Status.COMPLETED, completed_on__lte=as_of)
            .count()
        )

    def completed_by_date(self, start, end):
        rows = (
            self._completed_treatments(start, end)
            .values("completed_on")
            .annotate(count=Count("id"))
            .order_by()
        )
        return {row["completed_on"]: {"completed": row["count"]} for row in rows}

    def completed_by_doctor(self, start, end):
        rows = (
            self._completed_treatments(start, end)
            .filter(doctor__isnull=False)
            .values("doctor_id")
            .annotate(count=Count("id"))
            .order_by()
        )
        return {row["doctor_id"]: row["count"] for row in rows}

    def completed_by_treatment_type(self, start, end):
        rows = (
            self._completed_treatments(start, end)
            .filter(treatment_type__isnull=False)
            .values("treatment_type_id", treatment_type_name=F("treatment_type__name"))
            .annotate(count=Count("id"))
            .order_by("-count", "treatment_type_name")
        )
        return [
            {
                "treatment_type_id": row["treatment_type_id"],
                "treatment_type": row["treatment_type_name"],
                "count": row["count"],
            }
            for row in rows
        ]

    def completed_by_tooth(self, start, end):
        rows = (
            self._completed_treatments(start, end)
            .filter(tooth_number__isnull=False)
            .values("tooth_number")
            .annotate(count=Count("id"))
            .order_by()
        )
        return {row["tooth_number"]: row["count"] for row in rows}

    def doctors(self):
        queryset = User.objects.filter(clinic=self.clinic_id, role=User.Roles.DOCTOR)
        if self.doctor_id is not None:
            queryset = queryset.filter(id=self.doctor_id)
        return list(queryset.order_by("full_name", "id"))
