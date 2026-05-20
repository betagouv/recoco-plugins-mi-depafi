# Plugin MI-DEPAFI pour Recommandations Collaboratives

Plugin pour [Recommandations Collaboratives](https://github.com/betagouv/recommandations-collaboratives) développé pour la Direction de l'Évaluation de la Performance, de l'Achat, des Finances et de l'Immobilier (DEPAFI) du Ministère de l'Intérieur.

## Contexte

La DEPAFI anime un réseau national d'environ 400 référents transition écologique répartis sur l'ensemble du territoire. Ces référents accompagnent le déploiement d'actions liées au développement durable (tri des déchets, rénovation, mobilités, etc.) au sein des différentes entités du ministère : Police nationale, Gendarmerie nationale, administrations territoriales de l'État (ATE) et services déconcentrés.

Ce plugin étend Recommandations Collaboratives pour permettre aux référents de partager leurs retours d'expérience directement sur la plateforme, dans une logique d'accompagnement de projets.

## Fonctionnalités

### Réalisations

Chaque référent peut déclarer une action réalisée dans le cadre d'un dossier. Une réalisation comprend :

- **Action réalisée** — la fiche ressource associée à l'action mise en œuvre
- **Partenaires** — les organismes partenaires impliqués
- **Description** — un compte-rendu détaillé de l'action
- **Photos** — une galerie illustrant la réalisation

Une réalisation peut être enregistrée en brouillon ou publiée.

## Installation

```bash
uv add recoco-plugin-mi-depafi
```

Ajouter `plugin_mi_depafi` à `INSTALLED_APPS` dans les paramètres du portail, puis exécuter la migration :

```bash
python manage.py migrate_tenant --schema=<schema_du_portail> plugin_mi_depafi
```

Enfin, activer le plugin dans l'administration via la `SiteConfiguration` du portail concerné en ajoutant `"plugin_mi_depafi"` à la liste `enabled_plugins`.
