# uag (uagent)

uag est un agent d'exécution d'outils polyvalent qui s'exécute dans votre environnement local. Il interagit avec les utilisateurs via une interface de ligne de commande (CLI) et effectue diverses tâches telles que des opérations sur les fichiers, des recherches sur le Web et l'exécution de scripts Python selon les instructions.

## Caractéristiques Principales

- **Opérations sur les fichiers locaux** : Lecture, écriture, édition et recherche de fichiers.
- **Récupération d'informations** : Recherche Web avec DuckDuckGo et extraction du contenu des pages Web.
- **Exécution de code** : Exécution sécurisée de scripts Python et de commandes PowerShell.
- **Traitement multimédia** : Génération d'images, lecture de fichiers PDF/PPTX, captures d'écran.
- **Prise en charge multilingue** : Prend en charge plusieurs langues, dont le français, le japonais et l'anglais.
- **Prise en charge MCP (Model Context Protocol)** : Peut se connecter à des serveurs MCP externes pour étendre ses fonctions.

## Installation

Vous pouvez l'installer avec pip depuis PyPI :

```bash
pip install uag
```

Lors de la première exécution, un assistant de configuration démarrera automatiquement.

## Démarrage Rapide

Après l'installation, tapez simplement la commande suivante pour commencer :

```bash
uag
```

Une fois lancé, vous pouvez demander à l'agent des choses comme :
- "Lis le README dans le répertoire actuel et résume son contenu."
- "Recherche sur le Web les dernières nouvelles sur l'IA et fais-en un résumé."
- "Compresse tous les fichiers PNG du dossier 'images' dans un fichier ZIP."

## Configuration (Variables d'environnement)

Le comportement de uag peut être configuré via des variables d'environnement. Pour plus de détails, consultez :
- [ENVIRONMENT.md (English)](ENVIRONMENT.md)

## Documentation

- [README.md (English)](README.md)
- [README.ja.md (Japanese)](README.ja.md)

## Licence

Publié sous la licence Apache 2.0.
