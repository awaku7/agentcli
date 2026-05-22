# Major Updates (Last 30 Days)

This document summarizes the major updates, architectural enhancements, and feature releases introduced in the `uag` project over the last 30 days.

---

## 1. Specialized Sub-Agent Architecture (`run_sub_agent`)
A secure, sandboxed sub-agent execution framework has been introduced to delegate complex tasks to specialized roles under the orchestrator's control.

* **Role-Based Sub-Agents**:
  * `planner`: Formulates step-by-step plans, identifies risks, and maps out constraints.
  * `reviewer`: Audits code, designs, and patches for bugs, security vulnerabilities, and infinite loops.
  * `summarizer`: Compresses long conversation histories and logs into essential context.
  * `patch_designer`: Designs safe, precise code replacement patches (diffs) without executing changes.
  * `error_analyst`: Analyzes compilation, test, or runtime errors to pinpoint root causes.
* **Function-Specific Overrides**:
  * Added support to override the LLM provider, model name, and API key globally or individually per sub-agent role via environment variables (e.g., `UAGENT_SUB_AGENT_SUMMARIZER_PROVIDER=gemini` to route heavy summarization tasks to a fast, cost-effective model).
* **Localization**:
  * Fully localized the sub-agent tool specs and descriptions across 30 global languages.

---

## 2. Python 3.11+ Modernization
The entire codebase has been modernized to leverage Python 3.11+ features, improving type safety, performance, and maintainability.

* **Modern Typing Syntax**:
  * Upgraded type hints to Python 3.11+ native syntax (e.g., using `list` and `dict` instead of `typing.List` and `typing.Dict`, and `|` instead of `typing.Union`/`typing.Optional`).
* **Cleanup**:
  * Removed deprecated imports, legacy compatibility layers, and unused modules.
  * Verified all changes with strict syntax compilation checks.

---

## 3. Deterministic Reasoning & Temperature Unification
To ensure stable tool-use, reliable JSON formatting, and consistent reasoning steps, the default temperature has been optimized.

* **Unified Default Temperature**:
  * Set the default temperature to **`0.2`** across all major LLM providers (Gemini, Vertex AI, Claude, OpenAI, Azure, Bedrock, OpenRouter, Grok, NVIDIA) when executing agent loops.
  * Added support for provider-specific temperature overrides via environment variables (e.g., `UAGENT_GEMINI_TEMPERATURE`, `UAGENT_CLAUDE_TEMPERATURE`, `UAGENT_OPENAI_TEMPERATURE`).

---

## 4. Multilingual Tool Catalog & Search Ranking
The tool discovery mechanism has been enhanced to support multilingual environments and smarter search ranking.

* **Tokenization & Search**:
  * Added multilingual tokenization support for the tool catalog.
  * Improved search ranking algorithms to surface relevant tools more accurately based on user intent.
* **Locale Expansion**:
  * Added new locale translations (including Bengali `bn`, Persian `fa`, Mongolian `mn`, and Marathi `mr`), expanding the project's global reach.

---

## 5. Batch State Management & Robust File Operations
Enhanced support for processing large-scale, multi-file batch operations safely and efficiently.

* **Batch State Tracking**:
  * Introduced robust batch state tracking (`batch_state` tool) to manage progress, resume interrupted tasks, and log file-by-file outcomes.
* **File Operations**:
  * Improved performance and newline diagnostics in the `replace_in_file` tool.
  * Added robust Windows shell command quoting and argument escaping for tool wrappers.

---

## 6. GUI & Log Rendering Enhancements
Improved the user experience in the graphical interface with better log visualization.

* **ANSI Color Rendering**:
  * Added an ANSI HTML rendering helper to correctly parse and display colored terminal logs in the GUI.
  * Fixed log color rendering issues in the GUI console.
