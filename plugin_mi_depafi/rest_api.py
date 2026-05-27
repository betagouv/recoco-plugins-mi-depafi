from rest_framework import serializers
from rest_framework.filters import BaseFilterBackend
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated

from recoco.rest_api.filters import WatsonSearchFilter
from recoco.utils import has_perm_or_403

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


class CrmRealisationSearchFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, _view):
        search = request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(resource__title__icontains=search)
        return queryset


class CrmRealisationStatusFilter(BaseFilterBackend):
    def filter_queryset(self, request, queryset, _view):
        statuses = request.GET.getlist("status")
        if statuses:
            queryset = queryset.filter(status__in=statuses)
        return queryset


class CrmRealisationCategorySerializer(serializers.Serializer):
    name = serializers.CharField()


class CrmRealisationResourceSerializer(serializers.Serializer):
    title = serializers.CharField()
    category = CrmRealisationCategorySerializer(allow_null=True)


class CrmRealisationCommuneSerializer(serializers.Serializer):
    name = serializers.CharField()
    postal = serializers.CharField()


class CrmRealisationProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    commune = CrmRealisationCommuneSerializer(allow_null=True)


class CrmRealisationSerializer(serializers.ModelSerializer):
    resource = CrmRealisationResourceSerializer(read_only=True)
    project = CrmRealisationProjectSerializer(read_only=True)
    detail_url = serializers.SerializerMethodField()
    update_url = serializers.SerializerMethodField()

    class Meta:
        model = Realisation
        fields = ["id", "resource", "project", "status", "created_at", "detail_url", "update_url"]

    def get_detail_url(self, obj):
        return obj.get_absolute_url()

    def get_update_url(self, obj):
        from django.urls import reverse

        return reverse("plugin_mi_depafi:realisation-update", args=[obj.project_id, obj.pk])


class CrmRealisationPagination(LimitOffsetPagination):
    default_limit = 20


class CrmRealisationListAPIView(ListAPIView):
    serializer_class = CrmRealisationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [CrmRealisationSearchFilter, CrmRealisationStatusFilter, RealisationDepartmentsFilter]
    pagination_class = CrmRealisationPagination

    def get_queryset(self):
        has_perm_or_403(self.request.user, "use_crm", self.request.site)
        return (
            Realisation.objects.filter(project__project_sites__site=self.request.site)
            .select_related("resource__category", "project__commune")
            .order_by("-created_at")
            .distinct()
        )


class RealisationsForMapAPIView(ListAPIView):
    serializer_class = RealisationMapSerializer
    filter_backends = [RealisationStatusFilter, WatsonSearchFilter, RealisationDepartmentsFilter]
    pagination_class = None

    def get_queryset(self):
        return Realisation.objects.select_related(
            "project__commune__department", "resource"
        ).prefetch_related("photos")
