from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView

from apps.core.permissions import IsClinicOwner
from apps.finance.api.v1.serializers.common import VoidSerializer
from apps.finance.api.v1.serializers.payments import (
    PaymentCreateSerializer,
    PaymentListSerializer,
)
from apps.finance.api.v1.services.payments import PaymentService
from apps.finance.permissions import CanRecordPayments


class PaymentCreateListView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [CanRecordPayments()]
        return [IsClinicOwner()]

    @swagger_auto_schema(
        responses={200: PaymentListSerializer(many=True)},
        tags=["Finance: Payments"],
        operation_description="Payment journal, newest first, voided payments included",
        manual_parameters=[
            openapi.Parameter("from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"),
            openapi.Parameter("to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"),
            openapi.Parameter("patient_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("treatment_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter(
                "method",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["cash", "card", "click", "payme", "transfer"],
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        return PaymentService(request=request).get_payments(*args, **kwargs)

    @swagger_auto_schema(
        request_body=PaymentCreateSerializer,
        responses={201: PaymentListSerializer},
        tags=["Finance: Payments"],
        operation_description="Record a payment for a treatment; raises its total_paid",
    )
    def post(self, request, *args, **kwargs):
        return PaymentService(request=request).create_payment(*args, **kwargs)


class PaymentVoidView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        request_body=VoidSerializer,
        responses={200: PaymentListSerializer},
        tags=["Finance: Payments"],
        operation_description="Void a payment; lowers its treatment's total_paid",
    )
    def post(self, request, *args, **kwargs):
        return PaymentService(request=request).void_payment(*args, **kwargs)
