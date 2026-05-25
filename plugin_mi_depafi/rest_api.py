from rest_framework import serializers
from rest_framework.filters import BaseFilterBackend
from rest_framework.generics import ListAPIView

from recoco.rest_api.filters import WatsonSearchFilter

from .models import Realisation


class RealisationDepartmentsFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, _view):
        departments = request.GET.getlist("departments")
        if departments:
            queryset = queryset.filter(project__commune__department__code__in=departments)
        return queryset


class RealisationStatusFilter(BaseFilterBackend):
    def filter_queryset(self, _request, queryset, _view):
        return queryset.filter(status=Realisation.PUBLISHED)


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
        fields = ["id", "description", "updated_at", "project", "resource", "photos"]

    def get_photos(self, obj):
        request = self.context.get("request")
        photos = list(obj.photos.all())[:4]
        if request:
            return [request.build_absolute_uri(p.image.url) for p in photos]
        return [p.image.url for p in photos]


class RealisationsForMapAPIView(ListAPIView):
    serializer_class = RealisationMapSerializer
    filter_backends = [RealisationStatusFilter, WatsonSearchFilter, RealisationDepartmentsFilter]
    pagination_class = None

    def get_queryset(self):
        return Realisation.objects.select_related(
            "project__commune__department", "resource"
        ).prefetch_related("photos")
