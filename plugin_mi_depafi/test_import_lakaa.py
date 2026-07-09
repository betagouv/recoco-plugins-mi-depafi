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
from model_bakery import baker
from recoco.apps.addressbook.models import Organization
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
            },
            {
                "Nom Forest": f"Mettre en place le tri{_ORG_SUFFIX}",
                "topic": "4. Ressources",
                "description": "Trier les déchets",
                "body": "",
                "external name": "Tri biodéchets",
            },
        ],
    )

    cmd = _make_command()
    resource_map = cmd._import_resources(path, site)

    assert "Mettre en place le tri" in resource_map
    resource = Resource.objects.get(pk=resource_map["Mettre en place le tri"])
    assert resource.title == "Mettre en place le tri"
    assert resource.subtitle == "Tri biodéchets"
    assert resource.content == "Trier les déchets"
    cat = Category.objects.get(name="4. Ressources")
    assert resource.category == cat
    assert cat.color == "yellow"


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


# ---------------------------------------------------------------------------
# _import_projects
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_import_projects_creates_project(tmp_path, request):
    site = _get_site(request)
    path = _write_csv(
        tmp_path,
        "sites.csv",
        [
            {
                "id": "X",
                "name": "X",
                "external id": "X",
                "address": "X",
                "created at": "X",
                "group": "X",
            },
            {
                "id": "42",
                "name": f"GGD Meurthe{_ORG_SUFFIX}",
                "external id": "EXT-42",
                "address": "1 rue de la Paix",
                "created at": "2022-11-15",
                "group": f"Zone Est{_ORG_SUFFIX}",
            },
        ],
    )

    cmd = _make_command()
    project_map = cmd._import_projects(path, site)

    assert "GGD Meurthe" in project_map
    project = Project.objects.get(pk=project_map["GGD Meurthe"])
    assert "Adresse" in project.description
    tag_names = list(project.tags.values_list("name", flat=True))
    assert "lakaa_id:EXT-42" in tag_names
    assert "Zone Est" in tag_names


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
            {
                "id": "X",
                "name": "X",
                "external id": "X",
                "address": "X",
                "created at": "X",
                "group": "X",
            },
            {
                "id": "1",
                "name": "Mon site",
                "external id": "EXT-1",
                "address": "",
                "created at": "",
                "group": "",
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
