<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Un agent local. N'importe quel modèle. N'importe quel outil. Votre environnement, vos règles.
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI status"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI version"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="https://github.com/awaku7/agentcli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="PyPI Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a> ·
  <a href="https://pypi.org/project/uag/">PyPI</a> ·
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**Pourquoi uag ?**

uag est un agent IA local par conception, qui connecte le modèle de votre choix aux outils que vous utilisez réellement.
Il vous offre un environnement d'exécution unique et extensible pour les fichiers, les navigateurs, les bases de code, la communication, les API cloud,
les appareils IoT, les serveurs MCP et les workflows multi-agents.

- **Liberté de fournisseur** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek et bien d'autres.
- **Exécution locale par conception** — l'environnement d'exécution de votre agent et l'exécution des outils restent sur votre machine ; seuls les appels API que vous choisissez la quittent.
- **Une seule couche d'outils** — les mêmes outils fonctionnent depuis la CLI, l'interface graphique de bureau, l'interface web, VS Code et A2A.
- **Parallélisme intégré** — les opérations indépendantes en lecture seule peuvent s'exécuter simultanément.
- **Extensible** — ajoutez des outils, des plugins, des Agent Skills, des serveurs MCP et des outils basés sur Rust sans modifier le cœur.
- **Conçu pour la sécurité** — les actions destructrices, les identifiants, les commandes d'appareils et les écritures réseau prennent en charge la confirmation explicite et les politiques de contrôle.

> **En bref :** uag est le plan de contrôle entre vos modèles IA et votre environnement réel.

> **🧠 Résultats des outils tenant compte du contexte** — Les résultats volumineux des outils sont, dans la mesure du possible, exclus du contexte du modèle actif. uag les stocke sous forme d’artefacts et transmet au modèle un aperçu limité avec une référence Artifact stable à la place. Cela permet de réduire considérablement le nombre de tokens d’entrée requis pour les tours suivants lorsqu’un outil produit un résultat volumineux.
> [Guide détaillé sur la compression du contexte](CONTEXT_COMPRESSION.fr.md)

## Démarrage rapide

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

Le premier lancement ouvre l'assistant de configuration. Il aide à configurer un fournisseur et enregistre les paramètres sélectionnés
dans votre environnement local.

Pour les groupes de fonctionnalités courants :

```bash
python -m pip install "uag[core,providers,tools]"
```

> Les intégrations de plateforme sont facultatives. N'installez que ce dont votre système d'exploitation a besoin ; consultez

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Interfaces

| Interface | Commande | Idéal pour |
|---|---|---|
| **CLI** | `uag` | Un travail rapide privilégiant le clavier |
| **Interface graphique de bureau** | `uagg` | Une expérience de bureau native |
| **Interface web** | `uagw` | Un accès depuis le navigateur |
| **Serveur A2A** | `uaga` | La communication d'agent à agent |
| **VS Code** | Extension | Expliquer, refactoriser, corriger et parcourir les outils dans l'éditeur |

Toutes les interfaces partagent la même configuration de fournisseur, le même registre d'outils, les mêmes règles de sécurité et les mêmes données de session.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Ce que vous pouvez créer

Les adaptateurs de fournisseurs couvrent les environnements hébergés et locaux, notamment :

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- Lire, créer, modifier, rechercher, hacher, archiver et inspecter des fichiers
- Examiner les changements Git, rechercher les secrets, exécuter les tests, appliquer le linting, compiler et mesurer la couverture
- Parcourir de grandes bases de code Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA et autres
- Automatiser les navigateurs avec Playwright, y compris les workflows multipages et les téléchargements

- **MCP** — connecter des serveurs d'outils externes, y compris des services compatibles OAuth
- **A2A** — coordonner d'autres agents et des serveurs compatibles
- **Cloud** — accès aux API AWS, Google Cloud et Azure avec confirmation pour les écritures
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams et pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA et UPnP
- **Médias** — génération et modification d'images, transcription et synthèse audio, capture par caméra et codes QR
- **Documents** — analyse de PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL et journaux

- **SwitchBot** — découverte cloud et BLE, état, contrôle, traitement par lots et abonnements
- **ECHONET Lite** — découvrir et contrôler les appareils électroménagers japonais, y compris les notifications INF
- **Matter** — points de terminaison, clusters, attributs, historique d'état, abonnements et contrôle
- **BACnet / Modbus TCP / OPC UA** — lecture, écriture, navigation et surveillance pour l'automatisation industrielle et des bâtiments
- **UPnP** — découverte d'appareils, état WAN et gestion de la redirection de ports du routeur

### Où se situe uag ?

uag se place entre les personnes et les interfaces d'un côté, et les modèles, les outils et les systèmes du monde réel de l'autre.
Il coordonne la conversation, sélectionne les capacités, applique les règles de sécurité et permet de reprendre le workflow.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Plugins, Agent Skills et marketplaces

Transformez uag en agent spécialisé sans créer de fork du cœur :

- Installer des **plugins compatibles avec Claude Code** depuis un répertoire, un ZIP, un dépôt Git, une source HTTP ou une marketplace
- Regrouper des skills, sous-agents, serveurs MCP, hooks, commandes slash, styles de sortie, dépendances et canaux
- Parcourir les capacités communautaires de [SkillsMP](https://skillsmp.com) et [ClawHub](https://clawhub.ai)
- Ajouter localement des skills et outils privés de l'organisation via `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

Consultez le [Guide de développement des plugins](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **Plus de 200 outils** pour les fichiers, le web, les médias, les documents, le code, le cloud, la communication et l'IoT
- **Découverte et chargement dynamiques** — utilisez `tool_catalog` pour trouver les capacités et `tool_load` pour ne les activer qu'en cas de besoin
- **Intelligence du code** — `code_map`, navigateurs `idx` propres aux langages, revue Git, exécution de tests, linting, compilation et couverture
- **Plugins compatibles avec Claude Code** avec skills, agents, serveurs MCP, hooks, commandes et marketplaces
- **Agent Skills** de SkillsMP et ClawHub
- **Outils Python personnalisés** avec `TOOL_SPEC` et `run_tool()`
- **Outils basés sur Rust** pour des extensions natives légères

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Conçu pour des flux de travail réels

### 🧠 Résultats des outils tenant compte du contexte

Les résultats volumineux des outils sont, dans la mesure du possible, exclus du contexte du modèle actif. uag les stocke sous forme d’artefacts et transmet au modèle un aperçu limité avec une référence Artifact stable à la place. Cela permet de réduire considérablement le nombre de tokens d’entrée requis pour les tours suivants lorsqu’un outil produit un résultat volumineux.

Reprenez les conversations précédentes avec `:load <index>`. Les résultats des outils peuvent être mis en cache et les fournisseurs peuvent être changés
sans reconstruire l'application.

[Context compression](CONTEXT_COMPRESSION.fr.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Pilote automatique

Utilisez `:auto` pour les tâches en plusieurs tours avec un modèle réviseur facultatif. Définissez une limite de tours avec `--max-rounds N`.
Appuyez sur **F12** pour arrêter le pilote automatique ou sur **F12** pour arrêter la réponse en cours.

Les opérations indépendantes en lecture seule s'exécutent simultanément lorsque cela est sûr. Les recherches web, l'inspection de fichiers,
l'analyse de dépôts et les charges similaires peuvent s'effectuer en parallèle avec un pool de workers configurable
(`UAGENT_PARALLEL_WORKERS`). Les opérations d'écriture restent sérialisées ou nécessitent une confirmation.

La continuité des sessions, la mise en cache des résultats d'outils, l'état des lots, la reprise après redémarrage, la planification en DAG et
l'orchestration multi-agents rendent les tâches complexes reprenables plutôt que limitées à une seule exécution.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Privé, multilingue et conscient des politiques

`human_ask` met en pause l'exécution avant les actions sensibles. La suppression et l'écrasement de fichiers, les commandes shell, le contrôle des appareils,
les opérations sur les identifiants et les écritures réseau peuvent être régis par des règles de confirmation et de politique.

Utilisez le magasin d'identifiants au lieu de placer des secrets persistants dans les prompts :

L'interface Web inclut une connexion OIDC utilisant Authorization Code + PKCE, des jetons d'identification vérifiés, des sessions côté serveur, et des contrôles d'accès aux projets/salles. Les revendications de groupe Microsoft Entra ID vérifiées peuvent alimenter la politique d'accès basée sur l'annuaire lorsqu'elles sont configurées. Les déploiements Windows Active Directory, OAuth et trusted-proxy peuvent s'intégrer via des adaptateurs d'identité vérifiés explicites ; Windows AD nécessite un vérificateur Kerberos/Negotiate spécifique au déploiement et n'est pas activé par défaut.

uag inclut le traçage et les métriques OpenTelemetry, indépendants du fournisseur, pour Agent, LLM, l'outil, Context, Memory et les opérations de récupération. L'observabilité est désactivée par défaut.

Le fonctionnement local en priorité ne signifie pas que UAG est entièrement hors ligne ou isolé par défaut. Les appels aux modèles et services externes dépendent de votre configuration.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Traduction multilingue

- `translate_text` prend en charge Google Translate et le client Python officiel de DeepL via `provider=auto`, `provider=deepl` ou `provider=google`.
- Les définitions d’outils sont disponibles dans 37 langues plus l’anglais (38 au total), avec conservation des espaces réservés et des identifiants techniques.

La voix en duplex intégral est disponible via OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live,
et Bedrock Nova Sonic, avec annulation d'écho AEC3 facultative et appels de fonctions en temps réel limités par la sécurité.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Documentation

| Sujet | Documentation |
|---|---|
| Variables d'environnement | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture et invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Outils du dépôt | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| Cas d'utilisation IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Outils de communication | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Pilote automatique | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| OAuth / Proxy MCP | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| Extension VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Guide du développeur | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Flux des outils | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Développement et contribution

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

Exécutez les vérifications pré-PR :

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Pour le workflow de développement complet, consultez [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

Les rapports de bugs, idées de fonctionnalités, améliorations de la documentation, traductions, outils, skills et pull requests sont les bienvenus.
Veuillez ouvrir une issue ou une discussion avant toute modification importante. Lisez le [Guide du développeur](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
et exécutez les vérifications ci-dessus avant de soumettre une pull request.

## Licence

Sous licence [Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
