"""
Tests for the import_lakaa management command.

Most tests call the private _import_* methods directly with an explicit site;
the command entry point (site selection) is covered separately.
"""

import csv
import io
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from model_bakery import baker
from recoco.apps.addressbook.models import Organization, OrganizationGroup
from recoco.apps.geomatics.models import Commune, Department
from recoco.apps.plugins.resolvers import get_enabled_plugins, set_enabled_plugins
from recoco.apps.projects.models import Project, ProjectMember
from recoco.apps.resources.models import Category, Resource

from plugin_mi_depafi.apps import PLUGIN_NAME
from plugin_mi_depafi.management.commands import import_lakaa
from plugin_mi_depafi.management.commands.import_lakaa import (
    Command,
    _html_to_text,
    _parse_date,
    _parse_dt,
    _shorten,
    _strip_org,
    _val,
)
from plugin_mi_depafi.models import DepafiProject, Realisation

from ..conftest import make_project_on_site
from .conftest import make_resource

pytestmark = pytest.mark.django_db

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
    """Write `rows` (dicts) to a CSV, the header being the union of their keys."""
    path = tmp_path / filename
    fieldnames = list(dict.fromkeys(key for row in rows for key in row))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def _action_row(**kwargs):
    return {"id": "3333", "name": "Mon action", "topic": "1. RH", **kwargs}


def _site_row(**kwargs):
    return {
        "Id": "22680",
        "Nom": "Mon site",
        "Id externe": "EXT-1",
        "Organisation": "",
        "Adresse": "",
        "Coordonnées": "",
        "Date de création": "",
        "Région": "",
        **kwargs,
    }


def _user_row(**kwargs):
    return {
        "id": "1",
        "organisation": f"Ministère de l'Intérieur{_ORG_SUFFIX}",
        "first name": "Alice",
        "last name": "Dupont",
        "email": "alice@interieur.gouv.fr",
        "role": "store_manager",
        "Dernière connexion": "",
        "sites": "",
        "ID des sites": "",
        "ID externe des sites": "",
        "Typologie d'utilisateurs": "",
        **kwargs,
    }


def _decl_row(indicateur="", valeur="", **kwargs):
    """One row of a declaration: fixed metadata plus a single indicator/value pair.

    Real Lakaa exports repeat the fixed columns identically across every row
    of a declaration and vary only "Indicateurs"/"Valeurs": a declaration
    must be consolidated across all of its rows before import.
    """
    return {
        "Identifiant de la déclaration": "100",
        "Nom de l'établissement": "GGD Meurthe",
        "Nom de l'action": "Mettre en place le tri",
        "Email du déclarant": "agent@interieur.gouv.fr",
        "Déclaré le": "6/2/2024",
        "Completion": "Incomplet",
        "Partenaires": "",
        "Images": "",
        "Date de début": "",
        "Indicateurs": indicateur,
        "Valeurs": valeur,
        **kwargs,
    }


def _import_actions(tmp_path, site, rows, **kwargs):
    path = _write_csv(tmp_path, "actions.csv", rows)
    return _make_command()._import_resources(path, site, **kwargs)


def _import_sites(tmp_path, site, rows, cmd=None, **kwargs):
    path = _write_csv(tmp_path, "sites.csv", rows)
    return (cmd or _make_command())._import_projects(path, site, **kwargs)


def _import_users(tmp_path, site, rows, project_ids=None, cmd=None, **kwargs):
    path = _write_csv(tmp_path, "users.csv", rows)
    (cmd or _make_command())._import_users(path, project_ids or {}, site, **kwargs)


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("15/11/2022", date(2022, 11, 15)),
        ("2023-04-01", date(2023, 4, 1)),
        ("", None),
        (None, None),
        ("n.a.", None),
    ],
)
def test_parse_date(value, expected):
    assert _parse_date(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2024-05-16 07:13:20 UTC", date(2024, 5, 16)),
        ("6/2/2024", date(2024, 2, 6)),
    ],
)
def test_parse_dt(value, expected):
    assert _parse_dt(value).date() == expected


@pytest.mark.parametrize("sentinel", ["n.a", "-", "n.a.", "", None])
def test_val_sentinels_return_none(sentinel):
    assert _val(sentinel) is None


def test_val_strips_whitespace():
    assert _val("  bonjour  ") == "bonjour"


@pytest.mark.parametrize("value", [f"GGD Meurthe{_ORG_SUFFIX}", "GGD Meurthe"])
def test_strip_org(value):
    assert _strip_org(value) == "GGD Meurthe"


def test_html_to_text_separates_blocks_and_unescapes():
    html = "<p>Trier les <strong>déchets</strong></p><ul><li>bac&nbsp;jaune</li></ul>"
    assert _html_to_text(html) == "Trier les déchets bac jaune"


@pytest.mark.parametrize(
    "text,max_length,expected",
    [
        ("court", 10, "court"),
        ("un deux trois, quatre", 17, "un deux trois…"),
        ("abcdefghij", 5, "abcd…"),
    ],
)
def test_shorten(text, max_length, expected):
    assert _shorten(text, max_length) == expected


# ---------------------------------------------------------------------------
# _import_resources
# ---------------------------------------------------------------------------


def test_import_resources_creates_category_and_resource(tmp_path, current_site):
    resource_map = _import_actions(
        tmp_path,
        current_site,
        [
            _action_row(
                name=f"Mettre en place le tri{_ORG_SUFFIX}",
                topic="4. Ressources",
                description="<p>Trier les déchets</p>",
                body="<h1>Etape 1</h1><p>Installer un <strong>bac</strong></p>",
                **{
                    "cost indication": "Environ 200€",
                    "impact indication": "Fort",
                    "time indication": "2 semaines",
                },
            )
        ],
    )

    resource = Resource.objects.get(pk=resource_map["Mettre en place le tri"])
    assert resource.title == "Mettre en place le tri"
    assert resource.subtitle == "Fort"
    assert resource.summary == "Trier les déchets"
    assert resource.content.startswith("Temps de mise en œuvre: 2 semaines")
    assert "# Etape 1" in resource.content
    assert "**bac**" in resource.content
    assert "## Evaluation des coûts\n\nEnviron 200€" in resource.content
    assert "lakaa_action:3333" in resource.tags.names()
    cat = Category.objects.get(name="4. Ressources")
    assert resource.category == cat
    assert cat.color == "yellow"


@pytest.mark.parametrize(
    "status,expected",
    [
        ("published", Resource.PUBLISHED),
        ("draft", Resource.DRAFT),
        ("", Resource.DRAFT),
    ],
)
def test_import_resources_maps_status(tmp_path, current_site, status, expected):
    resource_map = _import_actions(tmp_path, current_site, [_action_row(status=status)])

    assert Resource.objects.get(pk=resource_map["Mon action"]).status == expected


def test_import_resources_force_updates_existing(tmp_path, current_site):
    resource = baker.make(
        Resource,
        title="Mon action",
        subtitle="old subtitle",
        content="old content",
        status=Resource.PUBLISHED,
        site_origin=current_site,
        sites=[current_site],
    )

    _import_actions(
        tmp_path,
        current_site,
        [
            _action_row(
                status="draft",
                description="<p>new summary</p>",
                body="<p>new content</p>",
                **{"impact indication": "new subtitle"},
            )
        ],
        force=True,
    )

    resource.refresh_from_db()
    assert resource.status == Resource.DRAFT
    assert resource.subtitle == "new subtitle"
    assert resource.summary == "new summary"
    assert resource.content == "new content"
    assert resource.category == Category.objects.get(name="1. RH")


def test_import_resources_long_description_kept_in_content(tmp_path, current_site):
    long_desc = (
        "<p>"
        + " ".join(["**mot**"] * 10)
        + " "
        + "<strong>gras</strong> " * 200
        + "fin.</p>"
    )
    path = _write_csv(
        tmp_path,
        "actions.csv",
        [_action_row(description=long_desc, body="<h1>Etape 1</h1>")],
    )

    cmd = _make_command()
    resource_map = cmd._import_resources(path, current_site)

    resource = Resource.objects.get(pk=resource_map["Mon action"])
    assert len(resource.summary) <= 512
    assert resource.summary.endswith("…")
    assert "<strong>" not in resource.summary
    # The full description is kept at the top of content, before the body.
    assert resource.content.endswith("# Etape 1")
    assert "fin." in resource.content
    assert "**gras**" in resource.content
    assert "Summary of 'Mon action' shortened" in cmd.stderr.getvalue()


def test_import_resources_long_description_without_body(tmp_path, current_site):
    long_desc = "<p>" + "texte " * 200 + "fin.</p>"
    resource_map = _import_actions(
        tmp_path, current_site, [_action_row(description=long_desc, body="")]
    )

    resource = Resource.objects.get(pk=resource_map["Mon action"])
    assert resource.summary.endswith("…")
    assert resource.content.endswith("fin.")


def test_import_resources_category_scoped_per_site(tmp_path, current_site):
    other_site = baker.make(Site, domain="other-site.example.com")
    existing_cat = baker.make(
        Category, name="4. Ressources", color="blue", icon="bi-star"
    )
    existing_cat.sites.add(other_site)

    _import_actions(tmp_path, current_site, [_action_row(topic="4. Ressources")])

    new_cat = Category.objects.filter(name="4. Ressources").exclude(pk=existing_cat.pk)
    new_cat = new_cat.get()
    assert new_cat.color == "yellow"
    assert list(new_cat.sites.all()) == [current_site]
    assert existing_cat.color == "blue"


def test_import_resources_tags_resource_matched_by_title(tmp_path, current_site):
    """Resources of earlier imports have no id tag: they get one, so later
    renames still match."""
    resource = baker.make(
        Resource, title="Mon action", site_origin=current_site, sites=[current_site]
    )

    _import_actions(tmp_path, current_site, [_action_row()])

    assert "lakaa_action:3333" in resource.tags.names()
    assert Resource.objects.filter(sites=current_site).count() == 1


def test_import_resources_matches_renamed_action_by_lakaa_id(tmp_path, current_site):
    resource = baker.make(
        Resource,
        title="Recyclage des archives",
        site_origin=current_site,
        sites=[current_site],
    )
    resource.tags.add("lakaa_action:3333")
    new_name = "Mettre en place le recyclage des archives papier"

    resource_map = _import_actions(tmp_path, current_site, [_action_row(name=new_name)])

    assert resource_map == {new_name: resource.pk}
    assert Resource.objects.filter(sites=current_site).count() == 1
    resource.refresh_from_db()
    assert resource.title == "Recyclage des archives"


def test_import_resources_force_renames_action_matched_by_lakaa_id(
    tmp_path, current_site
):
    resource = baker.make(
        Resource, title="Ancien titre", site_origin=current_site, sites=[current_site]
    )
    resource.tags.add("lakaa_action:3333")

    _import_actions(
        tmp_path, current_site, [_action_row(name="Nouveau titre")], force=True
    )

    resource.refresh_from_db()
    assert resource.title == "Nouveau titre"


# ---------------------------------------------------------------------------
# _import_projects
# ---------------------------------------------------------------------------


def test_import_projects_creates_project(tmp_path, current_site):
    project_map, project_ids = _import_sites(
        tmp_path,
        current_site,
        [
            _site_row(
                Nom=f"GGD Meurthe{_ORG_SUFFIX}",
                **{
                    "Id externe": "EXT-42",
                    "Adresse": "1 rue de la Paix",
                    "Coordonnées": "48.6921, 6.1844",
                    "Date de création": "27/3/2025",
                    "Région": f"Zone Est{_ORG_SUFFIX}",
                },
            )
        ],
    )

    project = Project.objects.get(pk=project_map["GGD Meurthe"])
    assert project_ids == {"22680": project.pk}
    assert project.location == "1 rue de la Paix"
    assert project.location_y == pytest.approx(48.6921)
    assert project.location_x == pytest.approx(6.1844)
    assert timezone.localtime(project.created_on).date() == date(2025, 3, 27)
    assert project.project_sites.get(site=current_site).status == "READY"
    assert {"lakaa_id:EXT-42", "lakaa_site:22680", "Zone Est"} <= set(
        project.tags.names()
    )


def test_import_projects_creates_org_in_group(tmp_path, current_site):
    _import_sites(
        tmp_path,
        current_site,
        [
            _site_row(
                Organisation=f"GGD Meurthe{_ORG_SUFFIX}",
                **{"Région": f"Zone Est{_ORG_SUFFIX}"},
            )
        ],
    )

    org = Organization.objects.get(name="GGD Meurthe")
    assert org.group.name == "Zone Est"


def test_import_projects_force_updates_org_group_of_existing_project(
    tmp_path, request, current_site
):
    make_project_on_site(request, name="Mon site")
    old_group = baker.make(OrganizationGroup, name="Ancien groupe")
    org = baker.make(Organization, name="GGD Meurthe", group=old_group)

    _import_sites(
        tmp_path,
        current_site,
        [_site_row(Organisation="GGD Meurthe", **{"Région": "Nouveau groupe"})],
        force_orgs=True,
    )

    org.refresh_from_db()
    assert org.group.name == "Nouveau groupe"
    assert current_site in org.sites.all()


def test_import_projects_does_not_overwrite_org_group_without_force(
    tmp_path, current_site
):
    existing_group = baker.make(OrganizationGroup, name="Groupe existant")
    org = baker.make(
        Organization, name="GGD Meurthe", group=existing_group, sites=[current_site]
    )

    _import_sites(
        tmp_path,
        current_site,
        [_site_row(Organisation="GGD Meurthe", **{"Région": "Nouveau groupe"})],
    )

    org.refresh_from_db()
    assert org.group == existing_group


def test_import_projects_force_does_not_regroup_organisation_shared_with_other_site(
    tmp_path, current_site
):
    old_group = baker.make(OrganizationGroup, name="Ancien groupe")
    org = baker.make(
        Organization, name="GGD Meurthe", group=old_group, sites=[baker.make(Site)]
    )

    cmd = _make_command()
    _import_sites(
        tmp_path,
        current_site,
        [_site_row(Organisation="GGD Meurthe", **{"Région": "Nouveau groupe"})],
        cmd=cmd,
        force_orgs=True,
    )

    org.refresh_from_db()
    assert org.group == old_group
    assert "shared with other sites" in cmd.stderr.getvalue()
    assert current_site in org.sites.all()


def test_import_projects_force_updates_tags_of_existing_project(
    tmp_path, request, current_site
):
    existing = make_project_on_site(request, name="Mon site")

    _import_sites(
        tmp_path,
        current_site,
        [_site_row(**{"Région": "Mon groupe"})],
        force_projects=True,
    )

    assert {"lakaa_id:EXT-1", "Mon groupe"} <= set(existing.tags.names())


def test_import_projects_force_updates_location(tmp_path, request, current_site):
    existing = make_project_on_site(
        request, name="Mon site", location="Ancienne adresse"
    )

    _import_sites(
        tmp_path,
        current_site,
        [_site_row(Adresse="Nouvelle adresse", **{"Coordonnées": "48.6921, 6.1844"})],
        force_projects=True,
    )

    existing.refresh_from_db()
    assert existing.location == "Nouvelle adresse"
    assert existing.location_y == pytest.approx(48.6921)
    assert existing.location_x == pytest.approx(6.1844)


def test_import_projects_does_not_update_location_without_force(
    tmp_path, request, current_site
):
    existing = make_project_on_site(
        request, name="Mon site", location="Adresse originale"
    )

    _import_sites(tmp_path, current_site, [_site_row(Adresse="Nouvelle adresse")])

    existing.refresh_from_db()
    assert existing.location == "Adresse originale"


def test_import_projects_matches_commune_by_city_name(tmp_path, current_site):
    commune = baker.make(
        Commune,
        department=baker.make(Department),
        name="Melun",
        postal="77000",
        insee="77288",
    )

    project_map, _ = _import_sites(tmp_path, current_site, [_site_row(Adresse="Melun")])

    assert Project.objects.get(pk=project_map["Mon site"]).commune == commune


def test_import_projects_matches_commune_by_postal_code_and_city(
    tmp_path, current_site
):
    commune = baker.make(
        Commune,
        department=baker.make(Department),
        name="Charleville-Mézières",
        postal="08000",
        insee="08105",
    )

    project_map, _ = _import_sites(
        tmp_path,
        current_site,
        [_site_row(Adresse="9 rue Bayard 08000 Charleville-Mézières")],
    )

    assert Project.objects.get(pk=project_map["Mon site"]).commune == commune


def test_import_projects_homonym_communes_resolved_by_coordinates(
    tmp_path, current_site
):
    department = baker.make(Department)
    saint_denis_93 = baker.make(
        Commune,
        department=department,
        name="Saint-Denis",
        postal="93200",
        insee="93066",
        latitude=48.936,
        longitude=2.357,
    )
    saint_denis_974 = baker.make(
        Commune,
        department=department,
        name="Saint-Denis",
        postal="97400",
        insee="97411",
        latitude=-20.879,
        longitude=55.448,
    )

    def _row(name, coordinates):
        return _site_row(
            Id=name,
            Nom=name,
            Adresse="Saint-Denis",
            **{"Id externe": name, "Coordonnées": coordinates},
        )

    project_map, _ = _import_sites(
        tmp_path,
        current_site,
        [_row("Site 93", "48.94,2.36"), _row("Site Réunion", "-20.88,55.45")],
    )

    assert Project.objects.get(pk=project_map["Site 93"]).commune == saint_denis_93
    assert (
        Project.objects.get(pk=project_map["Site Réunion"]).commune == saint_denis_974
    )


def test_import_projects_no_commune_match_leaves_commune_none(tmp_path, current_site):
    project_map, _ = _import_sites(
        tmp_path, current_site, [_site_row(Adresse="Ville introuvable")]
    )

    assert Project.objects.get(pk=project_map["Mon site"]).commune is None


def test_import_projects_falls_back_to_commune_centre(tmp_path, current_site):
    baker.make(
        Commune,
        department=baker.make(Department),
        name="Melun",
        postal="77000",
        insee="77288",
        latitude=48.54,
        longitude=2.66,
    )

    project_map, _ = _import_sites(
        tmp_path, current_site, [_site_row(Adresse="Melun", **{"Coordonnées": ","})]
    )

    project = Project.objects.get(pk=project_map["Mon site"])
    assert project.location_y == pytest.approx(48.54)
    assert project.location_x == pytest.approx(2.66)


def test_match_commune_postal_fallback_uses_coordinates():
    department = baker.make(Department)
    baker.make(
        Commune,
        department=department,
        name="Autre",
        postal="12345",
        insee="12001",
        latitude=44.0,
        longitude=2.0,
    )
    near = baker.make(
        Commune,
        department=department,
        name="Voisine",
        postal="12345",
        insee="12002",
        latitude=45.0,
        longitude=3.0,
    )

    assert import_lakaa._match_commune("1 rue X 12345 Inconnue", 45.01, 3.01) == near


def test_match_commune_without_coordinates_is_deterministic():
    department = baker.make(Department)
    first = baker.make(
        Commune, department=department, name="Doublon", postal="11111", insee="11001"
    )
    baker.make(
        Commune, department=department, name="Doublon", postal="22222", insee="22002"
    )

    assert import_lakaa._match_commune("Doublon") == first


def test_import_projects_idempotent(tmp_path, request, current_site):
    make_project_on_site(request, name="Mon site")

    _import_sites(tmp_path, current_site, [_site_row()])

    assert Project.objects.filter(name="Mon site").count() == 1


def test_import_projects_matches_renamed_site_by_lakaa_id(
    tmp_path, request, current_site
):
    existing = make_project_on_site(request)
    existing.tags.add("lakaa_site:22680")

    project_map, project_ids = _import_sites(
        tmp_path, current_site, [_site_row(Nom="Nouveau nom")]
    )

    assert project_map == {"Nouveau nom": existing.pk}
    assert project_ids == {"22680": existing.pk}
    assert not Project.objects.filter(name="Nouveau nom").exists()


def test_import_projects_matches_legacy_tag_and_adds_lakaa_id(
    tmp_path, request, current_site
):
    existing = make_project_on_site(request)
    existing.tags.add("lakaa_id:EXT-1")

    project_map, _ = _import_sites(
        tmp_path, current_site, [_site_row(Nom="Nouveau nom")]
    )

    assert project_map == {"Nouveau nom": existing.pk}
    assert "lakaa_site:22680" in existing.tags.names()


@pytest.mark.parametrize(
    "status,expected", [("TO_PROCESS", "READY"), ("IN_PROGRESS", "IN_PROGRESS")]
)
def test_import_projects_force_renames_and_moves_unprocessed_to_ready(
    tmp_path, request, current_site, status, expected
):
    existing = make_project_on_site(request)
    existing.tags.add("lakaa_site:22680")
    existing.project_sites.update(status=status)

    _import_sites(
        tmp_path, current_site, [_site_row(Nom="Nouveau nom")], force_projects=True
    )

    existing.refresh_from_db()
    assert existing.name == "Nouveau nom"
    assert existing.project_sites.get(site=current_site).status == expected


# ---------------------------------------------------------------------------
# _import_users
# ---------------------------------------------------------------------------


def _make_alice(organization=None):
    user = baker.make(
        User, username="alice@interieur.gouv.fr", email="alice@interieur.gouv.fr"
    )
    # baker.make(User) auto-creates a UserProfile via post_save signal
    user.profile.organization = organization
    user.profile.save(update_fields=["organization"])
    return user


def test_import_users_creates_user_on_site_with_organisation(tmp_path, current_site):
    _import_users(tmp_path, current_site, [_user_row()])

    user = User.objects.get(username="alice@interieur.gouv.fr")
    assert current_site in user.profile.sites.all()
    assert user.profile.organization.name == "Ministère de l'Intérieur"
    assert current_site in user.profile.organization.sites.all()


@pytest.mark.parametrize(
    "force,expected", [(True, "Ministère de l'Intérieur"), (False, "Ancienne")]
)
def test_import_users_updates_organisation_only_with_force(
    tmp_path, current_site, force, expected
):
    user = _make_alice(baker.make(Organization, name="Ancienne"))

    _import_users(tmp_path, current_site, [_user_row()], force=force)

    user.profile.refresh_from_db()
    assert user.profile.organization.name == expected


@pytest.mark.parametrize(
    "username,email",
    [
        ("Alice@Interieur.gouv.fr", "Alice@Interieur.gouv.fr"),
        ("alice.d", "alice@interieur.gouv.fr"),
    ],
)
def test_import_users_reuses_existing_account(tmp_path, current_site, username, email):
    existing = baker.make(User, username=username, email=email)

    _import_users(tmp_path, current_site, [_user_row()])

    assert User.objects.filter(email__iexact="alice@interieur.gouv.fr").count() == 1
    assert current_site in existing.profile.sites.all()


def test_import_users_matches_organisation_case_insensitively(tmp_path, current_site):
    org = baker.make(Organization, name="ggd meurthe")

    _import_users(tmp_path, current_site, [_user_row(organisation="GGD Meurthe")])

    assert Organization.objects.filter(name__iexact="ggd meurthe").count() == 1
    assert current_site in org.sites.all()


def test_import_users_grants_project_permissions(tmp_path, request, current_site):
    project = make_project_on_site(request)

    _import_users(
        tmp_path,
        current_site,
        [_user_row(**{"ID des sites": "42"})],
        project_ids={"42": project.pk},
    )

    user = User.objects.get(username="alice@interieur.gouv.fr")
    assert user.has_perm("projects.view_project", project)
    assert user.has_perm("projects.use_tasks", project)


def test_import_users_links_every_listed_site(tmp_path, request, current_site):
    p1, p2, other = (make_project_on_site(request) for _ in range(3))

    _import_users(
        tmp_path,
        current_site,
        [_user_row(**{"ID des sites": "1, 2"})],
        project_ids={"1": p1.pk, "2": p2.pk, "3": other.pk},
    )

    linked = set(ProjectMember.objects.values_list("project", flat=True))
    assert linked == {p1.pk, p2.pk}


def test_import_users_only_first_manager_is_owner(tmp_path, request, current_site):
    project = make_project_on_site(request)
    bob = "bob@interieur.gouv.fr"

    _import_users(
        tmp_path,
        current_site,
        [
            _user_row(**{"ID des sites": "42"}),
            _user_row(email=bob, **{"ID des sites": "42"}),
        ],
        project_ids={"42": project.pk},
    )

    assert ProjectMember.objects.filter(project=project, is_owner=True).count() == 1
    assert ProjectMember.objects.filter(project=project).count() == 2
    assert User.objects.get(username=bob).has_perm("projects.view_project", project)


@pytest.mark.parametrize(
    "role,is_owner",
    [
        ("store_manager", True),
        ("hq_manager", True),
        ("hq-manager", True),
        ("store_member", False),
        ("hq_member", False),
    ],
)
def test_import_users_owner_roles(tmp_path, request, current_site, role, is_owner):
    project = make_project_on_site(request)

    _import_users(
        tmp_path,
        current_site,
        [_user_row(role=role, **{"ID des sites": "42"})],
        project_ids={"42": project.pk},
    )

    assert ProjectMember.objects.get(project=project).is_owner is is_owner


def test_import_users_warns_on_unknown_site_id(tmp_path, current_site):
    cmd = _make_command()
    _import_users(
        tmp_path, current_site, [_user_row(**{"ID des sites": "999"})], cmd=cmd
    )

    assert "Unknown site id '999'" in cmd.stderr.getvalue()
    assert not ProjectMember.objects.exists()


# ---------------------------------------------------------------------------
# _import_realisations: pivoted schema, one row per (indicator, value) pair,
# sharing the same fixed metadata for a given "Identifiant de la déclaration".
# ---------------------------------------------------------------------------


@pytest.fixture
def declaration_prereqs(request):
    project = make_project_on_site(request, name="GGD Meurthe")
    resource = make_resource(request, title="Mettre en place le tri")
    user = baker.make(
        User, username="agent@interieur.gouv.fr", email="agent@interieur.gouv.fr"
    )
    return project, resource, user


def _import_declarations(tmp_path, site, rows, project=None, resource=None, cmd=None):
    path = _write_csv(tmp_path, "decl.csv", rows)
    cmd = cmd or _make_command()
    cmd._import_realisations(
        path,
        {project.name: project.pk} if project else {},
        {resource.title: resource.pk} if resource else {},
        site,
    )
    return cmd


@pytest.mark.parametrize(
    "completion,status",
    [("Incomplet", Realisation.DRAFT), ("Complet", Realisation.PUBLISHED)],
)
def test_import_realisations_maps_completion_to_status(
    tmp_path, current_site, declaration_prereqs, completion, status
):
    project, resource, _ = declaration_prereqs

    _import_declarations(
        tmp_path, current_site, [_decl_row(Completion=completion)], project, resource
    )

    assert Realisation.objects.get(project=project, resource=resource).status == status


def test_import_realisations_consolidates_multi_row_declaration(
    tmp_path, current_site, declaration_prereqs, settings, monkeypatch
):
    """A declaration spread across several CSV rows becomes a single Realisation."""
    settings.MEDIA_ROOT = str(tmp_path / "media")
    monkeypatch.setattr(import_lakaa, "_download", lambda url: b"%PDF-1.4")
    project, resource, user = declaration_prereqs
    metadata = {"Partenaires": "Metropole Grand Nancy", "Date de début": "15/11/2022"}

    _import_declarations(
        tmp_path,
        current_site,
        [
            _decl_row(
                "Description de votre action",
                "Tri sélectif installé sur 3 sites",
                **metadata,
            ),
            _decl_row("Sites concernés", "Caserne Roux, Lexy", **metadata),
            _decl_row(
                "Fichier (Word, PDF)",
                "http://invalid.test/justificatif.pdf",
                **metadata,
            ),
            _decl_row("Nombre d'agents bénéficiaires", "120", **metadata),
            _decl_row("Nombre de participants", "3", **metadata),
        ],
        project,
        resource,
    )

    r = Realisation.objects.get(project=project, resource=resource)
    assert r.description.startswith("<!-- lakaa:100 -->")
    assert "Tri sélectif installé sur 3 sites" in r.description
    assert r.location == "Caserne Roux, Lexy"
    assert r.key_figures == (
        "Nombre d'agents bénéficiaires: 120\nNombre de participants: 3"
    )
    assert r.partners == "Metropole Grand Nancy"
    assert r.date == date(2022, 11, 15)
    assert timezone.localtime(r.created_at).date() == date(2024, 2, 6)
    assert r.created_by == user
    assert r.documents.count() == 1


def test_import_realisations_long_site_field_kept_in_description(
    tmp_path, current_site, declaration_prereqs
):
    project, resource, _ = declaration_prereqs
    sites = "\n".join(f"Brigade de gendarmerie numéro {i}" for i in range(20))

    cmd = _import_declarations(
        tmp_path,
        current_site,
        [
            _decl_row("Description de votre action", "Tri des déchets"),
            _decl_row("Sites concernés", sites),
        ],
        project,
        resource,
    )

    r = Realisation.objects.get(project=project)
    assert len(r.location) <= 255
    assert r.location.endswith("…")
    assert "Tri des déchets" in r.description
    assert "**Sites concernés :**" in r.description
    assert "Brigade de gendarmerie numéro 19" in r.description
    assert "numéro 0  \nBrigade" in r.description
    assert "'Sites concernés' shortened" in cmd.stderr.getvalue()


def test_import_realisations_failed_download_is_left_out_then_retried(
    tmp_path, current_site, declaration_prereqs, settings, monkeypatch
):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    project, resource, _ = declaration_prereqs
    rows = [_decl_row(Images="https://example.test/a.png")]

    def _fail(url):
        raise OSError("boom")

    monkeypatch.setattr(import_lakaa, "_download", _fail)
    cmd = _import_declarations(tmp_path, current_site, rows, project, resource)

    assert not Realisation.objects.filter(project=project).exists()
    assert "will retry on the next run" in cmd.stderr.getvalue()

    monkeypatch.setattr(import_lakaa, "_download", lambda url: b"png-bytes")
    _import_declarations(tmp_path, current_site, rows, project, resource)

    realisation = Realisation.objects.get(project=project, resource=resource)
    assert realisation.photos.count() == 1


def test_import_realisations_idempotent(tmp_path, current_site, declaration_prereqs):
    project, resource, _ = declaration_prereqs

    for _ in range(2):
        _import_declarations(tmp_path, current_site, [_decl_row()], project, resource)

    assert Realisation.objects.filter(project=project, resource=resource).count() == 1


def test_import_realisations_warns_on_unknown_project(tmp_path, current_site):
    resource = baker.make(Resource, title="Mettre en place le tri")

    cmd = _import_declarations(tmp_path, current_site, [_decl_row()], resource=resource)

    assert "WARN" in cmd.stderr.getvalue()
    assert not Realisation.objects.exists()


def test_import_realisations_warns_on_unknown_resource(tmp_path, request, current_site):
    project = make_project_on_site(request, name="GGD Meurthe")

    cmd = _import_declarations(tmp_path, current_site, [_decl_row()], project=project)

    assert "WARN" in cmd.stderr.getvalue()
    assert not Realisation.objects.exists()


# ---------------------------------------------------------------------------
# Command entry point
# ---------------------------------------------------------------------------


def test_command_requires_site_domain(tmp_path):
    with pytest.raises(CommandError, match="--site-domain"):
        call_command("import_lakaa", data_dir=str(tmp_path))


def test_command_rejects_unknown_site_domain(tmp_path):
    with pytest.raises(CommandError, match="unknown.example.com"):
        call_command(
            "import_lakaa", site_domain="unknown.example.com", data_dir=str(tmp_path)
        )


def test_command_resolves_site_before_reading_files(tmp_path, current_site):
    with pytest.raises(CommandError, match="File not found"):
        call_command(
            "import_lakaa", site_domain=current_site.domain, data_dir=str(tmp_path)
        )


def test_command_runs_as_target_tenant(tmp_path, current_site, monkeypatch):
    """Outside a request, the command must enable the site's plugins itself,
    or the signal creating the DepafiProject profile is skipped."""
    baker.make(
        "home.SiteConfiguration", site=current_site, enabled_plugins=[PLUGIN_NAME]
    )
    sites_path = _write_csv(
        tmp_path, "Sites MI - CSV - 05.11.26.csv", [_site_row(Nom="GGD Meurthe")]
    )
    for filename in (
        "Actions MI - CSV - 05.11.2026.csv",
        "Utilisateurs MI – CSV - 05.11.26.csv",
        "Déclarations MI - CSV - 05.11.26.csv",
    ):
        (tmp_path / filename).touch()

    seen = {}

    def fake_import(self, site, *args):
        seen["enabled_plugins"] = list(get_enabled_plugins())
        seen["current_site"] = Site.objects.get_current()
        seen["project_map"], _ = self._import_projects(sites_path, site)

    monkeypatch.setattr(Command, "_import", fake_import)
    # Like a real management command: no request, so no plugin enabled yet
    set_enabled_plugins([])

    call_command(
        "import_lakaa", site_domain=current_site.domain, data_dir=str(tmp_path)
    )

    assert PLUGIN_NAME in seen["enabled_plugins"]
    assert seen["current_site"] == current_site
    project_pk = seen["project_map"]["GGD Meurthe"]
    assert DepafiProject.objects.filter(
        project_id=project_pk, site=current_site
    ).exists()
