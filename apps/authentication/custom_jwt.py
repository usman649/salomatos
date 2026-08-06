from django.core.exceptions import ObjectDoesNotExist
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class CustomJwtAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        from apps.core.exceptions import BaseUnauthorizedException

        user_id = validated_token.get("user_id")
        if not user_id:
            raise InvalidToken("Token contained no recognizable user identification")

        try:
            from apps.authentication.models import User

            return User.objects.get(id=user_id)
        except ObjectDoesNotExist as err:
            raise BaseUnauthorizedException(
                message="User associated with this token does not exist."
            ) from err
