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
