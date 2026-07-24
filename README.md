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

Le plugin fournit une commande de migration pour importer les données de l'ancienne plateforme Lakaa (fiches-actions → ressources, sites → dossiers, utilisateurs, déclarations → réalisations).

### Prérequis

L'export Lakaa doit contenir quatre fichiers `.csv` dans un même répertoire :

| Fichier (nom par défaut) | Contenu |
|---|---|
| `Actions MI - CSV.csv` | Fiches-actions (→ Ressources) |
| `Sites MI - CSV.csv` | Sites (→ Dossiers) |
| `Utilisateurs MI - CSV.csv` | Utilisateurs |
| `Déclarations MI - CSV.csv` | Déclarations (→ Réalisations) |

### Lancement

```bash
uv run python manage.py import_lakaa \
  --site-domain <domaine_du_portail> \
  --data-dir /chemin/vers/les/exports/
```

Les noms de fichiers par défaut peuvent être surchargés avec `--actions-file`, `--sites-file`, `--users-file` et `--reports-file`.

Par défaut, une fois un objet importé (ressource, dossier, utilisateur), les relances de la commande le laissent intact. Les options `--force-update-resources`, `--force-update-projects`, `--force-update-orgs` et `--force-update-users` permettent de forcer la mise à jour de certains champs sur les objets déjà existants (voir le détail dans `--help`).

### Ce que la commande importe, dans l'ordre

1. **Catégories et ressources** (`[1/4]`) — chaque ligne du fichier Actions devient une `Resource`, regroupée par thématique (`Category`) déduite du préfixe du thème.
2. **Dossiers** (`[2/4]`) — chaque site Lakaa devient un `Project` rattaché au portail cible, avec sa commune (déduite de l'adresse), ses coordonnées, et son groupe/organisation.
3. **Utilisateurs** (`[3/4]`) — créés avec l'e-mail comme identifiant (`username`) et un mot de passe inutilisable (à réinitialiser via l'envoi d'un e-mail). Le rattachement aux dossiers est déduit des déclarations ; les rôles `store_manager`/`hq_manager` deviennent propriétaires (`is_owner`) de leur(s) dossier(s).
4. **Réalisations** (`[4/4]`) — les lignes du fichier Déclarations sont regroupées par `Identifiant de la déclaration` (une déclaration peut être pivotée sur plusieurs lignes, une par indicateur) puis importées comme `Realisation` ; les indicateurs chiffrés sont repliés dans `key_figures`. Les photos et documents (PDF) référencés sont téléchargés et attachés en tant que `RealisationPhoto` / `RealisationDocument`.

### Idempotence

La commande peut être relancée sans risque de doublon :

- **Ressources** : identifiées par titre + site ; mises à jour uniquement avec `--force-update-resources`.
- **Dossiers** : identifiés par nom + site ; mis à jour uniquement avec `--force-update-projects`.
- **Organisations** : identifiées par nom ; le groupe n'est écrasé que si absent ou avec `--force-update-orgs`.
- **Utilisateurs** : identifiés par e-mail (`username`) ; mis à jour uniquement avec `--force-update-users`.
- **Réalisations** : un marqueur `<!-- lakaa:<id> -->` en tête de description sert de clé d'unicité — une déclaration déjà importée est entièrement ignorée (y compris ses photos/documents), sans option pour la forcer.

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
