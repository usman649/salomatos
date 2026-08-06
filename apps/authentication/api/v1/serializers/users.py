from rest_framework import serializers
from apps.authentication.models import User
from apps.core.exceptions import ValidationError


class UserLoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def validate(self, attrs):
        user = User.objects.authenticate(
            username=attrs.get("username"), password=attrs.get("password")
        )
        if not user:
            raise ValidationError(
                message="Invalid username or password",
                message_key="invalid_username_or_password",
            )
        attrs["user"] = user
        return attrs



class UserMeSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    specialty = serializers.CharField()
    phone_number = serializers.CharField()
    email = serializers.EmailField()
    experience = serializers.IntegerField()
    biography = serializers.CharField()
    image = serializers.ImageField()
    role = serializers.CharField()

class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            'full_name',
            'specialty',
            'phone_number',
            'email',
            'experience',
            'biography',
            'image'
        )





