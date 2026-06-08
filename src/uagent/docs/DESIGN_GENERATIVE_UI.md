# DESIGN: Generative UI (Artifacts) for uag Web

This document outlines the design and implementation guidelines for introducing a **Generative UI (Artifacts-like)** feature into the **uag Web UI (`uagw`)**.

---

## 1. Background & Objectives

The **uag** agent is a powerful local tool-execution agent. While the CLI, GUI, and A2A interfaces are text-based, the Web UI (`uagw` powered by FastAPI) has the potential to render rich, interactive, and dynamic user interfaces generated on-the-fly by the LLM.

### Objectives:
- **Interactive Previews**: Allow the LLM to generate self-contained HTML/CSS/JS applications (dashboards, forms, interactive tools) and render them directly inside the Web UI.
- **Zero Impact on Other Interfaces**: Ensure that CLI, GUI, and A2A interfaces remain completely unaffected. They will simply display the generated HTML as standard Markdown code blocks.
- **Local Integration**: Leverage the local nature of `uag` to allow generated UIs to interact with the local machine (via FastAPI endpoints or tool execution).

---

## 2. Architecture Overview

The Generative UI feature will follow a **Split-View (Chat + Preview)** architecture on the frontend, with minimal backend changes.

```
+-----------------------------------------------------------------+
|                           uag Web UI                            |
+--------------------------------+--------------------------------+
|           Left Pane            |           Right Pane           |
|            (Chat)              |       (Artifact Preview)       |
|                                |                                |
|  User: "Create a dashboard"    |  +--------------------------+  |
|                                |  | [Preview] [Code]         |  |
|  Agent: "Here is the UI..."    |  +--------------------------+  |
|  +--------------------------+  |  |                          |  |
|  | ```html                  |  |  |  Interactive Chart       |  |
|  | <html>...                |  |  |  [Button] [Input]        |  |
|  | ```                      |  |  |                          |  |
|  +--------------------------+  |  +--------------------------+  |
+--------------------------------+--------------------------------+
```

### Key Components:
1. **LLM Prompting**: Instruct the LLM to output self-contained HTML/CSS/JS inside ` ```html ` code blocks when asked to build UIs, dashboards, or interactive tools.
2. **Frontend Parser**: Detect ` ```html ` blocks in incoming WebSocket messages.
3. **Split-View Layout**: Introduce a collapsible right-side panel in the Web UI to host the preview.
4. **Sandboxed iframe**: Render the generated HTML inside a sandboxed `<iframe>` to ensure security and prevent style/script leakage into the host Web UI.
5. **Local Bridge (Optional but Powerful)**: Allow the sandboxed iframe to communicate with the host Web UI via `window.parent.postMessage()`, enabling the generated UI to trigger local tool executions.

---

## 3. Detailed Design

### 3.1 Frontend UI Changes (`src/uagent/templates/`)
- **Layout**: Modify the main chat template to use a flexible flexbox/grid layout.
  - Left side: Chat history and input (60% width or adjustable).
  - Right side: Artifacts panel (40% width, collapsible, hidden by default).
- **Artifact Detection**:
  - When a message contains a ` ```html ` block, extract the content.
  - Instead of (or in addition to) showing the raw code in the chat, display an "Open in Preview" button or automatically open the right panel.
- **Rendering**:
  - Use an `<iframe>` with `sandbox="allow-scripts"` to render the HTML.
  - Set the `srcdoc` attribute of the iframe to the extracted HTML content.
  - Inject common CDN libraries (Tailwind CSS, Lucide Icons, Chart.js/Recharts) into the iframe if they are not already included, to make UI generation easier for the LLM.

### 3.2 LLM System Prompt Adjustments
To encourage the LLM to use this feature effectively, we can append a concise instruction to the system prompt (only when running in Web mode, or globally since it's safe for CLI/GUI):

```markdown
When the user asks for a UI, dashboard, interactive tool, or visualization:
1. Write a complete, self-contained HTML page inside a single ```html code block.
2. Use Tailwind CSS (via CDN) for styling and Lucide Icons or FontAwesome for icons.
3. Include interactive JavaScript (e.g., Chart.js for charts, or simple state management).
4. Do not split the code into multiple blocks; keep it in one unified ```html block.
```

### 3.3 The Local Bridge (Bi-directional Communication)
Since `uag` runs locally, we can establish a bridge between the generated UI and the local agent:

1. **Iframe to Host**:
   The generated JS inside the iframe can send data to the host Web UI:
   ```javascript
   window.parent.postMessage({
       type: "execute_tool",
       tool: "create_file",
       args: { filename: "data.json", content: "{...}" }
   }, "*");
   ```
2. **Host to Local Agent**:
   The host Web UI listens for these messages and forwards them to the FastAPI backend or executes them via the existing WebSocket/tool execution loop.
   - *Security Note*: Only allow safe, pre-approved actions or prompt the user for confirmation before executing any local tools triggered by the Generative UI.

---

## 4. Implementation Steps

### Step 1: Frontend Layout & Parser (HTML/JS)
- Update the CSS/HTML in the templates to support the split-view.
- Implement the JS parser to detect ` ```html ` blocks and extract the code.
- Implement the sandboxed iframe rendering logic.

### Step 2: LLM Prompt Integration
- Update `src/uagent/runtime_memory.py` or `src/uagent/core.py` to append the Generative UI instructions to the system prompt when the Web interface is active.

### Step 3: Local Bridge & API (Optional Enhancement)
- Implement `window.addEventListener("message", ...)` in the host Web UI.
- Create a secure endpoint or WebSocket handler in `web.py` to handle requests from the generated UI (e.g., saving data, running local scripts).

---

## 5. Security, Robustness & Edge Cases

### 5.1 Security (Sandboxing & Local Access)
- **Risk**: Although `sandbox="allow-scripts"` prevents the iframe from accessing the host's cookies, `localStorage`, or DOM, the scripts inside the iframe can still make network requests (e.g., `fetch()`) to `localhost` or external servers.
- **Mitigation**: 
  - Any action triggered via the "Local Bridge" (e.g., executing a tool or saving a file) **must require explicit user confirmation** on the host Web UI before execution.
  - Do not allow the iframe to execute arbitrary shell commands or raw Python code directly without strict whitelisting and user approval.

### 5.2 Offline Robustness (CDN Dependencies)
- **Risk**: UIs generated by the LLM often rely on external CDNs (Tailwind CSS, Lucide Icons, Chart.js). In offline or air-gapped environments, these UIs will fail to render correctly.
- **Mitigation**:
  - Document this limitation clearly.
  - (Optional Future Enhancement) Cache or bundle lightweight versions of Tailwind CSS and Chart.js in `src/uagent/static/` and inject local paths into the iframe's `srcdoc` if an offline mode is detected.

### 5.3 LLM Output Variations
- **Risk**: The LLM might output HTML using different code block tags (e.g., ` ```xml `, ` ```xhtml `) or omit the code block entirely, outputting raw HTML. It might also generate multiple HTML blocks in a single response.
- **Mitigation**:
  - The frontend parser should use a robust regex that detects both ` ```html ` blocks and standard HTML structures (e.g., starting with `<!DOCTYPE html>` or `<html>` and ending with `</html>`).
  - If multiple HTML blocks are found, the UI should default to rendering the latest one, while providing a dropdown or tab to switch between different generated artifacts.

### 5.4 Chat History & Persistence
- **Risk**: When the user refreshes the page or reloads a session, the generated UI preview might disappear.
- **Mitigation**:
  - Ensure the frontend message rendering loop parses historical messages for HTML blocks and restores the preview panel state when a session is loaded.

### 5.5 CLI/GUI Readability
- **Risk**: Long HTML blocks can clutter the terminal (CLI) or text area (GUI), making the text chat hard to read.
- **Mitigation**:
  - While out of scope for the initial Web UI implementation, future updates to `cli.py` and `gui.py` should consider collapsing or truncating extremely long HTML blocks (e.g., showing `[HTML Artifact - 150 lines]` with an option to view/save).

---

## 6. Impact Analysis## 5. Impact Analysis

- **CLI (`cli.py`)**: **No Impact**. The HTML code block is printed as standard text/Markdown.
- **GUI (`gui.py` / `scheckgui.py`)**: **No Impact**. The HTML code block is displayed in the text area.
- **A2A (`a2a/`)**: **No Impact**.
- **Performance**: Minimal. The iframe is only rendered when an HTML block is generated. CDN assets are cached by the browser.
- **Security**: High. The `sandbox="allow-scripts"` attribute prevents the generated UI from accessing the host's cookies, localStorage, or executing arbitrary code in the host's context.

---

## 6. Next Actions

1. Review this design document.
2. Locate the active HTML templates in `src/uagent/templates/` (e.g., `index.html`, `chat.html`).
3. Implement the split-view layout and iframe rendering logic.
