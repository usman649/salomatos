from apps.core.permissions import get_clinic
from apps.core.reporting import parse_range
from apps.core.services import BaseService
from apps.statistics.api.v1.repositories.overview import StatisticsRepository
from apps.statistics.api.v1.serializers.overview import StatsOverviewSerializer

# The 32 permanent teeth in FDI notation: quadrant 1-4, position 1-8.
PERMANENT_TEETH = [quadrant * 10 + position for quadrant in range(1, 5) for position in range(1, 9)]


class StatisticsService(BaseService):
    def __init__(self, request, own_only=False):
        super().__init__(request)
        # A doctor's own view is the same report, narrowed to their own work.
        doctor_id = request.user.id if own_only else None
        self.db = StatisticsRepository(clinic_id=get_clinic(request.user), doctor_id=doctor_id)

    def _totals(self, report_range):
        start, end = report_range.start, report_range.end
        appointments = self.db.appointment_counts(start, end)
        new_patients, returning_patients = self.db.visiting_patients(start, end)
        return {
            "appointments": appointments["total"],
            "appointments_completed": appointments["completed"],
            "new_patients": new_patients,
            "returning_patients": returning_patients,
            "treatments_completed": self.db.treatments_completed(start, end),
            "treatments_started": self.db.treatments_started(start, end),
            "treatments_in_progress": self.db.treatments_in_progress(end),
        }

    def get_overview(self, *args, **kwargs):
        report_range = parse_range(self.request.query_params)
        start, end = report_range.start, report_range.end

        appointments_by_doctor = self.db.appointments_by_doctor(start, end)
        completed_by_doctor = self.db.completed_by_doctor(start, end)
        teeth = self.db.completed_by_tooth(start, end)

        overview = {
            "from": start,
            "to": end,
            "bucket": report_range.bucket,
            "totals": self._totals(report_range),
            "previous_totals": self._totals(report_range.previous()),
            "appointments_series": report_range.series(
                self.db.appointments_by_date(start, end), ["total", "completed"]
            ),
            "treatments_series": report_range.series(
                self.db.completed_by_date(start, end), ["completed"]
            ),
            "doctors": sorted(
                (
                    {
                        "doctor_id": doctor.id,
                        "doctor": doctor.full_name,
                        "appointments": appointments_by_doctor.get(doctor.id, 0),
                        "treatments_completed": completed_by_doctor.get(doctor.id, 0),
                    }
                    for doctor in self.db.doctors()
                ),
                key=lambda row: (-row["appointments"], row["doctor"]),
            ),
            "treatment_types": self.db.completed_by_treatment_type(start, end),
            "busy_hours": self.db.busy_hours(start, end),
            "teeth": [
                {"tooth": str(tooth), "count": teeth.get(tooth, 0)} for tooth in PERMANENT_TEETH
            ],
        }
        return self.get_response_object(overview, StatsOverviewSerializer)
