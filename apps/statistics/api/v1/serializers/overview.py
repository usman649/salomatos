from rest_framework import serializers


class StatsTotalsSerializer(serializers.Serializer):
    appointments = serializers.IntegerField()
    appointments_completed = serializers.IntegerField()
    new_patients = serializers.IntegerField()
    returning_patients = serializers.IntegerField()
    treatments_completed = serializers.IntegerField()
    treatments_started = serializers.IntegerField()
    treatments_in_progress = serializers.IntegerField()


class AppointmentsPointSerializer(serializers.Serializer):
    start = serializers.DateField()
    total = serializers.IntegerField()
    completed = serializers.IntegerField()


class TreatmentsPointSerializer(serializers.Serializer):
    start = serializers.DateField()
    completed = serializers.IntegerField()


class DoctorLoadSerializer(serializers.Serializer):
    doctor_id = serializers.IntegerField()
    doctor = serializers.CharField()
    appointments = serializers.IntegerField()
    treatments_completed = serializers.IntegerField()


class TreatmentTypeCountSerializer(serializers.Serializer):
    treatment_type_id = serializers.IntegerField()
    treatment_type = serializers.CharField()
    count = serializers.IntegerField()


class BusyHourSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(help_text="ISO weekday, 1 = Monday")
    hour = serializers.IntegerField(help_text="Clinic-time hour, 0-23")
    appointments = serializers.IntegerField()


class ToothCountSerializer(serializers.Serializer):
    tooth = serializers.CharField(help_text="FDI number, 11-48")
    count = serializers.IntegerField()


class StatsOverviewSerializer(serializers.Serializer):
    to = serializers.DateField()
    bucket = serializers.CharField()
    totals = StatsTotalsSerializer()
    previous_totals = StatsTotalsSerializer(allow_null=True)
    appointments_series = AppointmentsPointSerializer(many=True)
    treatments_series = TreatmentsPointSerializer(many=True)
    doctors = DoctorLoadSerializer(many=True)
    treatment_types = TreatmentTypeCountSerializer(many=True)
    busy_hours = BusyHourSerializer(many=True)
    teeth = ToothCountSerializer(many=True)

    def get_fields(self):
        # `from` is a Python keyword, so it cannot be declared above.
        fields = super().get_fields()
        return {"from": serializers.DateField(), **fields}
