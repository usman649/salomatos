from rest_framework.permissions import IsAuthenticated, AllowAny
from drf_yasg.utils import swagger_auto_schema
from apps.authentication.api.v1.serializers.users import UserLoginSerializer,UserMeSerializer,UserUpdateSerializer
from apps.authentication.api.v1.services.users import UserService
from rest_framework.views import APIView
from apps.core.services import ServiceDefaultResponseSerializer


class UserMeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        responses={200: UserMeSerializer},
        tags=['User'],
        operation_description="User me information",
    )

    def get(self,request,*args,**kwargs):
        return UserService(request=request).me()


class UserLoginView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=UserLoginSerializer,
        responses={200: ServiceDefaultResponseSerializer},
        tags=['User'],
        operation_description="User login information",
    )
    def post(self,request,*args,**kwargs):
        return UserService(request=request).login()

class UserUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=UserUpdateSerializer,
        responses={200: ServiceDefaultResponseSerializer},
        tags=['User'],
    )
    def patch(self,request,*args,**kwargs):
        return UserService(request=request).update(*args,**kwargs)






