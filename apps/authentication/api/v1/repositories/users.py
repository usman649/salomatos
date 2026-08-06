from apps.authentication.models import User
from apps.core.exceptions import ObjectNotFoundException

class UserRepository:
    def get_user(self, user_id):
        user = User.objects.filter(id=user_id).first()
        if not user:
            raise ObjectNotFoundException(
                message="User not found",message_key="user_not_found"
            )
        return user

    def get_users(self):
        users = User.objects.all()
        return users