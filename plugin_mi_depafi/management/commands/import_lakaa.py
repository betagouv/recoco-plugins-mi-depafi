"""
Import data from a Lakaa CSV export into Recommandations Collaboratives.

Import order (respects FK dependencies):
  1. Categories + Resources  (Actions MI - CSV.csv)
  2. Projects                (Sites MI - CSV.csv)
  3. Users                   (Utilisateurs MI - CSV.csv, site links derived from declarations)
  4. Réalisations             (Déclarations MI - CSV.csv)

All objects are scoped to the target Django Site given by --site-domain.
The command is idempotent: re-running it skips already-imported objects.
"""

import csv
import os
import re
import urllib.request
from datetime import datetime

from tqdm import tqdm

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import CommandError
from django.utils import timezone

from recoco.apps.home.models import SiteConfiguration, UserProfile
from recoco.apps.plugins.management.base import TenantCommand
from recoco.apps.projects.models import Project, ProjectMember, ProjectSite
from recoco.apps.resources.models import Category, Resource

from plugin_mi_depafi.models import Realisation, RealisationDocument, RealisationPhoto

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _extract_pdf_urls(text):
    """Return (cleaned_text, list_of_pdf_urls) by pulling PDF URLs out of text."""
    pdf_urls = []

    def _replace(m):
        url = m.group(0).rstrip(".,;)")
        if url.lower().endswith(".pdf"):
            pdf_urls.append(url)
            return ""
        return m.group(0)

    cleaned = _URL_RE.sub(_replace, text or "").strip()
    return cleaned, pdf_urls

# Sentinel values that Lakaa uses to mean "no data"
_EMPTY = {"n.a", "-", "n.a.", "", None}

# Organisation suffix appended to all names in the Lakaa export
_ORG_SUFFIX = " - Ministère de l'Intérieur"

# Mapping from Lakaa thematic prefix → (color, icon)
_THEME_STYLE = {
    "1.": ("green", "bi-person-raised-hand"),
    "2.": ("blue", "bi-bicycle"),
    "3.": ("orange", "bi-building"),
    "4.": ("yellow", "bi-droplet"),
    "5.": ("violet", "bi-laptop"),
    "6.": ("green", "bi-tree"),
}


def _val(v):
    """Return None if value is a Lakaa empty sentinel, else strip strings."""
    if v is None:
        return None
    s = str(v).strip()
    return None if s in _EMPTY else s


def _strip_org(s):
    """Remove the Lakaa organisation suffix from names."""
    if not s:
        return s
    return s.removesuffix(_ORG_SUFFIX).strip()


def _aware(dt):
    """Make a naive datetime timezone-aware (UTC). Returns None if dt is None."""
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return dt
    return timezone.make_aware(dt)


def _parse_dt(s):
    """Parse Lakaa CSV datetime strings: '2024-05-16 07:13:20 UTC' or '2022-11-15'."""
    if not _val(s):
        return None
    s = s.strip().removesuffix(" UTC")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return _aware(datetime.strptime(s, fmt))
        except ValueError:
            continue
    return None


def _parse_date(s):
    """Parse a date string in d/m/Y or Y-m-d format; return a date object or None."""
    if not _val(s):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _load_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _theme_style(theme_name):
    for prefix, style in _THEME_STYLE.items():
        if (theme_name or "").startswith(prefix):
            return style
    return ("blue", "bi-star")


class Command(TenantCommand):
    help = "Import a Lakaa CSV data export (actions, sites, users, declarations) into the target site"

    def get_schema(self, options):
        domain = options["site_domain"]
        try:
            site_config = SiteConfiguration.objects.select_related("site").get(
                site__domain=domain
            )
        except SiteConfiguration.DoesNotExist:
            raise CommandError(f"No SiteConfiguration found for '{domain}'")
        if not site_config.schema_name:
            raise CommandError(
                f"SiteConfiguration for '{domain}' has no schema_name — "
                "enable at least one plugin to auto-generate it"
            )
        # Cache the Site object here, before TenantCommand.execute() changes
        # search_path to the tenant schema — querying django_site afterwards
        # could resolve to a shadowed table in the tenant schema.
        self._site = site_config.site
        return site_config.schema_name

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--site-domain",
            required=True,
            help="Domain of the target Django Site (e.g. depafi.recoconseil.fr)",
        )
        parser.add_argument(
            "--data-dir",
            required=True,
            help="Directory containing the Lakaa CSV files",
        )
        parser.add_argument(
            "--actions-file",
            default="Actions MI - CSV.csv",
            help="Filename of the actions export inside --data-dir",
        )
        parser.add_argument(
            "--sites-file",
            default="Sites MI - CSV.csv",
            help="Filename of the sites export inside --data-dir",
        )
        parser.add_argument(
            "--users-file",
            default="Utilisateurs MI - CSV.csv",
            help="Filename of the users export inside --data-dir",
        )
        parser.add_argument(
            "--reports-file",
            default="Déclarations MI - CSV.csv",
            help="Filename of the declarations export inside --data-dir",
        )

    def handle(self, **options):
        data_dir = options["data_dir"]
        site = self._site  # fetched in get_schema(), before search_path changed

        actions_path = os.path.join(data_dir, options["actions_file"])
        sites_path = os.path.join(data_dir, options["sites_file"])
        users_path = os.path.join(data_dir, options["users_file"])
        reports_path = os.path.join(data_dir, options["reports_file"])

        for path in (actions_path, sites_path, users_path, reports_path):
            if not os.path.exists(path):
                raise CommandError(f"File not found: {path}")

        self.stdout.write(f"Target site: {site.name} ({site.domain})")

        self.stdout.write("\n[1/4] Importing categories and resources (actions)…")
        resource_map = self._import_resources(actions_path, site)

        self.stdout.write("\n[2/4] Importing projects (sites)…")
        project_map = self._import_projects(sites_path, site)

        self.stdout.write("\n[3/4] Importing users…")
        self._import_users(users_path, project_map, reports_path, site)

        self.stdout.write("\n[4/4] Importing réalisations (declarations)…")
        self._import_realisations(reports_path, project_map, resource_map)

        self.stdout.write(self.style.SUCCESS("\nImport complete."))

    # ------------------------------------------------------------------
    # Phase 1 — Resources (from dedicated Actions CSV)
    # ------------------------------------------------------------------

    def _import_resources(self, actions_path, site):
        rows = _load_csv(actions_path)
        resource_map = {}  # action name (stripped) → Resource pk
        created_cat = created_res = skipped_res = 0

        for row in rows:
            name = _strip_org(_val(row.get("Nom Forest")) or "")
            topic = _strip_org(_val(row.get("topic")) or "")
            if not name:
                continue

            color, icon = _theme_style(topic)
            cat, cat_new = Category.objects.get_or_create(
                name=topic,
                defaults={"color": color, "icon": icon},
            )
            if cat_new:
                cat.sites.add(site)
                created_cat += 1
            elif site not in cat.sites.all():
                cat.sites.add(site)

            resource = Resource.objects.filter(title=name, sites=site).first()
            if resource is None:
                # description = short intro HTML; body = full how-to HTML.
                # Both are stored as-is: inline HTML is valid in Markdown fields.
                content = _val(row.get("description")) or _val(row.get("body")) or name
                subtitle = _val(row.get("external name")) or ""
                resource = Resource.objects.create(
                    title=name,
                    subtitle=subtitle,
                    category=cat,
                    content=content,
                    status=Resource.PUBLISHED,
                    site_origin=site,
                )
                resource.sites.add(site)
                created_res += 1
            else:
                skipped_res += 1

            resource_map[name] = resource.pk

        self.stdout.write(
            f"  Categories: {created_cat} created  |  "
            f"Resources: {created_res} created, {skipped_res} skipped"
        )
        return resource_map

    # ------------------------------------------------------------------
    # Phase 2 — Projects (Lakaa "sites")
    # ------------------------------------------------------------------

    def _import_projects(self, sites_path, site):
        rows = _load_csv(sites_path)
        project_map = {}  # site name → Project pk
        created = skipped = 0

        for row in rows:
            name = _strip_org(_val(row.get("name")) or _val(row.get("external id")) or str(row["id"]))
            ext_id = _val(row.get("external id")) or name

            existing = Project.objects.filter(name=name, project_sites__site=site).first()
            if existing is not None:
                project_map[name] = existing.pk
                skipped += 1
                continue

            desc_parts = []
            if _val(row.get("address")):
                desc_parts.append(f"**Adresse :** {_val(row['address'])}")

            project = Project.objects.create(
                name=name,
                description="\n\n".join(desc_parts),
                created_on=_parse_dt(row.get("created at")) or timezone.now(),
                updated_on=timezone.now(),
            )
            ProjectSite.objects.create(
                project=project, site=site, is_origin=True, status="TO_PROCESS"
            )
            project.sites.add(site)

            tags = [f"lakaa_id:{ext_id}"]
            if _val(row.get("group")):
                tags.append(_strip_org(row["group"]))
            project.tags.add(*tags)

            project_map[name] = project.pk
            created += 1

        self.stdout.write(f"  Projects: {created} created, {skipped} skipped")
        return project_map

    # ------------------------------------------------------------------
    # Phase 3 — Users
    # ------------------------------------------------------------------

    def _import_users(self, users_path, project_map, reports_path, site):
        # Derive user → site associations from declarations (creator email → store name)
        user_sites: dict[str, set[str]] = {}
        for row in _load_csv(reports_path):
            email = (_val(row.get("Email du déclarant")) or "").lower()
            site_name = _strip_org(row.get("Nom de l'établissement") or "")
            if email and site_name:
                user_sites.setdefault(email, set()).add(site_name)

        rows = _load_csv(users_path)
        created = skipped = 0

        for row in rows:
            email = (row.get("email") or "").strip().lower()
            if not email:
                continue

            user, user_new = User.objects.get_or_create(
                username=email,
                defaults={
                    "email": email,
                    "first_name": row.get("first name") or "",
                    "last_name": row.get("last name") or "",
                },
            )
            if user_new:
                user.set_unusable_password()
                user.save(update_fields=["password"])
                created += 1
            else:
                skipped += 1

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.sites.add(site)

            role = row.get("role") or ""
            is_owner = role in ("store_manager", "hq_manager")

            for site_name in user_sites.get(email, set()):
                project_pk = project_map.get(site_name)
                if project_pk is None:
                    continue
                ProjectMember.objects.get_or_create(
                    member=user,
                    project_id=project_pk,
                    defaults={"is_owner": is_owner},
                )

        self.stdout.write(f"  Users: {created} created, {skipped} skipped")

    # ------------------------------------------------------------------
    # Phase 4 — Réalisations (declarations)
    # ------------------------------------------------------------------

    def _import_realisations(self, reports_path, project_map, resource_map):
        rows = _load_csv(reports_path)
        created = skipped = warn = 0

        for row in tqdm(rows, desc="Réalisations", unit="décl", file=self.stdout):
            lakaa_id = row.get("Identifiant de la déclaration") or ""
            site_name = _strip_org(row.get("Nom de l'établissement") or "")
            action_name = _strip_org(row.get("Nom de l'action") or "")

            project_pk = project_map.get(site_name)
            resource_pk = resource_map.get(action_name)

            if project_pk is None:
                self.stderr.write(
                    f"  [WARN] No project for store '{site_name}' (decl {lakaa_id})"
                )
                warn += 1
                continue
            if resource_pk is None:
                self.stderr.write(
                    f"  [WARN] No resource for action '{action_name}' (decl {lakaa_id})"
                )
                warn += 1
                continue

            sentinel = f"<!-- lakaa:{lakaa_id} -->"
            if Realisation.objects.filter(
                project_id=project_pk,
                resource_id=resource_pk,
                description__startswith=sentinel,
            ).exists():
                skipped += 1
                continue

            completion = (row.get("Completion") or "").strip()
            status = Realisation.DRAFT if completion == "Incomplet" else Realisation.PUBLISHED

            indicateurs = _val(row.get("Indicateurs")) or ""
            valeurs_raw = _val(row.get("Valeurs")) or ""
            key_figures, pdf_urls = _extract_pdf_urls(valeurs_raw)
            description = sentinel
            if indicateurs:
                description = f"{sentinel}\n\n{indicateurs}"

            creator_email = (_val(row.get("Email du déclarant")) or "").lower()
            creator = User.objects.filter(username=creator_email).first()

            realisation = Realisation.objects.create(
                project_id=project_pk,
                resource_id=resource_pk,
                created_by=creator,
                partners=_val(row.get("Partenaires")) or "",
                site=_val(row.get("Sites concernés")) or "",
                date=_parse_date(row.get("Date de début")),
                description=description,
                key_figures=key_figures,
                status=status,
            )

            declared_on = _parse_dt(row.get("Déclaré le"))
            if declared_on:
                Realisation.objects.filter(pk=realisation.pk).update(created_at=declared_on)

            images_raw = _val(row.get("Images")) or ""
            for order, url in enumerate(u.strip() for u in images_raw.split(",") if u.strip()):
                try:
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        data = resp.read()
                    filename = url.rsplit("/", 1)[-1]
                    photo = RealisationPhoto(realisation=realisation, order=order)
                    photo.image.save(filename, ContentFile(data), save=True)
                except Exception as exc:
                    self.stderr.write(f"  [WARN] Could not download image {url}: {exc}")

            for order, url in enumerate(pdf_urls):
                try:
                    with urllib.request.urlopen(url, timeout=10) as resp:
                        data = resp.read()
                    filename = url.rsplit("/", 1)[-1]
                    doc = RealisationDocument(realisation=realisation, order=order)
                    doc.file.save(filename, ContentFile(data), save=True)
                except Exception as exc:
                    self.stderr.write(f"  [WARN] Could not download document {url}: {exc}")

            created += 1

        self.stdout.write(
            f"  Réalisations: {created} created, {skipped} skipped, {warn} warnings"
        )
