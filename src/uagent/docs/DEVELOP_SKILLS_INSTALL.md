# DEVELOP_SKILLS_INSTALL (Skills Installation Specification)

This document defines the requirements and design for the skill installation and uninstallation features in **uag**.

## 1. Goal
Provide a unified, robust, and user-friendly mechanism to install, update, and uninstall Agent Skills from various sources into/from a centralized local directory (`~/.uag/skills`).

## 2. Target Directory
- Primary installation directory: `~/.uag/skills` (resolved as `os.path.expanduser("~/.uag/skills")`).
- This directory should be automatically added to the default skill roots searched by `get_default_skill_roots` in `agent_skills_shared.py`.

## 3. Supported Source Formats
The installation tool must automatically detect the format of the source and handle it appropriately:

| Source Type | Pattern / Detection | Action |
|---|---|---|
| **Git Repository** | Starts with `git@`, `http://`, `https://` AND ends with `.git` (or is a known Git host like github.com/gitlab.com) | Run `git clone <url> <dest_dir>`. If the directory already exists, run `git pull` to update. |
| **Remote ZIP Archive** | Starts with `http://` or `https://` AND ends with `.zip` (or contains `/archive/` / `/zip/`) | Download the ZIP file to a temporary location, verify size, and extract it into `<dest_dir>`. |
| **Local Directory** | Valid local directory path | Copy the directory recursively to `<dest_dir>`. |
| **Local ZIP Archive** | Valid local file path ending with `.zip` | Extract the ZIP file into `<dest_dir>`. |

## 4. Command Interface
New subcommands `install` and `uninstall` will be added to the `:skills` command:

```
:skills install <source> [name]
:skills uninstall <name>
```

- `<source>`: The Git URL, ZIP URL, local directory, or local ZIP file.
- `[name]` / `<name>`: The destination folder name under `~/.uag/skills`. For `install`, if omitted, it is inferred from the source (e.g., repository name or ZIP filename).

### Example Usage:
- `:skills install https://github.com/microsoft/win-dev-skills.git`
- `:skills install https://example.com/skills/my-custom-skill.zip`
- `:skills install C:\path\to\local\my-skill`
- `:skills uninstall win-dev-skills`

## 5. Tool Specification (`skills_install_tool` & `skills_uninstall_tool`)
Two new tools will be registered under `src/uagent/tools/skills_install_tool.py` and `src/uagent/tools/skills_uninstall_tool.py`.

Additionally, corresponding localization JSON files (`skills_install_tool.json` and `skills_uninstall_tool.json`) must be created in the same directory to support multi-language tool descriptions and parameters via `make_tool_translator`. These JSON files must include translations for all supported languages (en, ja, es, fr, ko, de, it, etc.) to maintain consistency with other tools.

### 5.1 `skills_install` Spec (JSON Schema):
```json
{
  "name": "skills_install",
  "description": "Install or update an Agent Skill from a Git repository, remote ZIP, local directory, or local ZIP file into ~/.uag/skills.",
  "parameters": {
    "type": "OBJECT",
    "properties": {
      "source": {
        "type": "STRING",
        "description": "The source URL or path (Git URL, HTTP ZIP URL, local directory, or local ZIP)."
      },
      "name": {
        "type": "STRING",
        "description": "Optional destination folder name. If not specified, it will be inferred from the source."
      },
      "overwrite": {
        "type": "BOOLEAN",
        "description": "Whether to overwrite or update the destination if it already exists. Defaults to true.",
        "default": true
      }
    },
    "required": ["source"]
  }
}
```

### 5.2 `skills_uninstall` Spec (JSON Schema):
```json
{
  "name": "skills_uninstall",
  "description": "Uninstall an Agent Skill from ~/.uag/skills.",
  "parameters": {
    "type": "OBJECT",
    "properties": {
      "name": {
        "type": "STRING",
        "description": "The folder name of the skill to uninstall."
      }
    },
    "required": ["name"]
  }
}
```

### Return Value (Both Tools):
A JSON string containing:
- `ok`: Boolean indicating success.
- `path`: The absolute path where the skill was installed or uninstalled.
- `message`: A status or error message.

## 6. Dynamic Command Registration System
To maintain high modularity and prevent core code bloat, a dynamic command registration system is introduced. This allows tools to define their own CLI commands/subcommands.

### 6.1 Command Specification (`CMD_SPEC`)
A tool module can optionally export a `CMD_SPEC` dictionary:

```python
CMD_SPEC = {
    "command": "skills",       # The main command (e.g., :skills)
    "subcommand": "install",   # The subcommand (e.g., install)
    "handler": handler_func    # The function to execute when the command is run
}
```

### 6.2 Registration Lifecycle
1. During startup, `tools/__init__.py` scans and loads all tool modules.
2. If a module exports a valid `CMD_SPEC`, it is registered in a global registry `_DYNAMIC_COMMANDS`.
3. When a command is executed in the CLI, `util_tools.py` checks the dynamic registry first. If a matching handler is found, it is executed.
4. If a tool is disabled or not loaded, its corresponding commands automatically become unavailable.

## 7. Security & Safety Constraints
- **Directory Traversal**: Ensure the destination folder name `[name]` does not contain path traversal sequences (e.g., `..`, `/`, `\`). It must be a single directory name.
- **ZIP Bomb Protection**: Limit the maximum uncompressed size of extracted ZIP files (e.g., max 50MB) and maximum file count (e.g., max 1000 files).
- **Git Command Check**: If Git is required but not installed/available in PATH, return a clear error message suggesting the ZIP fallback or installing Git.
- **Input Validation**: Validate that the source is not empty and conforms to expected formats.
