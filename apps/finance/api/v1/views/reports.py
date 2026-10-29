from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView

from apps.core.permissions import IsClinicDoctor, IsClinicOwner
from apps.finance.api.v1.serializers.reports import (
    DoctorMonthSerializer,
    FinanceOverviewSerializer,
    PayrollSerializer,
)
from apps.finance.api.v1.services.reports import FinanceReportService
from apps.finance.api.v1.views.expenses import MONTH_PARAMETER, RANGE_PARAMETERS


class FinanceOverviewView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        responses={200: FinanceOverviewSerializer},
        tags=["Finance: Reports"],
        operation_description="Billed, collected and owed for a period, with breakdowns",
        manual_parameters=RANGE_PARAMETERS,
    )
    def get(self, request, *args, **kwargs):
        return FinanceReportService(request=request).get_overview(*args, **kwargs)


class PayrollView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        responses={200: PayrollSerializer},
        tags=["Finance: Doctor pay"],
        operation_description="Every doctor's month: earned, paid and still owed",
        manual_parameters=[MONTH_PARAMETER],
    )
    def get(self, request, *args, **kwargs):
        return FinanceReportService(request=request).get_payroll(*args, **kwargs)


class DoctorMyMonthView(APIView):
    permission_classes = [IsClinicDoctor]

    @swagger_auto_schema(
        responses={200: DoctorMonthSerializer},
        tags=["Finance: Doctor pay"],
        operation_description="The signed-in doctor's own month; defaults to the current one",
        manual_parameters=[
            openapi.Parameter(
                "month", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="YYYY-MM"
            )
        ],
    )
    def get(self, request, *args, **kwargs):
        return FinanceReportService(request=request).get_my_month(*args, **kwargs)
