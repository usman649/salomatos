from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView

from apps.core.permissions import IsClinicDoctor, IsClinicOwner
from apps.statistics.api.v1.serializers.overview import StatsOverviewSerializer
from apps.statistics.api.v1.services.overview import StatisticsService

RANGE_PARAMETERS = [
    openapi.Parameter(
        "from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date", required=True
    ),
    openapi.Parameter(
        "to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date", required=True
    ),
]


class StatisticsOverviewView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        responses={200: StatsOverviewSerializer},
        tags=["Statistics"],
        operation_description="The clinic's activity for a period: counts only",
        manual_parameters=RANGE_PARAMETERS,
    )
    def get(self, request, *args, **kwargs):
        return StatisticsService(request=request).get_overview(*args, **kwargs)


class StatisticsMyOverviewView(APIView):
    permission_classes = [IsClinicDoctor]

    @swagger_auto_schema(
        responses={200: StatsOverviewSerializer},
        tags=["Statistics"],
        operation_description="The same report for the signed-in doctor's own work",
        manual_parameters=RANGE_PARAMETERS,
    )
    def get(self, request, *args, **kwargs):
        return StatisticsService(request=request, own_only=True).get_overview(*args, **kwargs)
