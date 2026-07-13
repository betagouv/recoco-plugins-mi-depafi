"""
Tests for the import_lakaa management command.

Tests call the private _import_* methods directly to bypass the
TenantCommand.execute() search_path setup, which requires a live tenant schema.
"""

import csv
import io
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from model_bakery import baker
from recoco.apps.addressbook.models import Organization, OrganizationGroup
from recoco.apps.geomatics.models import Commune, Department
from recoco.apps.home.models import UserProfile
from recoco.apps.projects.models import Project
from recoco.apps.resources.models import Category, Resource

from plugin_mi_depafi.management.commands.import_lakaa import (
    Command,
    _parse_date,
    _parse_dt,
    _strip_org,
    _val,
)
from plugin_mi_depafi.models import Realisation

from .conftest import make_project_on_site


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORG_SUFFIX = " - Ministère de l'Intérieur"


def _make_command():
    cmd = Command()
    buf = io.StringIO()
    buf._out = buf  # tqdm uses self.stdout._out to bypass Django's OutputWrapper
    cmd.stdout = buf
    cmd.stderr = io.StringIO()
    cmd.style = type("S", (), {"SUCCESS": staticmethod(lambda s: s)})()
    return cmd


def _write_csv(tmp_path, filename, rows):
    path = tmp_path / filename
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows[1:])
    return str(path)


def _get_site(request):
    project = make_project_on_site(request)
    return project.project_sites.first().site


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


def test_parse_date_slash_format():
    assert _parse_date("15/11/2022") == date(2022, 11, 15)


def test_parse_date_iso_format():
    assert _parse_date("2023-04-01") == date(2023, 4, 1)


def test_parse_date_empty_returns_none():
    assert _parse_date("") is None
    assert _parse_date(None) is None
    assert _parse_date("n.a.") is None


def test_parse_dt_utc_string():
    dt = _parse_dt("2024-05-16 07:13:20 UTC")
    assert dt is not None
    assert dt.year == 2024 and dt.month == 5 and dt.day == 16


def test_val_sentinels_return_none():
    for sentinel in ("n.a", "-", "n.a.", "", None):
        assert _val(sentinel) is None


def test_val_strips_whitespace():
    assert _val("  bonjour  ") == "bonjour"


def test_strip_org_removes_suffix():
    assert _strip_org(f"GGD Meurthe{_ORG_SUFFIX}") == "GGD Meurthe"


def test_strip_org_no_suffix_unchanged():
    assert _strip_org("GGD Meurthe") == "GGD Meurthe"


# ---------------------------------------------------------------------------
# _import_resources
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_import_resources_creates_category_and_resource(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "actions.csv",
        [
            {
                "Nom Forest": "X",
                "topic": "X",
                "description": "X",
                "body": "X",
                "external name": "X",
                "cost indication": "X",
                "impact indication": "X",
                "time indication": "X",
            },
            {
                "Nom Forest": f"Mettre en place le tri{_ORG_SUFFIX}",
                "topic": "4. Ressources",
                "description": "<p>Trier les déchets</p>",
                "body": "<h1>Etape 1</h1><p>Installer un <strong>bac</strong></p>",
                "external name": "Tri biodéchets",
                "cost indication": "Environ 200€",
                "impact indication": "Fort",
                "time indication": "2 semaines",
            },
        ],
    )

    cmd = _make_command()
    resource_map = cmd._import_resources(path, site)

    assert "Mettre en place le tri" in resource_map
    resource = Resource.objects.get(pk=resource_map["Mettre en place le tri"])
    assert resource.title == "Mettre en place le tri"
    assert resource.subtitle == "Fort"
    assert resource.summary == "Trier les déchets"
    assert resource.content.startswith("Temps de mise en œuvre: 2 semaines")
    assert "# Etape 1" in resource.content
    assert "**bac**" in resource.content
    assert "## Evaluation des coûts\n\nEnviron 200€" in resource.content
    cat = Category.objects.get(name="4. Ressources")
    assert resource.category == cat
    assert cat.color == "yellow"


@pytest.mark.django_db
def test_import_resources_honors_published_status(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "actions.csv",
        [
            {"Nom Forest": "X", "topic": "X", "status": "X"},
            {"Nom Forest": "Action publiée", "topic": "1. RH", "status": "published"},
        ],
    )

    cmd = _make_command()
    resource_map = cmd._import_resources(path, site)

    resource = Resource.objects.get(pk=resource_map["Action publiée"])
    assert resource.status == Resource.PUBLISHED


@pytest.mark.django_db
def test_import_resources_honors_draft_status(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "actions.csv",
        [
            {"Nom Forest": "X", "topic": "X", "status": "X"},
            {"Nom Forest": "Action brouillon", "topic": "1. RH", "status": "draft"},
        ],
    )

    cmd = _make_command()
    resource_map = cmd._import_resources(path, site)

    resource = Resource.objects.get(pk=resource_map["Action brouillon"])
    assert resource.status == Resource.DRAFT


@pytest.mark.django_db
def test_import_resources_unknown_status_defaults_to_draft(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "actions.csv",
        [
            {"Nom Forest": "X", "topic": "X", "status": "X"},
            {"Nom Forest": "Action sans statut", "topic": "1. RH", "status": ""},
        ],
    )

    cmd = _make_command()
    resource_map = cmd._import_resources(path, site)

    resource = Resource.objects.get(pk=resource_map["Action sans statut"])
    assert resource.status == Resource.DRAFT


@pytest.mark.django_db
def test_import_resources_force_updates_status(tmp_path, request):
    site = _get_site(request)
    resource = baker.make(
        Resource,
        title="Mon action",
        status=Resource.PUBLISHED,
        site_origin=site,
    )
    resource.sites.add(site)

    path = _write_csv(
        tmp_path,
        "actions.csv",
        [
            {"Nom Forest": "X", "topic": "X", "status": "X"},
            {"Nom Forest": "Mon action", "topic": "1. RH", "status": "draft"},
        ],
    )

    cmd = _make_command()
    cmd._import_resources(path, site, force=True)

    resource.refresh_from_db()
    assert resource.status == Resource.DRAFT


@pytest.mark.django_db
def test_import_resources_skips_duplicate(tmp_path, request):
    site = _get_site(request)
    resource = baker.make(
        Resource, title="Mon action", status=Resource.PUBLISHED, site_origin=site
    )
    resource.sites.add(site)

    path = _write_csv(
        tmp_path,
        "actions.csv",
        [
            {
                "Nom Forest": "X",
                "topic": "X",
                "description": "X",
                "body": "X",
                "external name": "X",
            },
            {
                "Nom Forest": "Mon action",
                "topic": "1. RH",
                "description": "desc",
                "body": "",
                "external name": "",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_resources(path, site)

    assert Resource.objects.filter(title="Mon action", sites=site).count() == 1


@pytest.mark.django_db
def test_import_resources_force_updates_existing(tmp_path, request):
    site = _get_site(request)
    resource = baker.make(
        Resource,
        title="Mon action",
        subtitle="old subtitle",
        content="old content",
        status=Resource.PUBLISHED,
        site_origin=site,
    )
    resource.sites.add(site)

    path = _write_csv(
        tmp_path,
        "actions.csv",
        [
            {
                "Nom Forest": "X",
                "topic": "X",
                "description": "X",
                "body": "X",
                "external name": "X",
            },
            {
                "Nom Forest": "Mon action",
                "topic": "1. RH",
                "description": "<p>new summary</p>",
                "body": "<p>new content</p>",
                "external name": "new subtitle",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_resources(path, site, force=True)

    resource.refresh_from_db()
    assert resource.subtitle == "new subtitle"
    assert resource.summary == "new summary"
    assert resource.content == "new content"
    assert resource.category == Category.objects.get(name="1. RH")


@pytest.mark.django_db
def test_import_resources_category_scoped_per_site(tmp_path, request):
    site_a = _get_site(request)
    site_b = baker.make(Site, domain="other-site.example.com")

    existing_cat = baker.make(Category, name="4. Ressources", color="blue", icon="bi-star")
    existing_cat.sites.add(site_b)

    path = _write_csv(
        tmp_path,
        "actions.csv",
        [
            {
                "Nom Forest": "X",
                "topic": "X",
                "description": "X",
                "body": "X",
                "external name": "X",
            },
            {
                "Nom Forest": "Mon action",
                "topic": "4. Ressources",
                "description": "",
                "body": "",
                "external name": "",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_resources(path, site_a)

    cats = Category.objects.filter(name="4. Ressources")
    assert cats.count() == 2
    new_cat = cats.exclude(pk=existing_cat.pk).get()
    assert new_cat.color == "yellow"
    assert site_a in new_cat.sites.all()
    assert site_b not in new_cat.sites.all()
    assert existing_cat.color == "blue"


# ---------------------------------------------------------------------------
# _import_projects
# ---------------------------------------------------------------------------


_SITES_HEADER = {
    "id": "X", "name": "X", "external id": "X", "organisation": "X",
    "address": "X", "coordinates": "X", "created at": "X", "group": "X",
}


@pytest.mark.django_db
def test_import_projects_creates_project(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "42",
                "name": f"GGD Meurthe{_ORG_SUFFIX}",
                "external id": "EXT-42",
                "organisation": "",
                "address": "1 rue de la Paix",
                "coordinates": "",
                "created at": "2022-11-15",
                "group": f"Zone Est{_ORG_SUFFIX}",
            },
        ],
    )

    cmd = _make_command()
    project_map = cmd._import_projects(path, site)

    assert "GGD Meurthe" in project_map
    project = Project.objects.get(pk=project_map["GGD Meurthe"])
    assert project.location == "1 rue de la Paix"
    tag_names = list(project.tags.values_list("name", flat=True))
    assert "lakaa_id:EXT-42" in tag_names
    assert "Zone Est" in tag_names


@pytest.mark.django_db
def test_import_projects_sets_coordinates(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Site GPS", "external id": "EXT-1",
                "organisation": "", "address": "",
                "coordinates": "48.6921, 6.1844",
                "created at": "", "group": "",
            },
        ],
    )

    cmd = _make_command()
    project_map = cmd._import_projects(path, site)

    project = Project.objects.get(pk=project_map["Site GPS"])
    assert project.location_x == pytest.approx(48.6921)
    assert project.location_y == pytest.approx(6.1844)


@pytest.mark.django_db
def test_import_projects_creates_org_in_group(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Mon site", "external id": "EXT-1",
                "organisation": f"GGD Meurthe{_ORG_SUFFIX}",
                "address": "", "coordinates": "", "created at": "",
                "group": f"Zone Est{_ORG_SUFFIX}",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_projects(path, site)

    org = Organization.objects.get(name="GGD Meurthe")
    assert org.group is not None
    assert org.group.name == "Zone Est"


@pytest.mark.django_db
def test_import_projects_force_updates_org_group(tmp_path, request):
    site = _get_site(request)
    old_group = baker.make(OrganizationGroup, name="Ancien groupe")
    org = baker.make(Organization, name="GGD Meurthe", group=old_group)
    org.sites.add(site)

    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Mon site", "external id": "EXT-1",
                "organisation": "GGD Meurthe",
                "address": "", "coordinates": "", "created at": "",
                "group": "Nouveau groupe",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_projects(path, site, force_orgs=True)

    org.refresh_from_db()
    assert org.group.name == "Nouveau groupe"


@pytest.mark.django_db
def test_import_projects_does_not_overwrite_org_group_without_force(tmp_path, request):
    site = _get_site(request)
    existing_group = baker.make(OrganizationGroup, name="Groupe existant")
    org = baker.make(Organization, name="GGD Meurthe", group=existing_group)
    org.sites.add(site)

    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Mon site", "external id": "EXT-1",
                "organisation": "GGD Meurthe",
                "address": "", "coordinates": "", "created at": "",
                "group": "Nouveau groupe",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_projects(path, site)

    org.refresh_from_db()
    assert org.group == existing_group


@pytest.mark.django_db
def test_import_projects_force_updates_location(tmp_path, request):
    existing = make_project_on_site(request)
    existing.name = "Mon site"
    existing.location = "Ancienne adresse"
    existing.save()
    site = existing.project_sites.first().site

    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Mon site", "external id": "EXT-1",
                "organisation": "", "address": "Nouvelle adresse",
                "coordinates": "48.6921, 6.1844", "created at": "", "group": "",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_projects(path, site, force_projects=True)

    existing.refresh_from_db()
    assert existing.location == "Nouvelle adresse"
    assert existing.location_x == pytest.approx(48.6921)
    assert existing.location_y == pytest.approx(6.1844)


@pytest.mark.django_db
def test_import_projects_does_not_update_location_without_force(tmp_path, request):
    existing = make_project_on_site(request)
    existing.name = "Mon site"
    existing.location = "Adresse originale"
    existing.save()
    site = existing.project_sites.first().site

    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Mon site", "external id": "EXT-1",
                "organisation": "", "address": "Nouvelle adresse",
                "coordinates": "", "created at": "", "group": "",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_projects(path, site)

    existing.refresh_from_db()
    assert existing.location == "Adresse originale"


@pytest.mark.django_db
def test_import_projects_matches_commune_by_city_name(tmp_path, request):
    site = _get_site(request)
    department = baker.make(Department)
    commune = baker.make(
        Commune, department=department, name="Melun", postal="77000", insee="77288"
    )

    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "ATE Seine-et-Marne", "external id": "EXT-1",
                "organisation": "", "address": "Melun", "coordinates": "",
                "created at": "", "group": "",
            },
        ],
    )

    cmd = _make_command()
    project_map = cmd._import_projects(path, site)

    project = Project.objects.get(pk=project_map["ATE Seine-et-Marne"])
    assert project.commune == commune


@pytest.mark.django_db
def test_import_projects_matches_commune_by_postal_code_and_city(tmp_path, request):
    site = _get_site(request)
    department = baker.make(Department)
    commune = baker.make(
        Commune,
        department=department,
        name="Charleville-Mézières",
        postal="08000",
        insee="08105",
    )

    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Site Ardennes", "external id": "EXT-1",
                "organisation": "", "coordinates": "", "created at": "", "group": "",
                "address": "9 rue Bayard 08000 Charleville-Mézières",
            },
        ],
    )

    cmd = _make_command()
    project_map = cmd._import_projects(path, site)

    project = Project.objects.get(pk=project_map["Site Ardennes"])
    assert project.commune == commune


@pytest.mark.django_db
def test_import_projects_no_commune_match_leaves_commune_none(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Site inconnu", "external id": "EXT-1",
                "organisation": "", "address": "Ville introuvable",
                "coordinates": "", "created at": "", "group": "",
            },
        ],
    )

    cmd = _make_command()
    project_map = cmd._import_projects(path, site)

    project = Project.objects.get(pk=project_map["Site inconnu"])
    assert project.commune is None


@pytest.mark.django_db
def test_import_projects_reads_coordinates_forest_column(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            {
                "id": "X", "name": "X", "external id": "X", "organisation": "X",
                "address": "X", "coordinates forest": "X", "created at": "X",
                "group": "X",
            },
            {
                "id": "1", "name": "Site GPS forest", "external id": "EXT-1",
                "organisation": "", "address": "",
                "coordinates forest": "48.6921, 6.1844",
                "created at": "", "group": "",
            },
        ],
    )

    cmd = _make_command()
    project_map = cmd._import_projects(path, site)

    project = Project.objects.get(pk=project_map["Site GPS forest"])
    assert project.location_x == pytest.approx(48.6921)
    assert project.location_y == pytest.approx(6.1844)


@pytest.mark.django_db
def test_import_projects_idempotent(tmp_path, request):
    existing = make_project_on_site(request)
    existing.name = "Mon site"
    existing.save()
    site = existing.project_sites.first().site

    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            _SITES_HEADER,
            {
                "id": "1", "name": "Mon site", "external id": "EXT-1",
                "organisation": "", "address": "", "coordinates": "",
                "created at": "", "group": "",
            },
        ],
    )

    cmd = _make_command()
    cmd._import_projects(path, site)

    assert Project.objects.filter(name="Mon site").count() == 1


# ---------------------------------------------------------------------------
# _import_users
# ---------------------------------------------------------------------------

def _user_row(**kwargs):
    base = {
        "id": "1", "organisation": f"Ministère de l'Intérieur{_ORG_SUFFIX}",
        "first name": "Alice", "last name": "Dupont",
        "email": "alice@interieur.gouv.fr", "role": "store_manager",
        "sign in count": "1", "current sign in at": "", "created at": "",
        "first sign in at": "", "lang": "fr", "updated at": "",
    }
    base.update(kwargs)
    return base


def _decl_for_user_row(**kwargs):
    base = {
        "Identifiant de la déclaration": "1",
        "Nom de l'établissement": f"GGD Meurthe{_ORG_SUFFIX}",
        "Nom de l'action": "Tri",
        "Email du déclarant": "alice@interieur.gouv.fr",
        "Déclaré le": "", "Completion": "Complet",
        "Partenaires": "", "Sites concernés": "",
        "Date de début": "", "Indicateurs": "", "Valeurs": "",
    }
    base.update(kwargs)
    return base


def _setup_user_import(tmp_path, user_rows, decl_rows):
    users_path = _write_csv(tmp_path, "users.csv", [_user_row()] + user_rows)
    reports_path = _write_csv(tmp_path, "decl.csv", [_decl_for_user_row()] + decl_rows)
    return users_path, reports_path


@pytest.mark.django_db
def test_import_users_sets_profile_site(tmp_path, current_site):
    users_path, reports_path = _setup_user_import(
        tmp_path, [_user_row()], [_decl_for_user_row()]
    )

    _make_command()._import_users(users_path, {}, reports_path, current_site)

    user = User.objects.get(username="alice@interieur.gouv.fr")
    assert current_site in user.profile.sites.all()


@pytest.mark.django_db
def test_import_users_creates_and_sets_organisation(tmp_path, current_site):
    users_path, reports_path = _setup_user_import(
        tmp_path, [_user_row()], [_decl_for_user_row()]
    )

    _make_command()._import_users(users_path, {}, reports_path, current_site)

    user = User.objects.get(username="alice@interieur.gouv.fr")
    assert user.profile.organization is not None
    assert user.profile.organization.name == "Ministère de l'Intérieur"


@pytest.mark.django_db
def test_import_users_links_organisation_to_site(tmp_path, current_site):
    users_path, reports_path = _setup_user_import(
        tmp_path, [_user_row()], [_decl_for_user_row()]
    )

    _make_command()._import_users(users_path, {}, reports_path, current_site)

    org = Organization.objects.get(name="Ministère de l'Intérieur")
    assert current_site in org.sites.all()


@pytest.mark.django_db
def test_import_users_force_updates_organisation(tmp_path, current_site):
    old_org = baker.make(Organization)
    user = baker.make(User, username="alice@interieur.gouv.fr", email="alice@interieur.gouv.fr")
    # baker.make(User) auto-creates a UserProfile via post_save signal
    user.profile.organization = old_org
    user.profile.save(update_fields=["organization"])
    user.profile.sites.add(current_site)

    users_path, reports_path = _setup_user_import(
        tmp_path, [_user_row()], [_decl_for_user_row()]
    )

    _make_command()._import_users(users_path, {}, reports_path, current_site, force=True)

    user.profile.refresh_from_db()
    assert user.profile.organization.name == "Ministère de l'Intérieur"


@pytest.mark.django_db
def test_import_users_skips_organisation_update_without_force(tmp_path, current_site):
    old_org = baker.make(Organization, name="Organisation originale")
    user = baker.make(User, username="alice@interieur.gouv.fr", email="alice@interieur.gouv.fr")
    # baker.make(User) auto-creates a UserProfile via post_save signal
    user.profile.organization = old_org
    user.profile.save(update_fields=["organization"])
    user.profile.sites.add(current_site)

    users_path, reports_path = _setup_user_import(
        tmp_path, [_user_row()], [_decl_for_user_row()]
    )

    _make_command()._import_users(users_path, {}, reports_path, current_site)

    user.profile.refresh_from_db()
    assert user.profile.organization == old_org


# ---------------------------------------------------------------------------
# _import_realisations — new column names + new field mapping
# ---------------------------------------------------------------------------


def _decl_row(**kwargs):
    base = {
        "Identifiant de la déclaration": "100",
        "Nom de l'établissement": "GGD Meurthe",
        "Nom de l'action": "Mettre en place le tri",
        "Email du déclarant": "agent@interieur.gouv.fr",
        "Déclaré le": "6/2/2024",
        "Completion": "Incomplet",
        "Partenaires": "",
        "Sites concernés": "",
        "Date de début": "",
        "Indicateurs": "",
        "Valeurs": "",
    }
    base.update(kwargs)
    return base


def _setup_realisation_prereqs(request):
    project = make_project_on_site(request)
    project.name = "GGD Meurthe"
    project.save()
    site = project.project_sites.first().site
    resource = baker.make(Resource, title="Mettre en place le tri")
    resource.sites.add(site)
    user = baker.make(
        User, username="agent@interieur.gouv.fr", email="agent@interieur.gouv.fr"
    )
    return project, resource, user


@pytest.mark.django_db
def test_import_realisations_incomplete_creates_draft(tmp_path, request):
    project, resource, _ = _setup_realisation_prereqs(request)

    path = _write_csv(
        tmp_path, "decl.csv", [_decl_row(), _decl_row(Completion="Incomplet")]
    )

    cmd = _make_command()
    cmd._import_realisations(
        path,
        {project.name: project.pk},
        {resource.title: resource.pk},
    )

    r = Realisation.objects.get(project=project, resource=resource)
    assert r.status == Realisation.DRAFT


@pytest.mark.django_db
def test_import_realisations_complet_creates_published(tmp_path, request):
    project, resource, _ = _setup_realisation_prereqs(request)

    path = _write_csv(
        tmp_path, "decl.csv", [_decl_row(), _decl_row(Completion="Complet")]
    )

    cmd = _make_command()
    cmd._import_realisations(
        path,
        {project.name: project.pk},
        {resource.title: resource.pk},
    )

    r = Realisation.objects.get(project=project, resource=resource)
    assert r.status == Realisation.PUBLISHED


@pytest.mark.django_db
def test_import_realisations_maps_partners(tmp_path, request):
    project, resource, _ = _setup_realisation_prereqs(request)

    path = _write_csv(
        tmp_path,
        "decl.csv",
        [_decl_row(), _decl_row(**{"Partenaires": "Metropole Grand Nancy"})],
    )

    cmd = _make_command()
    cmd._import_realisations(
        path, {project.name: project.pk}, {resource.title: resource.pk}
    )

    assert Realisation.objects.get(project=project).partners == "Metropole Grand Nancy"


@pytest.mark.django_db
def test_import_realisations_maps_site_field(tmp_path, request):
    project, resource, _ = _setup_realisation_prereqs(request)

    path = _write_csv(
        tmp_path,
        "decl.csv",
        [_decl_row(), _decl_row(**{"Sites concernés": "Caserne Roux, Lexy"})],
    )

    cmd = _make_command()
    cmd._import_realisations(
        path, {project.name: project.pk}, {resource.title: resource.pk}
    )

    assert Realisation.objects.get(project=project).site == "Caserne Roux, Lexy"


@pytest.mark.django_db
def test_import_realisations_maps_date(tmp_path, request):
    project, resource, _ = _setup_realisation_prereqs(request)

    path = _write_csv(
        tmp_path,
        "decl.csv",
        [_decl_row(), _decl_row(**{"Date de début": "15/11/2022"})],
    )

    cmd = _make_command()
    cmd._import_realisations(
        path, {project.name: project.pk}, {resource.title: resource.pk}
    )

    assert Realisation.objects.get(project=project).date == date(2022, 11, 15)


@pytest.mark.django_db
def test_import_realisations_maps_key_figures(tmp_path, request):
    project, resource, _ = _setup_realisation_prereqs(request)

    path = _write_csv(
        tmp_path,
        "decl.csv",
        [_decl_row(), _decl_row(**{"Valeurs": "3 sites, 120 agents"})],
    )

    cmd = _make_command()
    cmd._import_realisations(
        path, {project.name: project.pk}, {resource.title: resource.pk}
    )

    assert Realisation.objects.get(project=project).key_figures == "3 sites, 120 agents"


@pytest.mark.django_db
def test_import_realisations_appends_indicateurs_to_description(tmp_path, request):
    project, resource, _ = _setup_realisation_prereqs(request)

    path = _write_csv(
        tmp_path,
        "decl.csv",
        [_decl_row(), _decl_row(**{"Indicateurs": "Description de votre action"})],
    )

    cmd = _make_command()
    cmd._import_realisations(
        path, {project.name: project.pk}, {resource.title: resource.pk}
    )

    r = Realisation.objects.get(project=project)
    assert r.description.startswith("<!-- lakaa:100 -->")
    assert "Description de votre action" in r.description


@pytest.mark.django_db
def test_import_realisations_sets_created_by(tmp_path, request):
    project, resource, user = _setup_realisation_prereqs(request)

    path = _write_csv(tmp_path, "decl.csv", [_decl_row(), _decl_row()])

    cmd = _make_command()
    cmd._import_realisations(
        path, {project.name: project.pk}, {resource.title: resource.pk}
    )

    assert Realisation.objects.get(project=project).created_by == user


@pytest.mark.django_db
def test_import_realisations_idempotent(tmp_path, request):
    project, resource, _ = _setup_realisation_prereqs(request)

    path = _write_csv(tmp_path, "decl.csv", [_decl_row(), _decl_row()])

    cmd = _make_command()
    cmd._import_realisations(
        path, {project.name: project.pk}, {resource.title: resource.pk}
    )
    cmd._import_realisations(
        path, {project.name: project.pk}, {resource.title: resource.pk}
    )

    assert Realisation.objects.filter(project=project, resource=resource).count() == 1


@pytest.mark.django_db
def test_import_realisations_warns_on_unknown_project(tmp_path):
    resource = baker.make(Resource, title="Mettre en place le tri")
    path = _write_csv(tmp_path, "decl.csv", [_decl_row(), _decl_row()])

    cmd = _make_command()
    cmd._import_realisations(path, {}, {resource.title: resource.pk})

    assert "WARN" in cmd.stderr.getvalue()
    assert Realisation.objects.count() == 0


@pytest.mark.django_db
def test_import_realisations_warns_on_unknown_resource(tmp_path, request):
    project = make_project_on_site(request)
    project.name = "GGD Meurthe"
    project.save()

    path = _write_csv(tmp_path, "decl.csv", [_decl_row(), _decl_row()])

    cmd = _make_command()
    cmd._import_realisations(path, {project.name: project.pk}, {})

    assert "WARN" in cmd.stderr.getvalue()
    assert Realisation.objects.count() == 0
