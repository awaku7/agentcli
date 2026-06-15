<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

# uag (Agent IA local)

uag est un agent interactif qui exécute des **commandes**, manipule des **fichiers** et lit **divers formats de données** (PDF/PPTX/Excel, etc.) sur votre PC local. Il propose trois interfaces : CLI, GUI et Web.

uag est conçu pour **vous libérer des applications verrouillées par un fournisseur** : utilisez l’interface adaptée à votre flux de travail, changez de fournisseur et gardez le contrôle de votre environnement.

GitHub: https://github.com/awaku7/agentcli

## Installation

Vous pouvez installer `uag` via pip :

```bash
pip install uag
```

Après l'installation, le premier lancement d'`uag` démarrera automatiquement un **assistant de configuration interactif** pour configurer vos variables d'environnement. Pour des informations détaillées sur la configuration et le chiffrement, consultez **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

## Caractéristiques principales

- **Ensemble d'outils pratiques** : Équipé d'outils pour la manipulation de fichiers, la recherche web, l'extraction de données (PDF/PPTX/Excel), la génération d'images et l'analyse, tous exécutables dans votre environnement local.
- **Support multi-fournisseurs** : Supporte OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI).
- **Interfaces flexibles** :
  - **CLI**: `uag` / `python -m uagent`
  - **GUI**: `uagg` / `python -m uagent.gui`
  - **Web**: `uagw` / `python -m uagent.web`
- **MCP (Model Context Protocol)** : Support pour la connexion à des serveurs d'outils MCP externes.
- **Continuité de session** : Maintient le contexte de la conversation même lors du changement de fournisseur ou de modèle.
- **Web Inspector** : Enregistre automatiquement les transitions du navigateur, le DOM et les captures d'écran avec `playwright_inspector`.
- **Documentation intégrée** : Accédez instantanément à une documentation interne détaillée à l'aide de la commande `uag docs`.

## Utilisation

### Démarrage et sortie

Lancez `uag` depuis votre terminal pour commencer. Tapez `:exit` pour quitter.

### Serveur A2A (Agent2Agent)

Vous pouvez lancer un serveur HTTP compatible A2A séparé des interfaces existantes.

```bash
uaga
# ou python -m uagent.a2a.server
```

### Remarque sur Responses API

Si vous définissez `UAGENT_RESPONSES=1`, Responses API est utilisée pour les fournisseurs pris en charge : OpenAI / Azure / Bedrock / OpenRouter / Ollama.
Gemini / Claude / Vertex AI utilisent leurs chemins d’API natifs et ne sont pas couverts par Responses API.
Pour les autres fournisseurs, uag revient au chemin spécifique du fournisseur ou au flux chat-completions.

Voir [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) pour les paramètres `UAGENT_A2A_*` tels que l’authentification, l’hôte, le port, le rechargement, l’URL de base publique, la concurrence et le moteur.

### Conseils pratiques (continuité et contrôle)

- `:tools` : Affiche une liste des outils chargés.
- `:logs [n]` : Affiche les journaux de session (`n` pour spécifier le nombre d'entrées).
- `:load <index>` : Charge une session passée pour reprendre la conversation.
- `:skills` : Sélectionne et charge des compétences d'agent (rôles ou instructions supplémentaires).
- `:shrink [n]` : Organise l'historique pour ne conserver que les `n` derniers messages afin d'économiser des jetons.

## Configuration et détails

### Variables d'environnement et configuration

Pour les paramètres détaillés (clés API, langue d'affichage `UAGENT_LANG`, paramètres de réduction d'historique, etc.), consultez **[ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)**.

- **Configuration** : Configurez de manière interactive via `python -m uagent.setup_cli`.
- **Chiffrement** : Chiffrez vos fichiers `.env` en toute sécurité à l'aide de l'outil `uag_envsec`.
- **Mise à jour** : Utilisez `uag_envsec add --file .env.sec --key NAME --value VALUE` pour ajouter ou mettre à jour une variable dans un fichier chiffré existant.

### Développeurs et internationalisation

- **Docs développeur** : [`src/uagent/docs/DEVELOP.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Ajout de locales** : [`src/uagent/docs/ADD_LOCALE.md`](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md)
- **README dans d'autres langues** : [`docs/README.translations.md`](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md)
