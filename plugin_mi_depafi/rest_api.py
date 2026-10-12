from django_filters import rest_framework as filters
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from recoco.rest_api.filters import WatsonSearchFilter

from .filters import RealisationFilter
from .models import Realisation


class LenientDjangoFilterBackend(filters.DjangoFilterBackend):
    """Ignore invalid filter values (stale bookmark, unknown department code…)
    instead of answering 400, as the map filters did before django-filter."""

    raise_exception = False


class DepartmentMapSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()


class CommuneMapSerializer(serializers.Serializer):
    name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    department = DepartmentMapSerializer()


class ProjectMapSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()
    commune = CommuneMapSerializer()

    def get_latitude(self, obj):
        return obj.location_y

    def get_longitude(self, obj):
        return obj.location_x


class ResourceMapSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()


class RealisationMapSerializer(serializers.ModelSerializer):
    project = ProjectMapSerializer(read_only=True)
    resource = ResourceMapSerializer(read_only=True)
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Realisation
        fields = [
            "id",
            "description",
            "date",
            "updated_at",
            "project",
            "resource",
            "photos",
        ]

    def get_photos(self, obj):
        request = self.context.get("request")
        photos = list(obj.photos.all())[:4]
        if request:
            return [request.build_absolute_uri(p.image.url) for p in photos]
        return [p.image.url for p in photos]


class RealisationsForMapAPIView(ListAPIView):
    serializer_class = RealisationMapSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [WatsonSearchFilter, LenientDjangoFilterBackend]
    filterset_class = RealisationFilter
    pagination_class = None

    def get_queryset(self):
        return (
            Realisation.objects.filter(
                project__project_sites__site=self.request.site,
                status=Realisation.PUBLISHED,
            )
            .select_related("project__commune__department", "resource")
            .prefetch_related("photos")
            .distinct()
        )
