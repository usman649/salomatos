from rest_framework import serializers
from apps.authentication.models import User,DoctorType

class DoctorListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    phone_number = serializers.CharField()
    email = serializers.EmailField()


class DoctorCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'full_name',
            'phone_number',
            'email',
        ]


class DoctorTypeListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class DoctorTypeCreateUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(default='Stomatolog',required=False,allow_null=True)
    class Meta:
        model = DoctorType
        fields = [
            'name',
        ]

    def validate_name(self, value):
        if value is None:
            return 'Stomatolog'
        return value



