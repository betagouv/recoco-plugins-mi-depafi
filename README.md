# Plugin MI-DEPAFI pour Recommandations Collaboratives

Plugin pour [Recommandations Collaboratives](https://github.com/betagouv/recommandations-collaboratives) développé pour la Direction de l'Évaluation de la Performance, de l'Achat, des Finances et de l'Immobilier (DEPAFI) du Ministère de l'Intérieur.

## Contexte

La DEPAFI anime un réseau national d'environ 400 référents transition écologique répartis sur l'ensemble du territoire. Ces référents accompagnent le déploiement d'actions liées au développement durable (tri des déchets, rénovation, mobilités, etc.) au sein des différentes entités du ministère : Police nationale, Gendarmerie nationale, administrations territoriales de l'État (ATE) et services déconcentrés.

Ce plugin étend Recommandations Collaboratives pour permettre aux référents de partager leurs retours d'expérience directement sur la plateforme, dans une logique d'accompagnement de projets.

## Fonctionnalités

### Réalisations

Chaque référent peut déclarer une action réalisée dans le cadre d'un dossier. Une réalisation comprend :

- **Action réalisée** : la fiche ressource associée à l'action mise en œuvre
- **Partenaires** : les organismes partenaires impliqués
- **Description** : un compte-rendu détaillé de l'action
- **Photos** : une galerie illustrant la réalisation

Une réalisation peut être enregistrée en brouillon ou publiée.

## Installation

```bash
uv pip install -e recoco-plugins-mi-depafi
```

Ajouter `plugin_mi_depafi` à `INSTALLED_APPS` dans les paramètres du portail (ie: fichier `recoco/settings/development.py`), puis exécuter la migration :

```bash
python manage.py migrate_tenant --schema=<schema_du_portail> plugin_mi_depafi
```

Enfin, activer le plugin dans l'administration via la `SiteConfiguration` du portail concerné en ajoutant `"plugin_mi_depafi"` à la liste `enabled_plugins`.

## Import depuis Lakaa

Le plugin fournit une commande de migration pour importer les données de l'ancienne plateforme Lakaa (utilisateurs, sites → dossiers, fiches-actions → ressources, déclarations → réalisations).

### Prérequis

L'export Lakaa doit contenir trois fichiers `.xlsx` dans un même répertoire :

| Fichier (nom par défaut) | Contenu |
|---|---|
| `202606090733-users.xlsx` | Utilisateurs |
| `202606090732-sites.xlsx` | Sites (→ Dossiers) |
| `202606091433-reports.xlsx` | Déclarations (→ Réalisations) |

### Lancement

```bash
uv run python manage.py import_lakaa \
  --site-domain <domaine_du_portail> \
  --data-dir /chemin/vers/les/exports/
```

Les noms de fichiers par défaut peuvent être surchargés avec `--users-file`, `--sites-file` et `--reports-file`.

Passer `--skip-images` pour ignorer le téléchargement des photos (utile pour un test à blanc).

### Ce que la commande importe, dans l'ordre

1. **Catégories et ressources** — les 50 fiches-actions uniques sont extraites des déclarations et créées comme `Resource`, regroupées par thématique (`Category`).
2. **Dossiers** — chaque site Lakaa devient un `Project` rattaché au portail cible, avec ses métadonnées géographiques (`Région`, `Zone de défense`, `Périmètre`, `Niveau`) stockées en tags.
3. **Utilisateurs** — créés avec l'e-mail comme identifiant et un mot de passe inutilisable (à réinitialiser via l'envoi d'un e-mail). Les `Responsable - Site` deviennent propriétaires de leur dossier.
4. **Réalisations et photos** — chaque déclaration est importée comme `Realisation` ; les champs quantitatifs spécifiques à Lakaa sont repliés dans la description en Markdown. Les photos sont téléchargées depuis `storage.lakaa.io` et attachées en tant que `RealisationPhoto`.

### Idempotence

La commande peut être relancée sans risque de doublon :

- **Dossiers** : identifiés par nom + site Django.
- **Utilisateurs** : identifiés par e-mail (`username`).
- **Réalisations** : un marqueur `<!-- lakaa:<id> -->` en tête de description sert de clé d'unicité.
- **Photos** : ignorées si des photos existent déjà sur la réalisation.

## Points d'attention

### Jeton CSRF et HTMX (`realisation_modal.html`)

Le fragment `plugin_mi_depafi/fragments/realisation_modal.html` injecte manuellement le jeton CSRF dans les en-têtes HTMX via une lecture du cookie `csrftoken` en JavaScript :

```js
document.body.addEventListener('htmx:configRequest', (event) => {
    const token = document.cookie.match(/csrftoken=([^;]+)/)?.[1];
    if (token) event.detail.headers['X-CSRFToken'] = token;
});
```

Cette approche est un contournement temporaire. Deux pistes pour la résoudre proprement :

- Configurer HTMX globalement (via un méta-tag `hx-headers` sur le `<body>`) au niveau du gabarit de base du cœur de Recommandations Collaboratives.
- Intégrer [`django-htmx`](https://github.com/adamchainz/django-htmx) dans le cœur, qui gère automatiquement l'injection du jeton CSRF et expose des utilitaires côté Django pour détecter les requêtes HTMX.
