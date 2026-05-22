# Major Updates & Architectural Milestones (Project History)

This document summarizes the major updates, architectural milestones, and feature releases introduced in the `uag` project from its inception to the latest version.

---

## 1. Core Architecture & Multi-Provider Support (Enhanced Local AI)
The project was founded on a robust, multi-provider LLM client architecture designed to support diverse AI backends seamlessly, including fully offline local environments via **Ollama**.

* **Multi-Provider Integration & Strong Local AI Support**:
  * Native API support for **OpenAI, Azure OpenAI, Anthropic Claude, Google Gemini, Google Vertex AI, AWS Bedrock, OpenRouter, Ollama, Grok (xAI), and NVIDIA**.
  * Significantly enhanced support for local LLMs (such as Llama 3.1) via **Ollama**. Implemented a dedicated parameter tuning mechanism (`apply_ollama_extra_body`) to configure local-specific options (e.g., `keep_alive`, context size expansion via `num_ctx`, and `repeat_penalty`) directly from environment variables. This enables high-performance tool-use and image analysis (Ollama Vision) even in fully offline environments.
* **Full Multilingual Dialogue Support (I18N for LLM Interactions)**:
  * Implemented stateless, per-call translation helpers (`translate.py`) to automatically translate user inputs and LLM responses. This seamlessly enables "I18N for LLM interactions" (e.g., translating Japanese user inputs to English before sending them to the LLM, and translating the LLM's English responses back to Japanese). It supports translation via OpenAI-compatible APIs, as well as native Gemini and Claude APIs.
* **Deterministic Reasoning & Temperature Unification**:
  * Standardized the default temperature to **`0.2`** across all major LLM providers to ensure stable tool-use, reliable JSON formatting, and consistent reasoning steps.
  * Added support for provider-specific temperature overrides via environment variables (e.g., `UAGENT_GEMINI_TEMPERATURE`, `UAGENT_CLAUDE_TEMPERATURE`, `UAGENT_OLLAMA_TEMPERATURE`).

---

## 2. Context Compression & History Inheritance (`shrink_llm`)
To prevent context window overflow and reduce token consumption during long-running agent loops, the project implements an advanced history compression mechanism.

* **LLM-Driven Context Compression (`compress_history_with_llm`)**:
  * When the number of non-system messages exceeds a threshold (configured via `UAGENT_SHRINK_CNT`, default `100`), the agent automatically triggers a background compression routine.
  * It retains the most recent messages (configured via `UAGENT_SHRINK_KEEP_LAST`, default `20`) to maintain immediate conversational flow.
  * The older history is partitioned into chunks and summarized by a separate LLM context, compressing the entire past interaction into a single, highly dense `system` message. This allows the agent to inherit prior context, decisions, and errors indefinitely without hitting token limits.

---

## 3. Long-Term & Shared Memory Systems
The agent is equipped with persistent memory layers to retain user preferences, environment details, and cross-session context.

* **Personal Long-Term Memory (`UAGENT_MEMORY_FILE`)**:
  * Allows the agent to persist key insights, user instructions, and environment configurations across sessions into a local JSONL file (`scheck_memory.jsonl`).
  * These records are automatically injected into the system prompt at startup, ensuring the agent "remembers" the user's preferences.
* **Shared Long-Term Memory (`UAGENT_SHARED_MEMORY_FILE`)**:
  * Supports a shared memory file accessible by multiple agents or sessions, enabling collaborative context sharing.
  * Added interactive CLI commands such as `:shared-mem-list` and `:shared-mem-del <index>` to manage shared memory entries directly.

---

## 4. Specialized Sub-Agent Architecture (`run_sub_agent`)
A secure, sandboxed sub-agent execution framework was introduced to delegate complex tasks to specialized roles under the orchestrator's control.

* **Role-Based Sub-Agents**:
  * `planner`: Formulates step-by-step plans, identifies risks, and maps out constraints.
  * `reviewer`: Audits code, designs, and patches for bugs, security vulnerabilities, and infinite loops.
  * `summarizer`: Compresses long conversation histories and logs into essential context.
  * `patch_designer`: Designs safe, precise code replacement patches (diffs) without executing changes.
  * `error_analyst`: Analyzes compilation, test, or runtime errors to pinpoint root causes.
* **Function-Specific Overrides**:
  * Added support to override the LLM provider, model name, and API key globally or individually per sub-agent role via environment variables (e.g., `UAGENT_SUB_AGENT_SUMMARIZER_PROVIDER=gemini` to route heavy summarization tasks to a fast, cost-effective model).

---

## 5. Advanced Tooling & File Operations
A rich suite of local tools has been developed and refined to allow the agent to interact safely and efficiently with the user's machine.

* **File Search & Manipulation**:
  * `file_grep`: Upgraded with context lines, filenames-only mode, and auto-exclusion of noise directories.
  * `replace_in_file`: Optimized for performance with enhanced newline diagnostics and failure reporting.
  * `document_extract`: Added support to extract text and structure from Word-based documents (`.docx`, `.rtf`, `.odt`).
* **Batch State Management**:
  * Introduced robust batch state tracking (`batch_state` tool) to manage progress, resume interrupted tasks, and log file-by-file outcomes.
* **Playwright Inspector**:
  * Integrated Playwright Inspector to capture browser operations, network events, and console logs.

---

## 6. Multilingual Localization (I18N)
The project features a comprehensive, global-ready internationalization framework.

* **Global Reach**:
  * Fully localized the CLI, setup wizard, and tool specifications across **30 global languages** (including Japanese, English, Arabic, Hindi, Portuguese, Bengali, Persian, Mongolian, Marathi, and more).
  * Implemented robust Windows console language detection and unified i18n logic in tools.
* **Tool Catalog Search**:
  * Added multilingual tokenization support for the tool catalog to improve search ranking and discovery.

---

## 7. Security & Encryption (`uag_envsec`)
To protect sensitive API keys and credentials, a robust encryption layer was integrated.

* **Environment Encryption**:
  * Integrated `uag_envsec` to encrypt `.env` files into `.env.sec` using password-based encryption.
  * Implemented automatic detection and loading of `.env.sec` during CLI startup.
  * Added the `envsec add` command to securely append or update variables.

---

## 8. GUI, Web, & Multimedia Enhancements
The user experience has been enriched with graphical, web-based, and multimedia capabilities.

* **GUI Console & Log Rendering**:
  * Added an ANSI HTML rendering helper to correctly parse and display colored terminal logs in the GUI.
  * Fixed log color rendering issues in the GUI console.
* **Web UI Features**:
  * Added drag-and-drop file uploads and improved image attachment rendering.
* **Multimedia Tools**:
  * `generate_image` & `img2img`: Added support for DALL-E 3, Gemini, and Vertex AI (Imagen 3) with automatic opening behavior.
  * `audio_speech` & `audio_transcribe`: Added support for OpenAI, Azure, Gemini, and Vertex AI (including Google Cloud TTS REST transport for Windows compatibility).
