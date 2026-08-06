from apps.authentication.api.v1.repositories.users import UserRepository
from apps.core.services import BaseService
from apps.authentication.api.v1.services.user_manager import UserManager
from apps.authentication.api.v1.serializers.users import (
    UserMeSerializer,
    UserLoginSerializer,
    UserUpdateSerializer
)

class UserService(BaseService):
    def __init__(self,request):
        super().__init__(request)
        self.db = UserRepository()

    def me(self,*args,**kwargs):
        return self.get_response_object(
            obj=self.request.user,
            response_serializer_class=UserMeSerializer,
            context={'request':self.request}
        )

    def login(self,*args,**kwargs):
        serializer_class = UserLoginSerializer(
            data=self.request.data,context={'request':self.request}
        )
        serializer_class.is_valid(raise_exception=True)
        user = serializer_class.validated_data.get('user')
        token = UserManager.get_tokens_for_user(user)
        return self.get_response_object(
            obj={
                "result":token,
            },
            context={
                "request":self.request,
            }
        )

    def update(self,*args,**kwargs):
        user = self.db.get_user(user_id=kwargs.get('pk'))
        serializer_class = UserUpdateSerializer(
            instance=user,
            data=self.request.data,
            partial=True,
            context={'request':self.request}
        )
        serializer_class.is_valid(raise_exception=True)
        serializer_class.save()
        return self.get_response_object(
            obj=user,
            response_serializer_class=UserUpdateSerializer,
            context={'request':self.request}
        )
