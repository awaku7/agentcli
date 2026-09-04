# Compression du contexte et contexte de modèle borné

uag utilise plusieurs niveaux pour maintenir le contexte de modèle actif dans des limites définies. L’objectif est de réduire les tokens d’entrée superflus sans supprimer les fichiers, les résultats des outils ou les données de session dont l’utilisateur pourrait encore avoir besoin.

Ce document décrit l’implémentation actuelle. Il distingue également le comportement déterministe du comportement spécifique au fournisseur ou assisté par LLM.

## 1. Surface d’outils dynamique

Toutes les définitions d’outils n’ont pas besoin d’être envoyées au modèle à chaque tour.

- `tool_catalog` recherche les capacités disponibles.
- `tool_load` n’active que les outils requis pour la tâche en cours.
- `tool_catalog`, `tool_load` et `unload_tool` restent disponibles en tant qu’outils de gestion.
- Les flux Responses API compatibles avec GPT-5.4 peuvent utiliser le Tool Search natif côté serveur.
- Le mode Tool Search hérité restreint les spécifications des outils avec `tool_catalog` côté client.

Cela réduit le nombre de jetons d’entrée utilisés par les schémas d’outils, en particulier dans les installations comportant de nombreux outils.

## 2. Les résultats textuels volumineux des outils deviennent des artefacts

Lorsqu’un résultat textuel d’un outil dépasse le seuil de Artifact, uag stocke le résultat complet sous forme de Artifact et envoie au modèle une référence délimitée ainsi qu’un aperçu au lieu du texte intégral.

Les limites par défaut sont les suivantes :

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

La représentation visible par le modèle contient le nom de l’outil, la longueur d’origine, une référence `artifact://`, le chemin de stockage et un aperçu limité. Le résultat complet reste disponible via le magasin Artifact.

Le seuil peut être modifié à l’aide de `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Une valeur de `0` désactive la promotion Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` contrôle la politique habituelle de résultats limités ; `0` désactive cette limite habituelle.

## 3. Récupération limitée de `Artifact`

L’outil d’infrastructure `artifact_read` ne récupère que la partie demandée d’un `Artifact` :

- `start_line` sélectionne la première ligne.
- `max_lines` est limité à 500.
- `max_chars` est limité à 50 000 caractères.
- Il est possible d’utiliser aussi bien un identifiant Artifact qu’un URI `artifact://`.

Cela permet d’inspecter une petite partie pertinente plutôt que de réinjecter l’intégralité d’un fichier ou du résultat d’une commande dans le cycle suivant du modèle.

Les nouveaux artefacts sont stockés ci-dessous :

```text
~/.uag/artifacts/
```

Les anciens chemins Artifact existants restent lisibles à des fins de compatibilité.

## 4. Isolation des charges utiles binaires

Les données binaires intégrées ne sont pas envoyées sous forme de résultat textuel de l’outil au tour suivant du modèle. Les champs de type Base64 sont remplacés par un marqueur court tel que :

```text
[charge binaire omise du contexte LLM]
```

L’interface utilisateur et les clients distants peuvent toujours recevoir des pièces jointes en mémoire, et les fichiers enregistrés restent accessibles via leurs chemins d’accès ou leurs références Artifact. Cela empêche les images, les fichiers audio, les captures d’écran et autres charges utiles binaires de gonfler le contexte textuel du modèle.

La même catégorie de charge utile binaire est nettoyée avant la persistance SQLite et JSONL, ce qui empêche qu’elle ne réapparaisse sous forme de charge utile volumineuse après le rechargement d’une session.

## 5. Compression automatique de l’historique

uag peut compresser l’historique des conversations les plus anciennes lorsque le nombre de messages ou le nombre estimé de tokens atteint la limite configurée.

La politique de compression utilise :

- le nombre de messages non système ;
- la fenêtre de contexte résolue du modèle, lorsqu’elle est disponible ;
- `UAGENT_SHRINK_KEEP_LAST` (20 par défaut) ;
- `UAGENT_SHRINK_MAX_TOKENS` ou une valeur de remplacement spécifique au modèle ;
- `UAGENT_SHRINK_CNT` ; et
- `UAGENT_SHRINK_RATIO` (0,5 par défaut lorsqu’une fenêtre de contexte est connue).

Une limite spécifique au modèle peut être fournie sous la forme :

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Un résumé précédent n’est pas régénéré à chaque tour. L’hystérésis nécessite l’accumulation d’un historique suffisant, ou un nouveau dépassement du budget de tokens, avant que la compression ne se relance.

## 6. Résumés d’historique assistés par LLM

Lorsque la compression automatique utilise le LLM, les anciens messages de l’utilisateur, de l’assistant et de l’outil sont résumés en un message système glissant, tandis que la partie la plus récente est conservée.

Les historiques longs peuvent être résumés par blocs. Les commandes pertinentes sont :

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Le résumé est replié vers l’avant plutôt que de créer une séquence illimitée de messages de résumé. Il s’agit d’une opération assistée par LLM pouvant nécessiter des requêtes supplémentaires auprès du fournisseur.

## 7. Compression de secours déterministe

Si un résumé LLM n’est pas disponible, uag peut conserver les messages système les plus anciens et uniquement les messages les plus récents. Les limites des appels d’outils sont corrigées afin que l’historique résultant ne commence ni ne se termine par un appel d’outil orphelin.

Le chargeur et le nettoyeur suppriment également les entrées non pertinentes pour le modèle ou invalides, notamment les messages réservés à l’interface utilisateur, les messages de contrôle internes, les lignes de journalisation corrompues, les rôles non pris en charge, les résultats d’outils orphelins et les blocs d’appels d’outils incomplets.

Lorsqu’une session est rechargée, l’invite système actuelle est restaurée et seuls les messages système injectés pertinents, tels que le contexte de compétence ou de hook, sont conservés.

## 8. Récupération en cas de débordement de contexte

Si un fournisseur signale que la fenêtre de contexte a été dépassée, uag identifie un message récent volumineux dans l’historique et annule ce message ainsi que l’historique qui suit avant de réessayer. Il s’agit d’une solution de secours réactive, qui ne remplace pas la gestion normale des limites.

## 9. Poursuite et compaction côté fournisseur

Lorsque cela est pris en charge, le Responses API utilise `previous_response_id` pour poursuivre une chaîne de réponses sans renvoyer depuis le client l’intégralité de l’historique des réponses géré par le fournisseur.

Les flux Responses API envoient également la configuration de compaction côté fournisseur en utilisant le même seuil de réduction local. Le comportement exact dépend du fournisseur ; les Artifact locaux et les politiques d’historique restent les mesures de sécurité indépendantes du fournisseur.

## 10. Efficacité du comptage des jetons

Les comptes de jetons utilisés pour les décisions de compression sont mis en cache et mis à jour de manière incrémentielle lorsque seuls de nouveaux messages ont été ajoutés. Cela ne réduit pas directement le contexte du modèle, mais cela réduit le coût en CPU et la latence liés à la décision de compression.

## Ce qui ne constitue pas encore une couche unifiée complète

L’implémentation actuelle ne fournit pas encore l’ensemble des éléments suivants sous la forme d’un gestionnaire neutre vis-à-vis des fournisseurs :

- un `ContextManager` et un `ContextBudget` unifiés ;
- un `ToolResultRecord` avec des métadonnées d’importance et d’éviction ;
- des résumés sémantiques ne nécessitant pas de `LLM` ;
- la récupération et la réinjection automatiques des artefacts pertinents ;
- un gestionnaire de résultats central garantissant la conversion en `Artifact` pour chaque outil produisant des binaires ; ou
- une éviction tenant compte des priorités pour toutes les catégories : système, historique, schéma d’outil et résultats.

En résumé, le uag combine actuellement la troncature déterministe, les références Artifact, l’isolation des binaires, la sélection dynamique des outils, les résumés d’historique, la continuité des fournisseurs et la récupération en cas de débordement. La feuille de route de conception d’une couche de contexte unifiée est documentée dans [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
