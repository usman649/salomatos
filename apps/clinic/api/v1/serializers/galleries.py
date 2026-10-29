from rest_framework import serializers
from apps.authentication.models import Gallery
from apps.core.permissions import limit_to_clinic


class GalleryListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    image = serializers.ImageField()
    created_at = serializers.DateTimeField()

class GalleryCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gallery
        fields = [
            'id',
            'clinic',
            'user',
            'image',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        limit_to_clinic(self)
