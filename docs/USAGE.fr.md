# UTILISATION (Options de ligne de commande)

Ce document décrit les options de ligne de commande disponibles pour les points d'entrée uag.

______________________________________________________________________

## Points d'entrée

| Commande | Module Python | Interface |
|---|---|---|
| `uag` | `python -m uagent` | CLI (boucle stdin) |
| `uagg` | `python -m uagent.gui` | Interface graphique (tkinter) |
| `uagw` | `python -m uagent.web` | Serveur Web (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | Serveur A2A HTTP |

______________________________________________________________________

## Options de démarrage de la CLI (`uag`)

### `--workdir` / `-C <chemin>`

Répertoire de travail. S'il n'est pas défini, le programme utilise par défaut la variable d'environnement `UAGENT_WORKDIR`, puis le répertoire courant.
Le répertoire est créé s'il n'existe pas.

### `--tool-genre-mask <int>`

Masque de bits de genre d'outil. Lorsqu’il est fourni, l’invite de sélection interactive du genre est ignorée.

| Bit | Genre | Description |
|-----|-------|-------------|
| 1 | basic | Outils essentiels de gestion de fichiers et de chat |
| 2 | comm | Outils de communication (Bluesky, Teams) |
| 4 | office | Outils de suite bureautique (Excel, PDF, PPTX) |
| 8 | devel | Outils de développement (git, lint, compilation) |
| 16 | iot | Outils pour périphériques IoT (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Outils d'exécution de commandes |
| 64 | external | Outils de plugins externes |
| 128 | media | Génération et analyse d'images/d'audio |
| 256 | file | Outils de gestion de fichiers |
| 512 | index | Outils de navigation dans les sources/index |
| 1024 | dev | Outils de développement et de gestion de dépôts |
| 2048 | web | Outils Web et de navigation |
| 4096 | utility | Outils utilitaires et d’assistance |
| 8191 | all | Tous les outils |

Exemples :

```
uag --tool-genre-mask 1 # basique uniquement
uag --tool-genre-mask 9 # basique + développement (1 + 8)
uag --tool-genre-mask 8191    # tous les outils
```

### `--use-tool` / `--no-use-tool`

Active ou désactive l'envoi des définitions d'outils vers le LLM. Remplace la variable d’environnement `UAGENT_USE_TOOL`.

- `--use-tool` force l’envoi des outils.
- `--no-use-tool` désactive l’envoi des outils.

Lorsqu’il est désactivé, le LLM ne reçoit aucune définition d’outil et ne peut appeler aucun outil.

### `--computer-use` / `--no-computer-use`

Active ou désactive l’utilisation de l’ordinateur. Remplace la variable d’environnement `UAGENT_COMPUTER_USE`.

### `--inject-message` / `-M <message>`

Injecte un message dans le LLM au démarrage et se ferme une fois l’opération terminée. Cela implique l’option `--non-interactive`.

### `--embedded`

Mode intégré pour les déploiements soumis à des contraintes ou où la reproductibilité est essentielle.

- Désactive le magasin de sessions.
- Masque les outils de gestion des outils (`tool_catalog`, `tool_load`, `unload_tool`) sauf s’ils sont explicitement activés.
- Ignore `--tool-genre-mask` ; utilisez `--enable-tool` pour le chargement explicite d’un outil.

### `--enable-tool <nom>`

Charge explicitement un outil au démarrage. L’option peut être répétée, et les noms séparés par des virgules sont également acceptés.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

L'ordre spécifié est conservé et se reflète dans l'ordre des outils présenté à LLM. Les outils activés explicitement sont protégés contre le déchargement automatique.

### `--plugin-dir <chemin>`

Charger les plugins à partir du répertoire spécifié. Cette option peut être répétée.

______________________________________________________________________

## Options réservées à l’interface en ligne de commande

### `--inject-message-auto <options-de-objectif>`

Lance le mode pilote automatique à partir d’un objectif injecté non interactif. La valeur utilise les mêmes options que `:auto` ; mettez la valeur complète entre guillemets lorsqu’elle contient des options.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Trier les éléments --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Trier les éléments --infinite"
```

Le mode normal suit le chemin de décision du réviseur. Définissez `UAGENT_AUTO_SENTINEL=1` pour activer le mode sentinelle à LLM unique. Dans ce mode, la cible LLM doit terminer chaque réponse par exactement l’un des éléments suivants :

- `<AUTO_CONTINUE>` — lancer un autre tour
- `<AUTO_COMPLETE>` — terminer avec succès

Des marqueurs manquants ou invalides arrêtent le pilotage automatique en toute sécurité. Cela exécute toujours le `LLM` cible ; cela évite simplement l’appel supplémentaire au `LLM` de révision.

### `--non-interactive`

Mode non interactif. Ne lance pas la boucle stdin. Si un chemin d’accès à un fichier est fourni en tant qu’argument positionnel, il est traité et le programme se termine immédiatement.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Options du serveur Web (`uagw`)

### `--host <address>`

Adresse de liaison pour le serveur Web (par défaut : `127.0.0.1`, pouvant être remplacée par `UAGENT_WEB_HOST`).

Par défaut, le serveur Web n'écoute que sur localhost (`127.0.0.1`). Pour le rendre accessible depuis d'autres machines du réseau, utilisez `--host 0.0.0.0`.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Sélectionne les genres d’outils à l’aide du même masque de bits que celui décrit ci-dessus. Lorsque cette option est spécifiée, l’invite interactive relative au genre est ignorée.

### `--use-tool` / `--no-use-tool`

Active ou désactive l’envoi des définitions d’outils vers le LLM. Remplace `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Active ou désactive l’utilisation de l’ordinateur. Remplace `UAGENT_COMPUTER_USE`.

### `--no-frontend`

Exécute uniquement API sans modèles HTML ni fichiers frontaux statiques.

### `--embedded`

Désactive le stockage des sessions et masque les outils de gestion des outils (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Options du serveur A2A (`uaga`)

### `--host <address>`

Adresse de liaison pour le serveur A2A HTTP (par défaut : `0.0.0.0`, peut être remplacée par `UAGENT_A2A_HOST`).

### `--port <nombre>`

Numéro de port du serveur A2A HTTP (par défaut : `8765`, peut être remplacé par `UAGENT_A2A_PORT`).

### `--reload`

Active le rechargement à chaud lors des modifications du code (par défaut : désactivé, peut être redéfini par `UAGENT_A2A_RELOAD`).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Sélectionne les genres d'outils à l'aide du masque de bits décrit ci-dessus. Lorsqu’il est spécifié, l’invite interactive de sélection du genre est ignorée.

### `--use-tool` / `--no-use-tool`

Active ou désactive l’envoi des définitions d’outils vers le LLM. Remplace `UAGENT_USE_TOOL`.

### `--computer-use` / `--no-computer-use`

Active ou désactive l’utilisation de l’ordinateur. Remplace `UAGENT_COMPUTER_USE`.

### `--embedded`

Désactive le magasin de sessions et masque les outils de gestion des outils (`tool_catalog`, `tool_load`, `unload_tool`).

______________________________________________________________________

## Variables d’environnement associées

| Variable | Description |
|---|---|
| `UAGENT_PROVIDER` | Nom du fournisseur LLM (obligatoire au démarrage) |
| `UAGENT_*_API_KEY` | Clé API pour le fournisseur sélectionné |
| `UAGENT_WORKDIR` | Répertoire de travail par défaut |
| `UAGENT_WEB_HOST` | Adresse de liaison du serveur Web (par défaut : `127.0.0.1`) |
| `UAGENT_A2A_HOST` | Adresse de liaison du serveur A2A (par défaut : `0.0.0.0`) |
| `UAGENT_A2A_PORT` | Port du serveur A2A (par défaut : `8765`) |
| `UAGENT_A2A_RELOAD` | Activer le rechargement à chaud de A2A par défaut |
| `UAGENT_USE_TOOL` | Désactiver les outils lorsque la valeur est définie sur `0`, `false`, `no` ou `off` |
| `UAGENT_COMPUTER_USE` | Activer ou désactiver l’utilisation de l’ordinateur par défaut |
| `UAGENT_SESSION_STORE` | Active ou désactive le stockage des sessions ; le mode intégré impose la valeur `0` |
| `UAGENT_PLUGIN_DIRS` | Répertoires de recherche supplémentaires pour les plugins |
| `UAGENT_AUTO_SENTINEL` | Active le mode sentinelle « single-LLM » en pilote automatique lorsque la valeur est définie sur `1` |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Nombre maximal d'appels consécutifs à des outils récents (par défaut : `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Nombre maximal de cycles LLM/outil par opération utilisateur (par défaut : `200`) |
| `UAGENT_SHRINK_CNT` | Seuil facultatif de réduction automatique des messages (`0`/non défini = désactivé) |
| `UAGENT_SHRINK_KEEP_LAST` | Nombre de messages à conserver après la réduction (par défaut : `20`) |
| `UAGENT_LANG` | Langue de l'interface (`ja`, `en`, etc.) |

Pour la liste complète des variables d'environnement, voir [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Exemples

### Démarrage minimal avec OpenAI

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Ollama local avec uniquement les outils de base

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Serveur Web sur toutes les interfaces

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

ou

```
uagw --host 0.0.0.0
```

### Serveur A2A sur localhost avec un port personnalisé

```
uaga --host 127.0.0.1 --port 8080
```

### Désactiver les outils pour un petit modèle

```
uag --no-use-tool --tool-genre-mask 1
```

### Traitement de fichiers non interactif

```
uag --non-interactive README.md
```
