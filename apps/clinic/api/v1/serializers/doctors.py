from rest_framework import serializers
from apps.authentication.models import User,DoctorType

class DoctorListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.CharField()
    phone_number = serializers.CharField()
    email = serializers.EmailField()
    doctor_type = serializers.CharField()



class DoctorCreateUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = [
            'username',
            'password',
            'full_name',
            'phone_number',
            'email',
            'doctor_type',
        ]
        extra_kwargs = {
            'username': {'required': True, 'allow_null': False, 'allow_blank': False},
        }


    def validate_doctor_type(self, value):
        request = self.context.get('request')
        if value and request and value.clinic_id != request.user.id:
            raise serializers.ValidationError("Bu doktor turi sizning klinikangizga tegishli emas.")
        return value

    def validate(self, attrs):
        # Yaratishda parol majburiy, yangilashda ixtiyoriy
        if self.instance is None and not attrs.get('password'):
            raise serializers.ValidationError({'password': 'Bu maydon majburiy.'})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class DoctorTypeListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class DoctorTypeCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorType
        fields = [
            'name',
        ]




