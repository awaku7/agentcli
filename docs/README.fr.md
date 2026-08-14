<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Passerelle universelle pour l'IA</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Votre environnement, votre liberté.
</p>

<p align="center">
  Opérations sur les fichiers / Recherche web / Génération et analyse d'images / Extraction PDF et Excel / Contrôle IoT / Intégration MCP<br>
  24 providers / 3 interfaces utilisateur / Exécution d'outils parallèles / Marketplace Agent Skills
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Pourquoi uag ?

\*\* Libérez-vous de la dépendance vis-à-vis d'un fournisseur. \*\* La plupart des assistants IA vous lient à un fournisseur ou à un service cloud spécifique. uag est différent.

- **S'exécute localement** sur votre machine. Vos données restent avec vous (sauf les appels API que vous effectuez).
- **Liberté des fournisseurs** : OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... Plus de 15 fournisseurs, tous accessibles depuis une seule interface. Passez de l'un à l'autre en reconfigurant les variables d'environnement : pas de réinstallation, pas de migration.
- **229 outils** : E/S de fichiers, recherche sur le Web, génération d'images, Gmail, analyse de périphériques BLE, intégration de serveur MCP — **130 sont sécurisés en parallèle** (jusqu'à 8 s'exécutent simultanément via un pool de threads, configurables via `UAGENT_PARALLEL_WORKERS`). Lorsque le LLM déclenche plusieurs appels d'outil à la fois, uag les parallélise automatiquement.
- **3 interfaces utilisateur + A2A** : CLI, GUI, Web et protocole agent à agent. Même moteur, n’importe quelle interface.
- **Compétences d'agent** : installez des compétences développées par la communauté à partir du marché. Prolongez l'UAG à l'infini.

uag est **votre assistant IA selon vos conditions**. Pas lié à un fournisseur, pas lié à une interface, pas lié à une plateforme.

## Démarrage rapide

```bash
pip install uag
uag
```

Au premier lancement, l'assistant d'installation vous guide dans la configuration du fournisseur.
Voir [docs/ENVIRONMENT.md](ENVIRONMENT.md) pour toutes les variables d'environnement.

## Caractéristiques

### 🧠 Architecture multi-fournisseurs

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Tous les fournisseurs partagent le même ensemble d’outils et la même interface. Basculez en définissant « UAGENT_PROVIDER » — aucun changement de code, aucune installation séparée.

### ⚡ Exécution d'outils parallèles

Lorsque le LLM demande plusieurs outils simultanément, uag les **parallèle automatiquement**.
130 outils sont marqués « x_parallel_safe » et s'exécutent simultanément via un « ThreadPoolExecutor » (8 threads par défaut ; définissez « UAGENT_PARALLEL_WORKERS » pour changer).

**Exemple** : demandez « Vérifiez la météo dans les capitales nordiques » → LLM déclenche `search_web` × 5 pays → les 5 recherches s'exécutent en parallèle → résultats collectés en un seul lot.

Les outils en lecture seule (recherche de fichiers, calcul de hachage, liste de répertoires, traduction, requêtes de base de données, etc.) sont parallélisés de manière agressive.

### 🧩 Système de plugins (compatible Claude Code)

uagent implémente un **système de plugins compatible Claude Code**. Les plugins regroupent les compétences, les agents, les serveurs MCP, les hooks et bien plus encore dans des répertoires autonomes avec le manifeste `.claude-plugin/plugin.json`.

**Composants pris en charge** : compétences, sous-agents, serveurs MCP, hooks (12 événements de cycle de vie), commandes Slash, styles de sortie, userConfig, dépendances, canaux, marchés

**CLI commands**:

```
:plugin list                         # Liste des plugins installés
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Installer depuis le marché
:plugin remove <name>                # Désinstaller
:plugin enable/disable <name>        # Basculer
:plugin marketplace add/remove/list  # Gérer les places de marché
:plugin init <name>                  # Créer la structure d’un nouveau plugin
```

Consultez la documentation complète dans [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md).

### 🔄 Continuité des sessions

- **Changer de fournisseur en cours de session** : `UAGENT_PROVIDER` — l’historique des conversations est préservé.
- **Recharger les sessions passées** : `:load <index>` — reprenez là où vous vous êtes arrêté.

### 🛠 229 Outils

- **API cloud**: `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation.

| Catégorie | Outils |
|---|---|
| **Opérations sur les fichiers** | lecture/écriture/création/suppression/search/grep/hash/zip, file_type, parse_eml (fichiers .eml) |
| **Internet** | fetch_url, search_web, capture d'écran, browser_playwright |
| **Médias** | generate_image, analyse_image, img2img, audio_speech, audio_transcribe |
| **Documents** | Extraction PDF/PPTX/DOCX/RTF/ODT, extraction structurée Excel |
| **Prévision** | Prévision de séries temporelles avec 9 modèles (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, etc.), sélection automatique du modèle, génération de graphiques, i18n |
| **Communication** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook , **pybitchat** (BLE Mesh) — voir [COMMUNICATION.md](COMMUNICATION.md) and [BITCHAT.md](BITCHAT.md)|
| **IdO** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **Outils de développement** | workspace_status, git_ops, python_compile, lint_format, run_tests, db_query, **29 navigateurs de code source (famille idx)** |
| **MCP** | Connectez-vous à des serveurs MCP externes, répertoriez les outils, exécutez — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Communication agent à agent (avec d'autres instances uag ou des serveurs compatibles A2A) |
| **Système** | variables d'environnement, spécifications du système, heure, calcul de date, uuid_gen, slugify, quantities ||
| **Navigation source** | **29 outils idx** pour Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — obtenez un index de fonction/classe ou une définition spécifique sans lire l'intégralité du fichier |

#### Examen et couverture du référentiel

- `workspace_status`: Signalez la branche Git de l'espace de travail actif, les modifications, l'état de synchronisation en amont, le runtime Python et les marqueurs de projet courants sans modifier les fichiers.
- `git_review` : résume les modifications de Git, les fichiers à risque, les candidats de test et les résultats secrets sans exposer les valeurs secrètes.
- `security_scan` : analyse les fichiers du référentiel à la recherche de secrets probables et de fichiers de configuration à risque.
- `coverage_report` : exécute et normalise la couverture pour Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift et Dart/Flutter.
- Les dépendances de couverture manquantes peuvent être installées automatiquement lorsque l'exécution est demandée ; `dry_run` n'installe jamais de packages.

Voir [Outils d’analyse du dépôt](REPOSITORY_TOOLS.md) pour les paramètres, la sortie et les détails de sécurité.

### 🖥 4 interfaces + extension de code VS

| Mode | Commande | Objectif |
|---|---|---|
| **CLI** | `uag` | Fonctionnement rapide basé sur un terminal |
| **interface graphique** | `uagg` | Interface utilisateur de bureau via tkinter |
| **Internet** | `uagw` | Accès par navigateur |
| **Serveur A2A** | `ouaga` | Protocole Agent2Agent pour la communication multi-agents |
| **Code VS** | — | [Extension](VSCODE.md) avec panneau de discussion, explication, refactorisation, correction d'erreur et arborescence d'outils |

Voir [VSCODE.md](VSCODE.md) pour plus de détails sur l'extension VS Code — installation, commandes, raccourcis clavier et configuration.

### 🏠 Contrôle des appareils IoT

Voir [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Marché des compétences d'agent

`:skills mp_search` pour parcourir [SkillsMP](https://skillsmp.com) et [ClawHub](https://clawhub.ai) pour les compétences communautaires.
Installez et étendez les capacités d'uag à la volée.

### 🤖 Pilote automatique (`:auto`)

uag peut **poursuivre un objectif de manière autonome sur plusieurs cycles de LLM**. Parfait pour les tâches complexes en plusieurs étapes qui nécessitent un affinement itératif.

- **Comment ça marche** : chaque tour comporte une requête principale (étape A) suivie d'un jugement de l'examinateur (étape B) qui décide "TERMINER ou CONTINUER ?"
- **Même fournisseur, même API** : le jugement du réviseur utilise le même chemin de code que la requête principale, y compris la prise en charge de l'API Responses.
- **Juge séparé LLM** (facultatif) : définissez `UAGENT_AP_PROVIDER` pour utiliser un fournisseur/modèle différent pour l'évaluateur (par exemple, utilisez un modèle moins cher pour juger).
- **Quitter à tout moment** : appuyez sur la touche « x » pour arrêter immédiatement, même en pleine réponse. Ou laissez l'examinateur décider quand l'objectif est atteint.
- **Configurable** : `--max-rounds N` pour contrôler le budget.

Voir [README_AUTO.md](README_AUTO.md) pour une documentation complète.

### 🧩 Gestionnaire d'état par lots

uag peut suivre la progression des tâches multi-fichiers de longue durée. Lorsque le LLM traite des dizaines de fichiers, `batch_state` conserve la liste des fichiers en attente, terminés et ayant échoué sur le disque. Si la session se termine ou si un tour expire, l'exécution suivante reprend là où elle s'est arrêtée : rien n'est perdu.

### 🛡 Humain dans la boucle

`human_ask` permet au LLM de faire une pause et de vous demander votre confirmation avant d'effectuer des opérations destructrices (suppression de fichiers, écrasements, commandes shell). Vous gardez le contrôle.

### 🛑 Interruption (touche C / bouton Stop)

Arrêtez la génération de réponse LLM à tout moment et réinjectez une commande d'arrêt dans le LLM.

| Interfaces | Comment interrompre |
|---|---|
| **CLI** | Appuyez sur la touche « c » pendant le streaming LLM — la réponse en cours s'arrête et « Stop » est envoyé sous forme de message utilisateur afin que le LLM réponde en conséquence |
| **INTERFACE INTERIEUR WEB** | Cliquez sur le bouton rouge \*\* ■ Arrêter \*\* (apparaît automatiquement pendant le traitement LLM) |
| **Interface graphique de bureau** | Cliquez sur le bouton rouge \*\*\*\*\*\* (apparaît automatiquement pendant le traitement LLM) |

L'interruption fonctionne comme une « injection rapide » : au lieu de simplement abandonner, elle renvoie « Stop » au LLM sous forme de message utilisateur, lui permettant de conclure ou d'accuser réception de l'interruption en douceur.

Appuyez sur la touche « x » pour quitter le mode pilote automatique (voir [README_AUTO.md](README_AUTO.md)).

### 🕵️ Automatisation du navigateur et inspecteur Web

Deux outils complémentaires basés sur Playwright :

- **browser_playwright** : automatisez de vraies sessions de navigateur : naviguez, cliquez, remplissez des formulaires, extrayez des données, gérez des flux multipages. Fonctionne sans tête ou avec tête.
- **playwright_inspector** : enregistrez les transitions du navigateur, capturez des instantanés et des captures d'écran DOM à chaque étape. Utile pour déboguer les interactions Web ou auditer les modifications de page au fil du temps.

### 🔄 Chargement dynamique des outils

`tool_catalog` et `tool_load` vous permettent de découvrir et d'activer des outils au moment de l'exécution.
Pas besoin de tout charger au démarrage : activez uniquement ce dont vous avez besoin, quand vous en avez besoin.

### 🦀 Rust Native Tools

### 🌐i18n/L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / et plus encore.
Définissez `UAGENT_LANG` pour changer. Voir [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) pour ajouter de nouveaux paramètres régionaux.

Les traductions de ce README sont disponibles dans [docs/README.translations.md](README.translations.md).

### 🔒 Variables d'environnement cryptées

Stockez les clés et les secrets API dans « .env.sec » – un fichier « .env » crypté.
Gérez avec `uag_envsec`.

## Configuration et détails

- **Variables d'environnement** : [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Assistant d'installation** : `python -m uagent.setup_cli`
- **Env crypté** : `uag_envsec` — crypte `.env` en `.env.sec`
- **API Réponses** : définissez `UAGENT_RESPONSES=1` pour le mode API Réponses (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Activé automatiquement pour Sakana AI (Fugu).
- **Documents pour développeurs** : [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Flux d'outils**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Petits conseils LLM** : [SLM_TIPS.md](SLM_TIPS.md)

## Philosophie du projet

uag aspire à être **votre IA, sur votre machine, selon vos conditions.**

- Aucune dépendance SaaS - fonctionne localement
- Pas de dépendance vis-à-vis d'un fournisseur : changez à tout moment
- Pas de verrouillage de l'interface utilisateur - CLI / GUI / Web / A2A
- Pas de verrouillage de fonctionnalités - étendez-vous avec des outils et des compétences

Une expérience d’agent IA gratuite, sans dépendance vis-à-vis d’un fournisseur.

### ✨ Créez vos propres outils

[fr.md](TOOL_CREATOR_GUIDE.fr.md)
Consultez le guide étape par étape ici.

## Contribuer

Les contributions sont les bienvenues ! Rapports de bogues, suggestions de fonctionnalités, améliorations de la documentation, traductions et demandes d'extraction : tout est apprécié.

- **Issues**: Ouvrez un problème GitHub pour des bogues ou des demandes de fonctionnalités.
- **Demandes d'extraction** : Forkez le dépôt, effectuez vos modifications et soumettez une PR. Consultez [DEVELOP.md](../src/uagent/docs/DEVELOP.md) pour la configuration du développement et les directives.

Realtime Voix et AEC3

## Le mode vocal Realtime prend en charge les entrées/sorties de microphone et de haut-parleur en duplex intégral. Si le backend AEC3 est manquant, uag installe automatiquement pywebrtc-audio.

**Fournisseurs en temps réel** : OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice et Amazon Bedrock Nova Sonic. Le SDK de diffusion bidirectionnelle de Bedrock est installé automatiquement uniquement lorsque Bedrock est sélectionné.

```bat
python scheck.py realtime
```

AEC3 utilise le signal réel du microphone (proche) et l'audio réellement envoyé au haut-parleur (loin). Activez les diagnostics uniquement lors de l’investigation de problèmes audio.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime prend en charge une intégration Function Calling à sécurité limitée. L’adaptateur actuel expose automatiquement la fonction get_current_time en lecture seule. Les outils destructeurs et les contrôles d'appareils nécessitent une liste d'autorisation et un flux de confirmation explicites. Grok realtime utilise un adaptateur distinct et n'utilise pas ce chemin Function Calling spécifique à OpenAI.

## Architecture et invariants opérationnels

Consultez [ARCHITECTURE.md](ARCHITECTURE.md) pour connaître les contrats d’implémentation durables couvrant le cycle de vie A2A, les contextes I18N, l’installation des dépendances facultatives, la sécurité des outils, les capacités des fournisseurs, les limites de confiance OAuth, les événements structurés et la vérification d’acceptation.

## Enterprise Policy Engine

Enterprise Policy Engine supports organization-level rules for tools, providers, credentials, MCP servers, networks, skills, and plugins. Configure `UAGENT_POLICY_FILE` with a JSON/YAML policy file. See [ENTERPRISE_POLICY.md](ENTERPRISE_POLICY.md) for examples, roles, confirmation, and allowlists.

### Runtime recovery and orchestration

See [RESTART_RECOVERY.md](RESTART_RECOVERY.md) / [DAG_SCHEDULER.md](DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](MULTI_AGENT_RUNTIME.md) for durable recovery, dependency-aware execution, multi-agent orchestration, and remote A2A usage.
