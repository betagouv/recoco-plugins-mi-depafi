from django.urls import reverse
from rest_framework import serializers

from .models import Realisation, RealisationLike, RealisationNode


class RealisationNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RealisationNode
        fields = (
            "position",
            "realisation_id",
            "text",
            "title",
            "description",
            "photos",
            "like_count",
            "user_liked",
            "like_toggle_url",
            "detail_url",
        )

    realisation_id = serializers.PrimaryKeyRelatedField(
        source="realisation",
        queryset=Realisation.objects.all(),
    )
    text = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    user_liked = serializers.SerializerMethodField()
    like_toggle_url = serializers.SerializerMethodField()
    detail_url = serializers.SerializerMethodField()

    def _get_realisation(self, obj):
        return obj.realisation

    def get_text(self, obj):
        return f"Réalisation — {obj.realisation.resource.title}"

    def get_title(self, obj):
        return obj.realisation.resource.title

    def get_description(self, obj):
        return obj.realisation.description

    def get_photos(self, obj):
        request = self.context.get("request")
        photos = obj.realisation.photos.all()[:4]
        if request:
            return [request.build_absolute_uri(p.image.url) for p in photos]
        return [p.image.url for p in photos]

    def get_like_count(self, obj):
        return RealisationLike.objects.filter(realisation=obj.realisation).count()

    def get_user_liked(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return RealisationLike.objects.filter(
                realisation=obj.realisation, user=request.user
            ).exists()
        return False

    def get_like_toggle_url(self, obj):
        return reverse(
            "plugin_mi_depafi:realisation-like-toggle", kwargs={"pk": obj.realisation_id}
        )

    def get_detail_url(self, obj):
        return obj.realisation.get_absolute_url()
