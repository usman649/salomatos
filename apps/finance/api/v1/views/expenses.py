from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.views import APIView

from apps.core.permissions import IsClinicOwner
from apps.finance.api.v1.serializers.common import VoidSerializer
from apps.finance.api.v1.serializers.expenses import (
    CompensationCreateSerializer,
    CompensationListSerializer,
    DueMonthSerializer,
    ExpenseCreateUpdateSerializer,
    ExpenseListSerializer,
    ExpenseSummarySerializer,
    PayDueSerializer,
    RecurringExpenseCreateUpdateSerializer,
    RecurringExpenseListSerializer,
    SkipDueSerializer,
)
from apps.finance.api.v1.services.expenses import ExpenseService
from apps.finance.models import ExpenseCategory

RANGE_PARAMETERS = [
    openapi.Parameter(
        "from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date", required=True
    ),
    openapi.Parameter(
        "to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date", required=True
    ),
]

MONTH_PARAMETER = openapi.Parameter(
    "month", openapi.IN_QUERY, type=openapi.TYPE_STRING, description="YYYY-MM", required=True
)


class ExpenseCreateListView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        responses={200: ExpenseListSerializer(many=True)},
        tags=["Finance: Expenses"],
        operation_description="Expense journal, newest first, voided entries included",
        manual_parameters=[
            *RANGE_PARAMETERS,
            openapi.Parameter(
                "category",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=ExpenseCategory.values,
            ),
        ],
    )
    def get(self, request, *args, **kwargs):
        return ExpenseService(request=request).get_expenses(*args, **kwargs)

    @swagger_auto_schema(
        request_body=ExpenseCreateUpdateSerializer,
        responses={201: ExpenseListSerializer},
        tags=["Finance: Expenses"],
        operation_description="Expense create",
    )
    def post(self, request, *args, **kwargs):
        return ExpenseService(request=request).create_expense(*args, **kwargs)


class ExpenseUpdateView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        request_body=ExpenseCreateUpdateSerializer,
        responses={200: ExpenseListSerializer},
        tags=["Finance: Expenses"],
        operation_description="Expense update; a voided expense cannot be changed",
    )
    def patch(self, request, *args, **kwargs):
        return ExpenseService(request=request).update_expense(*args, **kwargs)


class ExpenseVoidView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        request_body=VoidSerializer,
        responses={200: ExpenseListSerializer},
        tags=["Finance: Expenses"],
        operation_description="Void an expense: it stays in the journal and leaves every total",
    )
    def post(self, request, *args, **kwargs):
        return ExpenseService(request=request).void_expense(*args, **kwargs)


class ExpenseSummaryView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        responses={200: ExpenseSummarySerializer},
        tags=["Finance: Expenses"],
        operation_description="Expense sums for a period, voided entries excluded",
        manual_parameters=RANGE_PARAMETERS,
    )
    def get(self, request, *args, **kwargs):
        return ExpenseService(request=request).get_summary(*args, **kwargs)


class RecurringExpenseCreateListView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        responses={200: RecurringExpenseListSerializer(many=True)},
        tags=["Finance: Recurring expenses"],
        operation_description="Recurring bills",
    )
    def get(self, request, *args, **kwargs):
        return ExpenseService(request=request).get_recurring_expenses(*args, **kwargs)

    @swagger_auto_schema(
        request_body=RecurringExpenseCreateUpdateSerializer,
        responses={201: RecurringExpenseListSerializer},
        tags=["Finance: Recurring expenses"],
        operation_description="Recurring bill create; due from the current month",
    )
    def post(self, request, *args, **kwargs):
        return ExpenseService(request=request).create_recurring_expense(*args, **kwargs)


class RecurringExpenseUpdateView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        request_body=RecurringExpenseCreateUpdateSerializer,
        responses={200: RecurringExpenseListSerializer},
        tags=["Finance: Recurring expenses"],
        operation_description="Recurring bill update; `is_active: false` pauses it",
    )
    def patch(self, request, *args, **kwargs):
        return ExpenseService(request=request).update_recurring_expense(*args, **kwargs)


class RecurringExpenseDueView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        responses={200: DueMonthSerializer},
        tags=["Finance: Recurring expenses"],
        operation_description="One month of recurring bills and whether each is paid",
        manual_parameters=[MONTH_PARAMETER],
    )
    def get(self, request, *args, **kwargs):
        return ExpenseService(request=request).get_due_month(*args, **kwargs)


class RecurringExpensePayView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        request_body=PayDueSerializer,
        responses={201: ExpenseListSerializer},
        tags=["Finance: Recurring expenses"],
        operation_description="Pay one month of a bill: records it as a normal expense",
    )
    def post(self, request, *args, **kwargs):
        return ExpenseService(request=request).pay_due(*args, **kwargs)


class RecurringExpenseSkipView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        request_body=SkipDueSerializer,
        responses={204: "Skipped"},
        tags=["Finance: Recurring expenses"],
        operation_description="Skip one month of a bill; nothing is posted",
    )
    def post(self, request, *args, **kwargs):
        return ExpenseService(request=request).skip_due(*args, **kwargs)


class DoctorCompensationView(APIView):
    permission_classes = [IsClinicOwner]

    @swagger_auto_schema(
        responses={200: CompensationListSerializer(many=True)},
        tags=["Finance: Doctor pay"],
        operation_description="A doctor's pay terms, newest first",
    )
    def get(self, request, *args, **kwargs):
        return ExpenseService(request=request).get_compensations(*args, **kwargs)

    @swagger_auto_schema(
        request_body=CompensationCreateSerializer,
        responses={201: CompensationListSerializer},
        tags=["Finance: Doctor pay"],
        operation_description="New pay terms from a month on; earlier terms are kept",
    )
    def post(self, request, *args, **kwargs):
        return ExpenseService(request=request).create_compensation(*args, **kwargs)
