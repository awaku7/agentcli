<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Universal AI Gateway</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  20+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## Γιατί uag;

**Απαλλαγείτε από το κλείδωμα προμηθευτή.** Οι περισσότεροι βοηθοί τεχνητής νοημοσύνης σας συνδέουν με έναν συγκεκριμένο πάροχο ή υπηρεσία cloud. Το uag είναι διαφορετικό.

- **Εκτελείται τοπικά** στο μηχάνημά σας. Τα δεδομένα σας παραμένουν μαζί σας (εκτός από τις κλήσεις API που πραγματοποιείτε).
- **Ελευθερία παρόχου**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ πάροχοι, όλοι προσβάσιμοι από μια ενιαία διεπαφή. Εναλλάξτε μεταξύ τους ρυθμίζοντας εκ νέου τις μεταβλητές περιβάλλοντος — χωρίς επανεγκατάσταση, χωρίς μετεγκατάσταση.
- **195  εργαλεία**: I/O αρχείων, αναζήτηση ιστού, δημιουργία εικόνων, Gmail, σάρωση συσκευής BLE, ενσωμάτωση διακομιστή MCP — **111 είναι παράλληλα ασφαλή** (έως 8 εκτελούνται ταυτόχρονα μέσω νήμα, με δυνατότητα διαμόρφωσης μέσω "UAGENT_PARALLEL_WORKERS"). Όταν το LLM ενεργοποιεί πολλές κλήσεις εργαλείων ταυτόχρονα, το uag τις παραλληλίζει αυτόματα.
- **3 διεπαφές χρήστη + A2A**: Πρωτόκολλο CLI, GUI, Web και Agent-to-Agent. Ίδιος κινητήρας, οποιαδήποτε διεπαφή.
- **Δεξιότητες πράκτορα**: Εγκαταστήστε δεξιότητες που δημιουργούνται από την κοινότητα από την αγορά. Επεκτείνετε το uag ατελείωτα.

Το uag είναι **ο βοηθός τεχνητής νοημοσύνης με τους όρους σας**. Δεν συνδέεται με πάροχο, δεν συνδέεται με διεπαφή, δεν συνδέεται με πλατφόρμα.

## Γρήγορη εκκίνηση

```bash
pip install uag
uag
```

Κατά την πρώτη εκκίνηση, ο οδηγός εγκατάστασης σάς καθοδηγεί στη διαμόρφωση του παρόχου.
Δείτε το [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) για όλες τις μεταβλητές περιβάλλοντος.

## Χαρακτηριστικά

### 🧠 Αρχιτεκτονική πολλών παρόχων

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo/MaguStudio /*L* / **Together AI** / **Vercel AI Gateway**

Όλοι οι πάροχοι μοιράζονται το ίδιο σύνολο εργαλείων και διεπαφή. Εναλλαγή ορίζοντας "UAGENT_PROVIDER" — χωρίς αλλαγές κώδικα, χωρίς ξεχωριστές εγκαταστάσεις.

### ⚡ Παράλληλη εκτέλεση εργαλείου

Όταν το LLM ζητά πολλά εργαλεία ταυτόχρονα, το uag **τα παραλληλίζει αυτόματα**.
111 εργαλεία επισημαίνονται ως "x_parallel_safe" και εκτελούνται ταυτόχρονα μέσω ενός "ThreadPoolExecutor" (8 νήματα από προεπιλογή, ορίστε το "UAGENT_PARALLEL_WORKERS" για αλλαγή).

**Παράδειγμα**: Ρωτήστε "Έλεγχος του καιρού στις σκανδιναβικές πρωτεύουσες" → Το LLM ενεργοποιεί το `search_web` × 5 χώρες → και οι 5 αναζητήσεις εκτελούνται παράλληλα → αποτελέσματα που συλλέγονται σε μία παρτίδα.

Τα εργαλεία μόνο για ανάγνωση (αναζήτηση αρχείων, υπολογισμός κατακερματισμού, καταχώριση καταλόγου, μετάφραση, ερωτήματα DB, κ.λπ.) παραλληλίζονται επιθετικά.


### 🧩 Plugin System (Claude Code Compatible)

uagent implements a **Claude Code-compatible plugin system**. Plugins bundle skills, agents, MCP servers, hooks, and more into self-contained directories with a `.claude-plugin/plugin.json` manifest.

**Supported components**: Skills, Sub-agents, MCP servers, Hooks (12 lifecycle events), Slash commands, Output styles, userConfig, Dependencies, Channels, Marketplaces

**CLI commands**:
```
:plugin list                         # List installed plugins
:plugin install <source> [--scope]   # Install (dir/zip/git/http)
:plugin install <name>@<marketplace>  # Install from marketplace
:plugin remove <name>                # Uninstall
:plugin enable/disable <name>        # Toggle
:plugin marketplace add/remove/list  # Manage marketplaces
:plugin init <name>                  # Scaffold new plugin
```

See [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) for full documentation.


### 🔄 Συνέχεια συνεδρίας

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 195  Εργαλεία

| Κατηγορία | Εργαλεία |
|---|---|
| **Λειτουργίες αρχείων** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (αρχεία .eml) |
| **Ιστός** | fetch_url, search_web, screenshot, browser_playwright |
| **ΜΜΕ** | δημιουργία_εικόνας, ανάλυση_εικόνας, img2img, audio_speech, audio_transscribe |
| **Έγγραφα** | Εξαγωγή PDF/PPTX/DOCX/RTF/ODT, δομημένη εξαγωγή Excel |
| **Πρόβλεψη** | Πρόβλεψη χρονοσειρών με 9 μοντέλα (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, κ.λπ.), αυτόματη επιλογή μοντέλου, δημιουργία γραφημάτων, i18n |
| **Επικοινωνία** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook , **pybitchat** (BLE Mesh) — δείτε [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) and [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Εργαλεία προγραμματιστών** | git_ops, python_compile, lint_format, run_tests, db_query, **26 προγράμματα πλοήγησης πηγαίου κώδικα (οικογένεια idx)** |
| **MCP** | Σύνδεση σε εξωτερικούς διακομιστές MCP, λίστα εργαλείων, εκτέλεση |
| **A2A** | Επικοινωνία agent-to-agent (με άλλες παρουσίες uag ή διακομιστές συμβατούς με A2A) |
| **Σύστημα** | env vars, προδιαγραφές συστήματος, ώρα, υπολογισμός ημερομηνίας, uuid_gen, slugify ||
| **Πηγή Nav** | **26 εργαλεία idx** για Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — λάβετε ευρετήριο συνάρτησης/κλάσης ή συγκεκριμένο ορισμό χωρίς να διαβάσετε ολόκληρο το αρχείο |

### 🖥 4 διεπαφές + Επέκταση κώδικα VS

| Λειτουργία | Εντολή | Σκοπός |
|---|---|---|
| **CLI** | «uag» | Γρήγορη λειτουργία με βάση το τερματικό |
| **GUI** | `uagg` | UI επιφάνειας εργασίας μέσω tkinter |
| **Ιστός** | `uagw` | Πρόσβαση βάσει προγράμματος περιήγησης |
| **Διακομιστής A2A** | `uaga` | Πρωτόκολλο Agent2Agent για επικοινωνία πολλαπλών πρακτόρων |
| **Κωδικός VS** | — | [Επέκταση](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) με Πίνακας συνομιλίας, Εξήγηση, Επαναφορά, Διόρθωση σφάλματος και Εργαλεία Προβολή δέντρου |

Ανατρέξτε στο [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) για λεπτομέρειες σχετικά με την επέκταση κώδικα VS — εγκατάσταση, εντολές, πληκτρολογήσεις και διαμόρφωση.

### 🏠 Έλεγχος συσκευής IoT
- **Θέμα**: Επιθεώρηση μόνο για ανάγνωση της τοπολογίας ελεγκτή/γέφυρας/συσκευής

Δείτε το [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)


### 🎯 Agent Skills Marketplace

`:skills mp_search` για να περιηγηθείτε στο [SkillsMP](https://skillsmp.com) και στο [ClawHub](https://clawhub.ai) για δεξιότητες κοινότητας.
Εγκαταστήστε και επεκτείνετε τις δυνατότητες του uag on the fly.

### 🤖 Αυτόματος πιλότος (`:auto`)

Το uag μπορεί **αυτόνομα να επιδιώξει έναν στόχο σε πολλούς γύρους LLM**. Ιδανικό για σύνθετες εργασίες πολλαπλών βημάτων που χρειάζονται επαναληπτική βελτίωση.

- **Πώς λειτουργεί**: Κάθε γύρος έχει ένα κύριο ερώτημα (Βήμα Α) που ακολουθείται από μια κρίση αναθεωρητή (Βήμα Β) που αποφασίζει "ΟΛΟΚΛΗΡΩΣΗ ή ΣΥΝΕΧΕΙΑ;"
- **Ίδιος πάροχος, ίδιο API**: Η κρίση του αναθεωρητή χρησιμοποιεί την ίδια διαδρομή κώδικα ως κύριο ερώτημα — συμπεριλαμβανομένης της υποστήριξης του Responses API.
- **Ξεχωριστός κριτής LLM** (προαιρετικό): Ρυθμίστε το "UAGENT_AP_PROVIDER" ώστε να χρησιμοποιεί διαφορετικό πάροχο/μοντέλο για τον κριτικό (π.χ. χρησιμοποιήστε ένα φθηνότερο μοντέλο για την κρίση).
- **Έξοδος ανά πάσα στιγμή**: Πατήστε το πλήκτρο `x` για να σταματήσετε αμέσως, ακόμη και στη μέση της απόκρισης. Ή αφήστε τον αναθεωρητή να αποφασίσει πότε θα επιτευχθεί ο στόχος.
- **Δυνατότητα ρύθμισης**: `--max-rounds N` για έλεγχο του προϋπολογισμού.

Ανατρέξτε στο [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) για πλήρη τεκμηρίωση.

### 🧩 Διαχειριστής κατάστασης παρτίδας

Το uag μπορεί να παρακολουθεί την πρόοδο σε μακροχρόνιες εργασίες πολλών αρχείων. Όταν το LLM επεξεργάζεται δεκάδες αρχεία, το "batch_state" παραμένει στη λίστα των εκκρεμών, ολοκληρωμένων και αποτυχημένων αρχείων στο δίσκο. Εάν η περίοδος σύνδεσης τελειώσει ή λήξει ένα γύρο, η επόμενη εκτέλεση συνεχίζεται από το σημείο που σταμάτησε — τίποτα δεν χάνεται.

### 🛡 Human-in-the-Loop

Το `human_ask` επιτρέπει στο LLM να σταματήσει και να ζητήσει την επιβεβαίωσή σας πριν εκτελέσει καταστροφικές λειτουργίες (διαγραφή αρχείου, αντικαταστάσεις, εντολές φλοιού). Παραμένεις στον έλεγχο.

### 🛑 Διακοπή (πλήκτρο c / κουμπί Διακοπή)

Σταματήστε τη δημιουργία απόκρισης LLM ανά πάσα στιγμή και εισαγάγετε μια εντολή διακοπής πίσω στο LLM.

| Διεπαφή | Πώς να διακόψετε |
|---|---|
| **CLI** | Πατήστε το πλήκτρο `c` κατά τη ροή LLM — η τρέχουσα απόκριση σταματά και το "Stop"` αποστέλλεται ως μήνυμα χρήστη, ώστε το LLM να ανταποκρίνεται ανάλογα |
| **Διεπαφή χρήστη WEB** | Κάντε κλικ στο κόκκινο κουμπί **■ Stop** (εμφανίζεται αυτόματα κατά την επεξεργασία LLM) |
| **Γραφικό περιβάλλον εργασίας επιφάνειας εργασίας** | Κάντε κλικ στο κόκκινο κουμπί **■** (εμφανίζεται αυτόματα κατά την επεξεργασία LLM) |

Η διακοπή λειτουργεί ως "πρότυπη έγχυση": αντί απλώς να διακοπεί, τροφοδοτεί το "Stop"" πίσω στο LLM ως μήνυμα χρήστη, επιτρέποντάς του να ολοκληρώσει με χάρη ή να αναγνωρίσει τη διακοπή.

Πατήστε το πλήκτρο `x` για έξοδο από τη λειτουργία αυτόματου πιλότου (δείτε [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Αυτοματισμός προγράμματος περιήγησης και επιθεωρητής ιστού

Δύο συμπληρωματικά εργαλεία που βασίζονται σε θεατρικούς συγγραφείς:

- **browser_playwright**: Αυτοματοποιήστε πραγματικές περιόδους λειτουργίας προγράμματος περιήγησης — πλοήγηση, κλικ, συμπλήρωση φορμών, εξαγωγή δεδομένων, διαχείριση ροών πολλών σελίδων. Λειτουργεί ακέφαλο ή με κεφάλι.
- **playwright_inspector**: Καταγράψτε τις μεταβάσεις του προγράμματος περιήγησης, τραβήξτε στιγμιότυπα και στιγμιότυπα οθόνης DOM σε κάθε βήμα. Χρήσιμο για τον εντοπισμό σφαλμάτων αλληλεπιδράσεων ιστού ή τον έλεγχο αλλαγών σελίδας με την πάροδο του χρόνου.

### 🔄 Δυναμική φόρτωση εργαλείων

Το "tool_catalog" και το "tool_load" σάς επιτρέπουν να ανακαλύψετε και να ενεργοποιήσετε εργαλεία κατά την εκτέλεση.
Δεν χρειάζεται να φορτώσετε τα πάντα κατά την εκκίνηση — ενεργοποιήστε μόνο ό,τι χρειάζεστε, όταν το χρειάζεστε.


### 🦀 Rust Native Tools

`uuid_gen` and `slugify` are implemented in Rust (via PyO3) for performance.
They load directly from a pre-built `.pyd` — **no `pip install` required**.

External developers can also ship Rust-based tools: place a `.pyd` next to the
wrapper `.py`, use ``load_rust_pyd()`` from ``uagent.tools.rust_helper``, and
users get the tool without any extra dependencies. See
[TOOL_CREATOR_GUIDE.el.md](TOOL_CREATOR_GUIDE.el.md).

### 🌐 i18n / L10n

日本語 / Αγγλικά / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / και άλλα.
Ρυθμίστε το "UAGENT_LANG" για εναλλαγή. Ανατρέξτε στο [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) για να προσθέσετε μια νέα τοπική ρύθμιση.

Οι μεταφράσεις αυτού του README είναι διαθέσιμες στο [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Κρυπτογραφημένες μεταβλητές περιβάλλοντος

Αποθηκεύστε τα κλειδιά και τα μυστικά API στο «.env.sec» — ένα κρυπτογραφημένο αρχείο «.env».
Διαχείριση με «uag_envsec».

## Διαμόρφωση & Λεπτομέρειες

- **Μεταβλητές περιβάλλοντος**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Οδηγός εγκατάστασης**: `python -m uagent.setup_cli`
- **Κρυπτογραφημένο env**: "uag_envsec" — κρυπτογράφηση ".env" ως ".env.sec"
- **Responses API**: Ορίστε το "UAGENT_RESPONSES=1" για τη λειτουργία Responses API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Αυτόματη ενεργοποίηση για Sakana AI (Fugu).
- **Έγγραφα προγραμματιστή**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Μικρές συμβουλές LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Φιλοσοφία έργου

Το uag φιλοδοξεί να είναι **το AI σας, στον υπολογιστή σας, με τους όρους σας.**

- Χωρίς εξάρτηση SaaS — εκτελείται τοπικά
- Χωρίς κλείδωμα παρόχου — εναλλαγή ανά πάσα στιγμή
- Χωρίς κλείδωμα διεπαφής χρήστη — CLI / GUI / Web / A2A
- Χωρίς κλείδωμα λειτουργιών — επεκτείνετε με εργαλεία και δεξιότητες

Μια δωρεάν εμπειρία πράκτορα AI, χωρίς κλείδωμα προμηθευτή.

### ✨ Create Your Own Tools

Writing a new tool for uag is straightforward — create a single `.py` file with
`TOOL_SPEC` and `run_tool()`, place it in ``UAGENT_EXTERNAL_TOOLS_DIR``, and
it's immediately available. For Rust developers, ship a pre-built `.pyd` with
zero extra dependencies for users.

See [TOOL_CREATOR_GUIDE.el.md](TOOL_CREATOR_GUIDE.el.md)
for the step-by-step guide.

## Contributing

Contributions are welcome! Bug reports, feature suggestions, documentation improvements, translations, and pull requests — all appreciated.

- **Issues**: Open a GitHub issue for bugs or feature requests.
- **Pull requests**: Fork the repo, make your changes, and submit a PR. See [DEVELOP.md](../src/uagent/docs/DEVELOP.md) for development setup and guidelines.
- **Translations**: README translations and locale additions are welcome. See [ADD_LOCALE.md](../src/uagent/docs/ADD_LOCALE.md).
- **Tools & Skills**: New tool plugins and Agent Skills can be contributed via the marketplace.

Realtime Voice και AEC3

## Η λειτουργία Realtime φωνής υποστηρίζει είσοδο/έξοδο μικροφώνου και ηχείου full-duplex. Εάν λείπει το σύστημα υποστήριξης AEC3, το uag εγκαθιστά αυτόματα το pywebrtc-audio.

```bat
python scheck.py realtime
```

Το AEC3 χρησιμοποιεί το πραγματικό σήμα του μικροφώνου (κοντά) και τον ήχο που πραγματικά αποστέλλεται στο ηχείο (μακριά). Ενεργοποιήστε τα διαγνωστικά μόνο κατά τη διερεύνηση προβλημάτων ήχου.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime υποστηρίζει μια ενσωμάτωση Function Calling περιορισμένης ασφάλειας. Ο τρέχων προσαρμογέας εκθέτει αυτόματα τη λειτουργία get_current_time μόνο για ανάγνωση. Τα καταστροφικά εργαλεία και τα χειριστήρια συσκευών απαιτούν ρητή λίστα επιτρεπόμενων και ροή επιβεβαίωσης. Το Grok σε πραγματικό χρόνο χρησιμοποιεί έναν ξεχωριστό προσαρμογέα και δεν χρησιμοποιεί αυτήν τη διαδρομή Function Calling για το OpenAI.
