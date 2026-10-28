<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Vos modèles d’IA. Vos outils. Votre environnement.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Autres langues</a></p>

---

**UAG est un environnement d’exécution d’agents IA open source, conçu pour privilégier l’exécution locale.** Il relie le modèle de langage de votre choix aux outils et systèmes que vous utilisez. Travaillez avec du code, des fichiers, des navigateurs, des services et des appareils depuis une interface cohérente, sans dépendre d’un fournisseur de modèles unique.

| **Choisissez votre modèle** | **Connectez vos outils** | **Gardez le contrôle** |
| :--- | :--- | :--- |
| Modèles hébergés ou locaux : OpenAI, Claude, Gemini, Grok, Bedrock, Ollama, entre autres | Fichiers, code, Web, MCP, Agent Skills, plugins, services cloud et IoT | Exécution locale, validation humaine, stockage des identifiants et politiques configurables |

> UAG est **une couche d’exécution d’agents, pas un fournisseur de modèles**. Les appels à des modèles externes ou à des services connectés dépendent de votre configuration. Le fonctionnement local prioritaire n’implique ni une utilisation entièrement hors ligne ni une isolation systématique.

## Démarrage rapide
<!-- README-SYNC:quick-start -->

**Python 3.11 ou version ultérieure** est nécessaire. Installez UAG depuis [PyPI](https://pypi.org/project/uag/) et ouvrez l’interface en ligne de commande :

~~~bash
python -m pip install --upgrade uag
uag
~~~

Au premier lancement, l’assistant de configuration vous aide à choisir un fournisseur et à enregistrer ses identifiants. Vous pouvez également utiliser des variables d’environnement ou le magasin d’identifiants. Pour installer à l’avance davantage de dépendances liées aux modèles et aux outils :

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Essayez ensuite ces demandes :

~~~text
> Qu’est-ce qui a changé dans ce dépôt Git ? Résume les risques.
> Cherche la documentation récente de cette bibliothèque et explique la procédure de migration.
> Analyse ces fichiers et produis un rapport concis.
> :help
~~~

Pour commencer, consultez le guide d’installation Windows (incluant Git et les environnements virtuels) ainsi que la référence de configuration : [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Interfaces
<!-- README-SYNC:interfaces -->

Toutes les interfaces utilisent le même moteur d’agent et le même registre d’outils.

| Interface | Démarrage | Utilisation |
| :--- | :--- | :--- |
| **CLI** | `uag` | Travail dans le terminal et automatisation |
| **Desktop** | `uagg` | Discussions dans une application native |
| **Web** | `uagw` | Discussions et espaces depuis un navigateur |
| **A2A** | `uaga` | Interopérabilité entre agents |
| **VS Code** | [Guide de l’extension](VSCODE.md) | Travail au plus près du code |

Les interfaces Desktop et Web nécessitent des dépendances supplémentaires, absentes du groupe `uag[core,providers,tools]` utilisé au démarrage :

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Le serveur Web peut essayer d’installer FastAPI et Uvicorn au lancement. Les installer à l’avance évite de dépendre de cette installation automatique. Plus d’informations : [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## Ce que vous pouvez réaliser avec UAG
<!-- README-SYNC:capabilities -->

| Fonctionnalité | Ce qu’offre UAG |
| :--- | :--- |
| **Flux indépendants du modèle** | Changer de fournisseur hébergé ou local avec `UAGENT_PROVIDER` sans réécrire les outils |
| **Code et fichiers** | Explorer les dépôts, examiner Git, vérifier le code, exécuter des tests, manipuler les fichiers et automatiser le navigateur |
| **Outils extensibles** | Plus de 200 outils, découverte à la demande avec `tool_catalog` / `tool_load`, extensions Python et Rust |
| **Agents connectés** | MCP, A2A, plugins compatibles Claude Code, Agent Skills et sous-agents |
| **Travaux de longue durée** | Pilote automatique, lectures indépendantes en parallèle, tâches planifiées, reprise et sessions persistantes |
| **Au-delà du terminal** | Cloud, communications, documents, médias, voix en temps réel et protocoles IoT pris en charge |

### Un seul moteur, de nombreuses intégrations
<!-- README-SYNC:integrations -->

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

**Exemples de fournisseurs compatibles** : voir ci-dessous ; leurs réglages particuliers figurent dans la référence de configuration.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Personnaliser avec des skills et des plugins
<!-- README-SYNC:extensions -->

Étendez UAG sans modifier son noyau. Installez des Agent Skills via SkillsMP ou ClawHub, connectez des serveurs MCP ou chargez des plugins compatibles Claude Code regroupant outils, skills, agents et hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Des outils personnalisés peuvent exposer `TOOL_SPEC` et `run_tool()` ; les outils s’appuyant sur Rust sont également pris en charge. Consultez : [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Conçu pour les tâches réelles
<!-- README-SYNC:workflows -->

### Contexte et mémoire
<!-- README-SYNC:context-memory -->

Les résultats volumineux des outils peuvent être conservés dans des **artefacts** plutôt que de saturer le contexte actif du modèle. L’agent peut ensuite relire uniquement la partie utile avec `artifact_read`. Les sessions sont enregistrées par défaut dans SQLite, avec recherche d’historique et vérification explicite de la mémoire.

- [Context compression](CONTEXT_COMPRESSION.fr.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Automatisation et collaboration
<!-- README-SYNC:automation -->

UAG prend en charge les lectures indépendantes en parallèle, la coordination de plusieurs agents, la reprise des sessions et un pilote automatique pour les travaux en plusieurs tours. Lancez-le avec `:auto` ; appuyez sur **F12** pour interrompre la réponse en cours et demander l’arrêt du pilote automatique.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Sécurité et observabilité
<!-- README-SYNC:security -->

Les opérations sensibles peuvent nécessiter une confirmation `human_ask`. Les identifiants peuvent être enregistrés dans le gestionnaire natif du système ou dans des fichiers chiffrés. L’interface Web prend en charge, après configuration, la connexion OIDC et les contrôles d’accès. Les traces et métriques OpenTelemetry sont **facultatives**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Ces contrôles sont configurables : **ils ne garantissent pas** que toute exécution d’outil soit isolée dans un bac à sable. Consultez les guides de déploiement et de politique avant d’exposer UAG à des utilisateurs ou réseaux non fiables.

### Langues, appareils et voix
<!-- README-SYNC:languages -->

UAG fournit des ressources pour **38 paramètres régionaux** (anglais et 37 traductions), des intégrations vocales bidirectionnelles facultatives et des outils pour SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP et OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Documentation
<!-- README-SYNC:documentation -->

Pour démarrer ou approfondir un domaine, utilisez ces ressources :

| Commencer ici | Approfondir |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Vous pouvez aussi parcourir l’ensemble des documents et les autres traductions : [Documentation](./) · [Other languages](README.translations.md).

## Développement et contributions
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

Avant toute pull request qui modifie du **code Python**, exécutez les tests utiles et les vérifications du projet :

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Les règles de contribution figurent dans les guides ci-dessous. Issues, documentation, traductions, outils et pull requests ciblées sont bienvenus : [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Licence
<!-- README-SYNC:license -->

UAG est distribué sous la licence suivante : [Apache License 2.0](../LICENSE).
