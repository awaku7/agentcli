<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Passerelle universelle pour l'IA</h1>

<p align="center">
 <b>U</b>universal <b>A</b>I <b>G</b>ateway — Votre environnement, votre liberté.
</p>

<p align="center">
 Opérations de fichiers / Recherche Web / Génération et analyse d'images / Extraction PDF et Excel / Contrôle IoT / Intégration MCP<br>
 24 fournisseurs / 3 interfaces utilisateur / Exécution d'outils parallèles / Agent Marché des compétences
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Lisez ceci dans votre langue</a>
</p>

______________________________________________________________________

## Pourquoi uag ?

**Libérez-vous de la dépendance vis-à-vis d'un fournisseur.** La plupart des assistants IA vous lient à un fournisseur ou à un service cloud spécifique. uag est différent.

- **S'exécute localement** sur votre machine. Vos données restent avec vous (sauf API appels que vous passez).
- **Liberté du fournisseur** : OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 fournisseurs, tous accessibles depuis une seule interface. Échangez entre eux en reconfigurant les variables d'environnement — pas de réinstallation, pas de migration.
- **222 outils** : E/S de fichiers, recherche sur le Web, génération d'images, Gmail, analyse de périphériques BLE, intégration du serveur MCP — **130 sont marqués statiquement comme parallèles sécurisés** (jusqu'à 8 s'exécutent simultanément via un pool de threads, configurable via `UAGENT_PARALLEL_WORKERS`). Lorsque le LLM déclenche plusieurs appels d'outils à la fois, uag les parallélise automatiquement.
- **3 interfaces utilisateur + A2A** : CLI, GUI, Web et protocole agent à agent. Même moteur, n'importe quelle interface.
- **Prêt pour l'IoT** : SwitchBot, ECHONET Lite, Matter, UPnP — contrôlez vos appareils domestiques via l'IA.
- **Compétences d'agent** : installez des compétences développées par la communauté à partir du marché. Prolongez uag à l'infini.

uag est **votre assistant IA selon vos conditions**. Non lié à un fournisseur, non lié à une interface, non lié à une plate-forme.

## Démarrage rapide

```bash
pip install uag
uag
```

Lors du premier lancement, l'assistant d'installation vous guide dans la configuration du fournisseur.
Voir [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) pour toutes les variables d'environnement.

## Computer Use

Computer Use est opt-in et prend en charge à la fois un environnement d'exécution de navigateur Playwright visible
et un environnement d'exécution de bureau. Lorsqu'il est activé, les deux environnements d'exécution sont créés et enregistrés ;

```bat
set UAGENT_COMPUTER_USE=1
```

Utilisez `desktop` pour sélectionner le runtime de bureau du système d'exploitation à la place. Les ressources Runtime sont
fermées ensemble lors de la sortie normale, de `Ctrl-C` et de l'arrêt du processus. Définissez
`UAGENT_COMPUTER_HEADLESS=1` pour les tests CI ou de fumée basés sur un navigateur.
Voir [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
pour les détails d'intégration et de sécurité.

## Realtime Voice et AEC3

Le mode vocal en temps réel prend en charge OpenAI Realtime, Azure OpenAI GPT Realtime, xAI Grok Voice API, Google Gemini Multimodal Live API et Amazon Bedrock Nova Sonic avec microphone duplex intégral et E/S de haut-parleur. Le backend AEC3 `pywebrtc-audio` requis est installé automatiquement, et le SDK de streaming bidirectionnel facultatif de Bedrock est installé automatiquement uniquement lorsque le fournisseur Bedrock est sélectionné :

```bash
python scheck.py realtime
```

Le pipeline AEC3 reçoit le signal du microphone réel (`near`) et l'audio réellement transmis au haut-parleur (`far`) afin que l'assistant puisse écouter pendant parlant. Activez les diagnostics uniquement lors de l'enquête sur les problèmes audio :

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Appel de fonction en temps réel

OpenAI Realtime prend en charge une intégration d'appel de fonction à sécurité limitée. L'adaptateur temps réel actuel expose automatiquement « get_current_time » en lecture seule. Les outils destructeurs et les contrôles de périphériques ne sont pas exposés sans une liste d'autorisation et un flux de confirmation explicites. Grok realtime utilise un adaptateur distinct et n'utilise pas ce chemin d'appel de fonction spécifique à OpenAI.

## Fonctionnalités

### 🧠 Architecture multi-fournisseurs

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / lama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Tous les fournisseurs partagent le même ensemble d'outils et la même interface. Basculez en définissant `UAGENT_PROVIDER` — aucun changement de code, aucune installation séparée.

#### Ollama et llama.cpp

Ollama et llama.cpp sont des fournisseurs distincts. Ollama utilise son propre service et sa propre gestion de modèles, tandis que `llama.cpp` se connecte à un point de terminaison compatible `llama-server` OpenAI :

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

#llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

Le fournisseur llama.cpp utilise le chemin compatible avec Chat Completions. Gardez `UAGENT_RESPONSES=0` sauf si un proxy compatible est configuré.

### ⚡ Exécution d'outils parallèles

Lorsque le LLM demande plusieurs outils simultanément, uag **les parallélise automatiquement**.
130 outils sont marqués statiquement `x_parallel_safe` et s'exécutent simultanément via un `ThreadPoolExecutor` (8 threads par par défaut ; définissez `UAGENT_PARALLEL_WORKERS` pour changer).

**Exemple** : Demandez "Vérifier la météo dans les capitales nordiques" → LLM déclenche `search_web` × 5 pays → les 5 recherches s'exécutent en parallèle → résultats collectés en un seul lot.

Le décompte actuel est basé sur des modules d'outils qui définissent un `TOOL_SPEC` (actuellement 222, y compris les 2 outils soutenus par Rust dans `src/uagent/tools_rust/`). `http_request` utilise une sécurité sensible aux méthodes : les appels `GET`/`HEAD`/`OPTIONS` peuvent s'exécuter en parallèle, tandis que les méthodes d'écriture restent en série.

Les outils en lecture seule (recherche de fichiers, calcul de hachage, liste de répertoires, traduction, requêtes de base de données, etc.) sont parallélisés de manière agressive.

### 🧩 Système de plugins (compatible avec le code Claude)

uagent implémente un **Claude Système de plugin compatible avec le code**. Les plugins regroupent les compétences, les agents, les serveurs MCP, les hooks et bien plus encore dans des répertoires autonomes avec un manifeste `.claude-plugin/plugin.json`.

**Composants pris en charge** : compétences, sous-agents, serveurs MCP, hooks (12 événements de cycle de vie), commandes Slash, styles de sortie, userConfig, dépendances, canaux, marchés

**CLI commandes**:

```
:plugin list # Liste des plugins installés
:plugin install <source> [--scope] # Installer (dir/zip/git/http)
:plugin install <name>@<marketplace> # Installer depuis le marché
:plugin supprimer <name> # Désinstaller
:plugin activer/désactiver <name> # Basculer
:plugin marketplace ajouter/supprimer/list # Gérer places de marché
:plugin init <name> # Scaffold new plugin
```

Voir [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) pour une documentation complète.

### 🔄 Continuité de session

- **Changer de fournisseur à mi-session** avec `UAGENT_PROVIDER` — historique des conversations est préservé.
- **Rechargez les sessions passées** avec `:load <index>` — reprenez là où vous vous êtes arrêté.
- **La mise en cache des résultats de l'outil** évite une réexécution redondante lorsque le même appel d'outil se répète.

### 🛠 229 Outils

| Catégorie | Outils |
|---|---|
| **Opérations sur les fichiers** | lecture/écriture/création/suppression/search/grep/hash/zip, file_type, parse_eml (fichiers .eml), `path_alias` |
| **Web** | fetch_url, search_web, capture d'écran, browser_playwright, `url_alias`, `public_transit_route` ([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **Médias** | generate_image, analyse_image, img2img, audio_speech, audio_transcribe |
| **Documents** | Extraction PDF/PPTX/DOCX/RTF/ODT, extraction structurée Excel |
| **Prévision** | Prévision de séries chronologiques avec 9 modèles (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), sélection automatique de modèles, génération de tracés, i18n |
| **Communication** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) — voir [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) et [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IdO** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **API Cloud** | `aws_api`, `gcp_api`, `azure_api` – opérations génériques AWS, Google Cloud et Azure API ; les opérations d'écriture nécessitent une confirmation explicite |
| **Outils de développement** | workspace_status, git_ops, git_review, security_scan, cover_report, python_compile, lint_format, run_tests, db_query, **29 navigateurs de code source (famille idx)** |
| **MCP** | Connectez-vous aux serveurs MCP externes, répertoriez les outils, exécutez — [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Communication d'agent à agent (avec d'autres instances uag ou serveurs compatibles A2A) |
| **Système** | variables d'environnement, spécifications du système, heure, calcul de date, [quantités](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Navigation source** | **29 outils idx** pour Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — obtenez un index de fonction/classe ou une définition spécifique sans lire l'intégralité du fichier |

#### Examen et couverture du référentiel

- `workspace_status` : signale la branche Git de l'espace de travail actif, les modifications, état de synchronisation en amont, runtime Python et marqueurs de projet courants sans modifier les fichiers.
- `git_review` : résume les modifications de Git, les fichiers à risque, les candidats aux tests et les résultats secrets sans exposer les valeurs secrètes.
- `security_scan` : analyse les fichiers du référentiel à la recherche de secrets probables et de fichiers de configuration à risque.
- `coverage_report` : exécute et normalise la couverture pour Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift et Dart/Flutter.
- Les dépendances de couverture manquantes peuvent être installées automatiquement lorsque l'exécution est demandée ; `dry_run` n'installe jamais de packages.

Voir [Outils d'analyse du référentiel](docs/REPOSITORY_TOOLS.md) pour les paramètres, les sorties et les détails de sécurité.

Voir [Alias de chemin et d'URL](docs/PATH_URL_ALIASES.md) pour raccourcir les chemins de fichiers et les URL répétés dans les arguments de l'outil.

### 🖥 4 Interfaces + VS Code Extension

| Mode | Commande | Objectif |
|---|---|---|
| **CLI** | `uag` | Fonctionnement rapide basé sur un terminal |
| **GUI** | `uagg` | Interface utilisateur de bureau via tkinter |
| **Web** | `uagw` | Accès par navigateur |
| **A2A Serveur** | `ouaga` | Protocole Agent2Agent pour la communication multi-agents |
| **Code VS** | — | [Extension](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) avec panneau de discussion, explication, refactorisation, correction des erreurs et arborescence des outils |

Voir [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) pour plus de détails sur l'extension VS Code - installation, commandes, raccourcis clavier et configuration.

### 🏠 Contrôle des appareils IoT

- **BACnet** : lecture/écriture des appareils BACnet/IP (CVC, éclairage, compteurs d'énergie). Abonnement COV pour les notifications push
- **Modbus TCP** : Registres et bobines de maintien/entrée en lecture/écriture. Surveillance des modifications basée sur les interrogations
- **OPC UA** : parcourir l'espace d'adressage, lire/écrire des variables, s'abonner aux modifications de données
- **SwitchBot** : contrôle par lots dans le cloud et analyse/contrôle BLE. Abonnement basé sur des sondages
- **ECHONET Lite** : Découvrez, contrôlez et abonnez-vous aux notifications INF des appareils électroménagers (AC, lumières, chauffe-eau, etc.)
- **Matter** : Contrôle de lecture/écriture + abonnement d'attribut pour la surveillance des changements d'état
- **UPnP** : Découverte d'appareils et redirection de port IGD

Voir [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` pour parcourir [SkillsMP](https://skillsmp.com) et [ClawHub](https://clawhub.ai) pour la communauté compétences.
Installez et étendez les capacités de uag à la volée.

### 🤖 Pilote automatique (`:auto`)

uag peut **poursuivre de manière autonome un objectif sur plusieurs tours LLM**. Parfait pour les tâches complexes en plusieurs étapes qui nécessitent un raffinement itératif.

- **Comment ça marche** : chaque cycle comporte une requête principale (étape A) suivie d'un jugement du réviseur (étape B) qui décide "TERMINER ou CONTINUER ?"
- **Même fournisseur, même API** : Le jugement du réviseur utilise le chemin de code identique à la requête principale, y compris la prise en charge des réponses API.
- **Juge séparé LLM** (facultatif) : définissez `UAGENT_AP_PROVIDER` pour utiliser un fournisseur/modèle différent pour le réviseur (par exemple, utilisez un modèle moins cher pour juger).
- **Quitter à tout moment** : appuyez sur la touche F11 pour arrêter immédiatement, même en cours de réponse. Ou laissez le réviseur décider quand l'objectif est atteint.
- **Configurable** : `--max-rounds N` pour contrôler le budget.

Voir [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) pour une documentation complète.

### 🧩 État du lot Manager

uag peut suivre la progression des tâches multi-fichiers de longue durée. Lorsque le LLM traite des dizaines de fichiers, `batch_state` conserve la liste des fichiers en attente, terminés et ayant échoué sur le disque. Si la session se termine ou si un tour expire, l'exécution suivante reprend là où elle s'est arrêtée — rien n'est perdu.

### 🛡 Human-in-the-Loop

`human_ask` permet au LLM de faire une pause et de demander votre confirmation avant d'effectuer des opérations destructrices (suppression de fichiers, écrasements, commandes shell). Vous gardez le contrôle.

### 🛑 Interruption (touche C / bouton Stop)

Arrêtez la génération de réponse LLM à tout moment et réinjectez une commande d'arrêt au LLM.

| Interfaces | Comment interrompre |
|---|---|
| **CLI** | Appuyez sur la touche « c » pendant le streaming de LLM — la réponse actuelle s'arrête et « « Stop » » est envoyé sous forme de message utilisateur afin que le LLM réponde en conséquence |
| **INTERFACE INTERIEUR WEB** | Cliquez sur le bouton rouge **weight Stop** (apparaît automatiquement pendant le traitement LLM) |
| **Bureau GUI** | Cliquez sur le bouton rouge \*\*\*\*\*\*\*\* (apparaît automatiquement pendant le traitement de LLM) |

L'interruption fonctionne comme une « injection rapide » : au lieu de simplement abandonner, elle renvoie « Stop » au LLM sous forme de message utilisateur, lui permettant de conclure ou d'accuser réception de l'interruption en douceur.

Appuyez sur la touche « x » pour quitter le mode pilote automatique (voir [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Automatisation du navigateur et Web Inspector

Deux outils complémentaires basés sur Playwright :

- **browser_playwright** : automatisez de vraies sessions de navigateur - naviguer, cliquer, remplir formulaires, extraire des données, gérer des flux multipages. Fonctionne sans tête ou avec tête.
- **playwright_inspector** : enregistrez les transitions du navigateur, capturez des instantanés et des captures d'écran DOM à chaque étape. Utile pour déboguer les interactions Web ou auditer les modifications de page au fil du temps.

### 🔄 Le chargement dynamique des outils

`tool_catalog` et `tool_load` vous permettent de découvrir et d'activer les outils au moment de l'exécution.
Pas besoin de tout charger au démarrage — activez uniquement ce dont vous avez besoin, quand vous en avez besoin.

### 🦀 Rust Native Tools

`uuid_gen` et `slugify` sont implémentés dans Rust (via PyO3) pour plus de performances.
Ils se chargent directement à partir d'un `.pyd` pré-construit — **aucune `pip install` requise**.

Les développeurs externes peuvent également fournir des outils basés sur Rust : placez un `.pyd` à côté du
wrapper `.py`, utilisez `load_rust_pyd()` de `uagent.tools.rust_helper`, et
les utilisateurs obtiennent l'outil sans aucune dépendance supplémentaire. Voir
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文/ 한국어 / Español / Français / Русский / et plus encore.
Définissez `UAGENT_LANG` pour changer. Voir [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) pour ajouter une nouvelle langue.

Les traductions de ce README sont disponibles dans [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variables d'environnement cryptées

Stockez les clés et les secrets API dans `.env.sec` — un fichier `.env` crypté.
Gérez avec `uag_envsec`.

## Configuration et détails

- **Variables d'environnement** : [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Assistant de configuration** : `python -m uagent.setup_cli`
- **Env chiffré** : `uag_envsec` — chiffrer `.env` comme `.env.sec`
- **Réponses API** : définissez `UAGENT_RESPONSES=1` pour le mode Réponses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Activé automatiquement pour Sakana AI (Fugu).
- **Documents pour développeurs** : [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Flux d'outils** : [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — comment les outils sont envoyés aux LLM (masque de genre, tool_catalog, GPT-5.4+ natif tool_search)
- **Petits conseils LLM** : [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Philosophie du projet

uag aspire à être **votre IA, sur votre machine, selon vos conditions.**

- Aucune dépendance SaaS - s'exécute localement
- Pas de verrouillage de fournisseur - changez à tout moment
- Pas de verrouillage de l'interface utilisateur - CLI / GUI / Web / A2A
- Pas de verrouillage de fonctionnalités - étendez-vous avec des outils et des compétences

A expérience d'agent IA gratuite, sans dépendance à un fournisseur.

### ✨ Créez vos propres outils

Écrire un nouvel outil pour uag est simple : créez un seul fichier `.py` avec
`TOOL_SPEC` et `run_tool()`, placez-le dans `UAGENT_EXTERNAL_TOOLS_DIR`, et
il est immédiatement disponible. Pour les développeurs Rust, fournissez un `.pyd` prédéfini avec
zéro dépendance supplémentaire pour les utilisateurs.

Voir [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
pour le guide étape par étape.

## Contribuer

Les contributions sont les bienvenues ! Rapports de bogues, suggestions de fonctionnalités, améliorations de la documentation, traductions et demandes d'extraction - tous appréciés.

- **Problèmes** : ouvrez un problème GitHub pour les bogues ou les demandes de fonctionnalités.
- **Demandes d'extraction** : créez le dépôt, apportez vos modifications et soumettez un PR. Voir [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) pour la configuration et les directives de développement.
- **Traductions** : les traductions README et les ajouts de paramètres régionaux sont les bienvenus. Voir [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Outils et compétences** : de nouveaux plugins d'outils et compétences d'agent peuvent être contribués via le marché.

### Vérifications de développement (avant PR)

Installez d'abord les dépendances de test uniquement. Ils sont conservés en dehors de la liste des dépendances d'exécution :

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

Exécutez les mêmes vérifications utilisées par GitHub Actions avant de pousser :

```bash
python -m ruff check src tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Pour une itération locale plus rapide, exécutez uniquement les tests concernés :

```bash
pytest -q tests/<affected_area>
```

Vérifications supplémentaires lorsque pertinent :

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Après les modifications des paramètres régionaux (`.po`) : `python scripts/compile_locales.py` et `python scripts/po_qc_summary.py`.

Runtime politique (détails dans [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1) : les assistants augmentent au lieu de `sys.exit` ; l'hôte de l'outil transforme l'outil `SystemExit`/`Exception` en chaînes d'erreur afin qu'un seul outil ne puisse pas tuer le processus. Les sorties rapides et sans échec au démarrage restent intentionnelles.

## Architecture et invariants opérationnels

Voir [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) pour les contrats durables couvrant le cycle de vie A2A, les contextes I18N, l'installation facultative des dépendances, la sécurité des outils, les capacités du fournisseur, les limites de confiance OAuth, les événements structurés et la vérification de l'acceptation.

## Enterprise Policy Engine

Les politiques au niveau de l'organisation pour les outils, les fournisseurs, les informations d'identification, les serveurs MCP, les réseaux, les compétences et les plugins sont prises en charge. Définissez `UAGENT_POLICY_FILE` sur un fichier de stratégie JSON/YAML ; voir [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) pour des exemples de configuration, des rôles, des confirmations et des listes autorisées.

### Runtime récupération et orchestration

Voir [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) pour une récupération durable, une exécution tenant compte des dépendances, une orchestration multi-agents et une utilisation à distance de A2A.

Voir [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) pour la coordination des baux leaders à exécution partagée.
