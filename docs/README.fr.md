<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="logo uag" width="720">
</p>

<h1 align="center">uag — Passerelle universelle AI</h1>

<p align="center">
  <b>U</b>universal <b>A</b>I <b>G</b>ateway — Votre environnement, votre liberté.
</p>

<p align="center">
  Opérations de fichiers/Recherche Web/Génération et analyse d'images/Extraction PDF et Excel/Contrôle IoT/Intégration MCP<br>
  Plus de 15 fournisseurs / 3 interfaces utilisateur / Exécution d'outils parallèles / Marché des compétences d'agent
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Lisez ceci dans votre langue</a>
</p>

---

## Pourquoi uag ?

** Libérez-vous de la dépendance vis-à-vis d'un fournisseur. ** La plupart des assistants IA vous lient à un fournisseur ou à un service cloud spécifique. uag est différent.

- **S'exécute localement** sur votre machine. Vos données restent avec vous (sauf les appels API que vous effectuez).
- **Liberté des fournisseurs** : OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... Plus de 15 fournisseurs, tous accessibles depuis une seule interface. Passez de l'un à l'autre en reconfigurant les variables d'environnement : pas de réinstallation, pas de migration.
- **112 outils** : E/S de fichiers, recherche sur le Web, génération d'images, analyse de périphériques BLE, intégration de serveur MCP — et **66 sont parallel-safe (jusqu'à 4 simultanément)**. Lorsque le LLM déclenche plusieurs appels d'outil à la fois, uag les exécute automatiquement via un pool de threads.
- **3 interfaces utilisateur + A2A** : CLI, GUI, Web et protocole agent à agent. Même moteur, n’importe quelle interface.
- **Prêt pour l'IoT** : SwitchBot, ECHONET Lite, Matter, UPnP — contrôlez vos appareils domestiques via l'IA.
- **Compétences d'agent** : installez des compétences développées par la communauté à partir du marché. Prolongez l'UAG à l'infini.

uag est **votre assistant IA selon vos conditions**. Pas lié à un fournisseur, pas lié à une interface, pas lié à une plateforme.

## Démarrage rapide

```bash
pip install uag
uag
```

Au premier lancement, l'assistant d'installation vous guide dans la configuration du fournisseur.
Voir [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) pour toutes les variables d'environnement.

## Fonctionnalités

### 🧠 Architecture multi-fournisseurs

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

Tous les fournisseurs partagent le même ensemble d’outils et la même interface. Basculez en définissant « UAGENT_PROVIDER » — aucun changement de code, aucune installation séparée.

### ⚡ Exécution d'outils parallèles

Lorsque le LLM demande plusieurs outils simultanément, uag les **parallèle automatiquement**.
55 outils sont marqués « x_parallel_safe » et s'exécutent simultanément via un « ThreadPoolExecutor » à 4 threads.

**Exemple** : demandez « Vérifiez la météo dans les capitales nordiques » → LLM déclenche `search_web` × 5 pays → les 5 recherches s'exécutent en parallèle → résultats collectés en un seul lot.

Les outils en lecture seule (recherche de fichiers, calcul de hachage, liste de répertoires, traduction, requêtes de base de données, etc.) sont parallélisés de manière agressive.

### 🔄 Continuité des sessions

- **Changer de fournisseur en cours de session** avec `UAGENT_PROVIDER` — l'historique des conversations est préservé.
- **Rechargez les sessions passées** avec `:load <index>` — reprenez là où vous vous étiez arrêté.
- La **mise en cache des résultats de l'outil** évite une réexécution redondante lorsque le même appel d'outil se répète.

### 🛠 112 Outils

| Catégorie | Outils |
|---|---|
| **Opérations sur les fichiers** | lire/écrire/créer/supprimer/search/grep/hash/zip |
| **Internet** | fetch_url, search_web, capture d'écran, browser_playwright |
| **Médias** | generate_image, analyse_image, img2img, audio_speech, audio_transcribe |
| **Documents** | Extraction PDF/PPTX/DOCX/RTF/ODT, extraction structurée Excel |
| **IdO** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP |
| **Outils de développement**, ****11 outils idx** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — obtenez un index de fonctions/classes ou une définition spécifique sans lire tout le fichier** | git_ops, python_compile, lint_format, run_tests, db_query, ****11 outils idx** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — obtenez un index de fonctions/classes ou une définition spécifique sans lire tout le fichier** |
| **MCP** | Connectez-vous à des serveurs MCP externes, répertoriez les outils, exécutez |
| **A2A** | Communication agent à agent (avec d'autres instances uag ou des serveurs compatibles A2A) |
| **Système** | variables d'environnement, spécifications du système, heure, calcul de date |
| **Navigation dans le code** | **11 outils idx** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — obtenez un index de fonctions/classes ou une définition spécifique sans lire tout le fichier |

### 🖥 3Interfaces + A2A

| Mode | Commande | Objectif |
|---|---|---|
| **CLI** | `uag` | Fonctionnement rapide basé sur un terminal |
| **interface graphique** | `uagg` | Interface utilisateur de bureau via tkinter |
| **Internet** | `uagw` | Accès par navigateur |
| **Serveur A2A** | `ouaga` | Protocole Agent2Agent pour la communication multi-agents |

### 🏠 Contrôle des appareils IoT

- **SwitchBot** : contrôle par lots dans le cloud et analyse/contrôle BLE
- **ECHONET Lite** : Découvrez et contrôlez les appareils électroménagers (AC, lumières, chauffe-eau, etc.) sur le réseau local
- **Matter** : inspection en lecture seule de la topologie du contrôleur/pont/appareil
- **UPnP** : découverte de périphériques et redirection de port IGD

Voir [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Marché des compétences d'agent

`:skills mp_search` pour parcourir [SkillsMP](https://skillsmp.com) et [ClawHub](https://clawhub.ai) pour les compétences communautaires.
Installez et étendez les capacités d'uag à la volée.

### 🧩 Gestionnaire d'état par lots

uag peut suivre la progression des tâches multi-fichiers de longue durée. Lorsque le LLM traite des dizaines de fichiers, `batch_state` conserve la liste des fichiers en attente, terminés et ayant échoué sur le disque. Si la session se termine ou si un tour expire, l'exécution suivante reprend là où elle s'est arrêtée : rien n'est perdu.

### 🛡 Humain dans la boucle

`human_ask` permet au LLM de faire une pause et de vous demander votre confirmation avant d'effectuer des opérations destructrices (suppression de fichiers, écrasements, commandes shell). Vous gardez le contrôle.

### 🕵️ Automatisation du navigateur et inspecteur Web

Deux outils complémentaires basés sur Playwright :

- **browser_playwright** : automatisez de vraies sessions de navigateur : naviguez, cliquez, remplissez des formulaires, extrayez des données, gérez des flux multipages. Fonctionne sans tête ou avec tête.
- **playwright_inspector** : enregistrez les transitions du navigateur, capturez des instantanés et des captures d'écran DOM à chaque étape. Utile pour déboguer les interactions Web ou auditer les modifications de page au fil du temps.

### 🔄 Chargement dynamique des outils

`tool_catalog` et `tool_load` vous permettent de découvrir et d'activer des outils au moment de l'exécution.
Pas besoin de tout charger au démarrage : activez uniquement ce dont vous avez besoin, quand vous en avez besoin.

### 🌐i18n/L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / et plus encore.
Définissez `UAGENT_LANG` pour changer. Voir [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) pour ajouter de nouveaux paramètres régionaux.

Les traductions de ce README sont disponibles dans [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Variables d'environnement cryptées

Stockez les clés et les secrets API dans « .env.sec » – un fichier « .env » crypté.
Gérez avec `uag_envsec`.

## Configuration et détails

- **Variables d'environnement** : [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Assistant d'installation** : `python -m uagent.setup_cli`
- **Env crypté** : `uag_envsec` — crypte `.env` en `.env.sec`
- **API Réponses** : définissez `UAGENT_RESPONSES=1` pour le mode API Réponses (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Documents pour développeurs** : [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Petits conseils LLM** : [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Philosophie du projet

uag aspire à être **votre IA, sur votre machine, selon vos conditions.**

- Aucune dépendance SaaS - fonctionne localement
- Pas de dépendance vis-à-vis d'un fournisseur : changez à tout moment
- Pas de verrouillage de l'interface utilisateur - CLI / GUI / Web / A2A
- Pas de verrouillage de fonctionnalités - étendez-vous avec des outils et des compétences

Une expérience d’agent IA gratuite, sans dépendance vis-à-vis d’un fournisseur.