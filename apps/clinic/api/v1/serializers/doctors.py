from rest_framework import serializers
from apps.authentication.models import User

class DoctorListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    specialty = serializers.CharField()
    phone_number = serializers.CharField()
    email = serializers.EmailField()


class DoctorCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'full_name',
            'specialty',
            'phone_number',
            'email',
        ]


