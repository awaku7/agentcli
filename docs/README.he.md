<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>שער AI אוניברסלי</strong><br>
  סוכן מקומי אחד. כל מודל. כל כלי. הסביבה שלכם, הכללים שלכם.
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
  <a href="https://github.com/awaku7/agentcli/discussions">דיונים</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">תרגומים</a>
</p>

______________________________________________________________________

**למה uag?**

uag הוא סוכן AI בגישה מקומית-תחילה, שמחבר את המודל המועדף עליכם לכלים שבהם אתם באמת משתמשים.
הוא מספק סביבת ריצה יחידה וניתנת להרחבה עבור קבצים, דפדפנים, בסיסי קוד, תקשורת, ממשקי ענן,
מכשירי IoT, שרתי MCP ותהליכי עבודה מרובי-סוכנים.

- **חופש בחירת ספק** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek ועוד.
- **ביצוע מקומי-תחילה** — סביבת הריצה של הסוכן וביצוע הכלים נשארים במחשב שלכם; רק קריאות ה-API שתבחרו עוזבות אותו.
- **שכבת כלים אחת** — אותם כלים פועלים דרך ה-CLI, ממשק שולחני, ממשק web, VS Code ו-A2A.
- **מקביליות מתוכננת מראש** — פעולות בלתי תלויות לקריאה בלבד יכולות לפעול במקביל.
- **ניתן להרחבה** — הוסיפו כלים, תוספים, Agent Skills, שרתי MCP וכלים מבוססי Rust בלי לשנות את הליבה.
- **מודע לבטיחות** — פעולות הרסניות, פרטי גישה, בקרות מכשירים וכתיבות לרשת תומכים באישור מפורש ובבקרות מדיניות.

> **בקיצור:** uag הוא מישור הבקרה שבין מודלי ה-AI שלכם לבין הסביבה האמיתית שלכם.

> **🧠 תוצאות כלי המותאמות להקשר** — תוצאות כלי גדולות מוחזקות מחוץ להקשר המודל הפעיל, ככל שהדבר אפשרי. uag מאחסן אותן כ-Artifacts ומעביר למודל תצוגה מקדימה מוגבלת עם הפניה יציבה ל-Artifact במקום זאת. הדבר יכול להפחית באופן משמעותי את מספר האסימונים הנדרשים בתורות הבאות כאשר כלי מייצר תוצאה גדולה.
> [מדריך מפורט לדחיסת הקשר](CONTEXT_COMPRESSION.he.md)

## התחלה מהירה

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

בהפעלה הראשונה נפתח אשף ההגדרה. הוא מסייע להגדיר ספק ושומר את ההגדרות שנבחרו
בסביבה המקומית שלכם.

עבור קבוצות היכולות הנפוצות:

```bash
python -m pip install "uag[core,providers,tools]"
```

> שילובי פלטפורמה הם אופציונליים. התקינו רק את מה שמערכת ההפעלה שלכם צריכה; ראו

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## ממשקים

| ממשק | פקודה | מתאים במיוחד ל- |
|---|---|---|
| **CLI** | `uag` | עבודה מהירה, בראש ובראשונה דרך המקלדת |
| **ממשק שולחני** | `uagg` | חוויית שולחן עבודה native |
| **ממשק Web** | `uagw` | גישה מבוססת דפדפן |
| **שרת A2A** | `uaga` | תקשורת בין סוכנים |
| **VS Code** | Extension | הסבר, ארגון מחדש, תיקון ועיון בכלים בתוך העורך |

כל הממשקים חולקים את אותה תצורת ספק, רשימת כלים, כללי בטיחות ונתוני הפעלות.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## מה אפשר לבנות

מתאמי ספקים מכסים סביבות ריצה מתארחות ומקומיות, ובכללן:

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

- לקרוא, ליצור, לערוך, לחפש, לחשב hash, לאחסן בארכיון ולבדוק קבצים
- לסקור שינויים ב-Git, לסרוק סודות, להריץ בדיקות, לבצע lint, לקמפל ולמדוד כיסוי
- לנווט בבסיסי קוד גדולים של Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA ושפות נוספות
- לבצע אוטומציה של דפדפנים באמצעות Playwright, כולל תהליכים מרובי-עמודים והורדות

- **MCP** — חיבור לשרתי כלים חיצוניים, כולל שירותים התומכים ב-OAuth
- **A2A** — תיאום עם סוכנים אחרים ושרתים תואמים
- **Cloud** — גישה לממשקי AWS, Google Cloud ו-Azure עם אישור לכתיבות
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams ו-pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA ו-UPnP
- **Media** — יצירה ועריכה של תמונות, תמלול ודיבור אודיו, צילום ממצלמה וקודי QR
- **Documents** — ניתוח PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL ולוגים

- **SwitchBot** — גילוי בענן וב-BLE, מצב, שליטה, אצווה ומינויים
- **ECHONET Lite** — גילוי ושליטה במכשירי חשמל ביתיים יפניים, כולל התראות INF
- **Matter** — נקודות קצה, אשכולות, מאפיינים, היסטוריית מצב, מינויים ושליטה
- **BACnet / Modbus TCP / OPC UA** — קריאה, כתיבה, עיון וניטור באוטומציית תעשייה ובניינים
- **UPnP** — גילוי מכשירים, מצב WAN וניהול מיפוי יציאות בנתבים

### היכן uag משתלב

uag נמצא בין אנשים וממשקים מצד אחד, לבין מודלים, כלים ומערכות בעולם האמיתי מצד שני.
הוא מתאם את השיחה, בוחר יכולות, מחיל כללי בטיחות ושומר על אפשרות להמשיך את תהליך העבודה.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### תוספים, Agent Skills ו-marketplaces

הפכו את uag לסוכן ייעודי בלי לפצל את ליבת הפרויקט:

- התקינו **תוספים תואמי Claude Code** מספרייה, ZIP, מאגר Git, מקור HTTP או marketplace
- אגדו skills, sub-agents, שרתי MCP, hooks, פקודות slash, סגנונות פלט, תלויות וערוצים
- עיינו ביכולות הקהילה דרך [SkillsMP](https://skillsmp.com) ו-[ClawHub](https://clawhub.ai)
- הוסיפו skills וכלים פרטיים של הארגון מקומית באמצעות `UAGENT_EXTERNAL_TOOLS_DIR`

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

ראו את [מדריך פיתוח התוספים](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md).

- **יותר מ-200 כלים** לקבצים, web, מדיה, מסמכים, קוד, ענן, תקשורת ו-IoT
- **גילוי וטעינה דינמיים** — השתמשו ב-`tool_catalog` כדי למצוא יכולות וב-`tool_load` כדי להפעיל אותן רק כשצריך
- **מודיעין קוד** — `code_map`, נווטי `idx` ייעודיים לשפות, סקירת Git, הרצת בדיקות, linting, קומפילציה וכיסוי
- **תוספים תואמי Claude Code** עם skills, agents, שרתי MCP, hooks, פקודות ו-marketplaces
- **Agent Skills** מ-SkillsMP ומ-ClawHub
- **כלי Python מותאמים אישית** עם `TOOL_SPEC` ו-`run_tool()`
- **כלים מבוססי Rust** להרחבות native קלות-משקל

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## נבנה עבור תהליכי עבודה אמיתיים

### 🧠 תוצאות כלי המותאמות להקשר

תוצאות כלי גדולות מוחזקות מחוץ להקשר המודל הפעיל, ככל שהדבר אפשרי. uag מאחסן אותן כ-Artifacts ומעביר למודל תצוגה מקדימה מוגבלת עם הפניה יציבה ל-Artifact במקום זאת. הדבר יכול להפחית באופן משמעותי את מספר האסימונים הנדרשים בתורות הבאות כאשר כלי מייצר תוצאה גדולה.

המשיכו שיחות קודמות באמצעות `:load <index>`. ניתן לשמור תוצאות כלים במטמון ולהחליף ספקים
בלי לבנות מחדש את היישום.

[Context compression](CONTEXT_COMPRESSION.he.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### טייס אוטומטי

השתמשו ב-`:auto` לעבודה מרובת סבבים עם מודל סוקר אופציונלי. הגדירו מגבלת סבבים באמצעות `--max-rounds N`.
לחצו על **F12** כדי לעצור את הטייס האוטומטי או על **F12** כדי לעצור את התגובה הנוכחית.

פעולות בלתי תלויות לקריאה בלבד פועלות במקביל כאשר הדבר בטוח. חיפושי web, בדיקת קבצים,
ניתוח מאגרים ועומסי עבודה דומים יכולים להסתיים במקביל באמצעות מאגר עובדים שניתן להגדיר
(`UAGENT_PARALLEL_WORKERS`). פעולות כתיבה נשארות סדרתיות או דורשות אישור.

רציפות הפעלה, שמירת תוצאות כלים במטמון, מצב אצווה, התאוששות מהפעלה מחדש, תזמון DAG
ותזמור רב-סוכנים הופכים עבודה מורכבת לניתנת להמשך במקום חד-פעמית.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 פרטי, רב-לשוני ומודע למדיניות

`human_ask` משהה את הפעולה לפני ביצוע פעולות רגישות. מחיקת קבצים, החלפות, פקודות shell, בקרות מכשירים,
פעולות על פרטי גישה וכתיבות לרשת יכולות להיות כפופות לכללי אישור ומדיניות.

השתמשו במאגר פרטי הגישה במקום להציב סודות ארוכי-טווח בפרומפטים:

ממשק המשתמש של ה-Web כולל כניסה באמצעות OIDC עם Authorization Code + PKCE, אסימוני זיהוי מאומתים, סשנים בצד השרת, ובקרות גישה לפרויקטים/חדרים. טענות קבוצת Microsoft Entra ID מאומתות יכולות להזין מדיניות גישה מבוססת ספרייה כאשר מוגדרות. פריסות Windows Active Directory, OAuth ו-trusted-proxy יכולות להשתלב דרך מתאמי זהות מאומתים מפורשים; Windows AD דורש מאמת Kerberos/Negotiate ספציפי לפריסה ואינו מופעל כברירת מחדל.

uag כולל מעקב ומדדים של OpenTelemetry שניתנים להפעלה לפי בחירה ואינם תלויים בספק, עבור פעולות Agent, LLM, כלי, Context, Memory ואחזור. יכולת התצפית מושבתת כברירת מחדל.

העדפת הרצה מקומית אינה אומרת ש-UAG פועל כברירת מחדל ללא חיבור לרשת או שכל הכלים מבודדים. פניות למודלים חיצוניים ולשירותים מחוברים תלויות בתצורה.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 תרגום רב-לשוני

- `translate_text` תומך ב-Google Translate ובקליינט ה-Python הרשמי של DeepL באמצעות `provider=auto`, `provider=deepl` או `provider=google`.
- הגדרות הכלים זמינות ב-37 שפות מקומיות בנוסף לאנגלית (38 בסך הכל), תוך שמירה על סימני מילוי ומזהים טכניים.

קול דו-כיווני מלא זמין דרך OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live
ו-Bedrock Nova Sonic, עם ביטול הד מובנה אופציונלי AEC3 וקריאות פונקציות בזמן אמת המוגבלות מטעמי בטיחות.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## תיעוד

| נושא | תיעוד |
|---|---|
| משתני סביבה | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| ארכיטקטורה ואינווריאנטים | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| כלי המאגר | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| מקרי שימוש ב-IoT | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| כלי תקשורת | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| טייס אוטומטי | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| תוסף VS Code | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| מדריך למפתחים | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| זרימת כלים | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## פיתוח ותרומה

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

הריצו את הבדיקות שלפני PR:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

לתהליך הפיתוח המלא, ראו [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md).

דיווחי באגים, רעיונות לתכונות, שיפורי תיעוד, תרגומים, כלים, skills ובקשות pull יתקבלו בברכה.
אנא פתחו issue או דיון לפני שינויים גדולים. קראו את [מדריך המפתחים](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
והריצו את הבדיקות שלעיל לפני שליחת pull request.

## רישיון

מופץ בכפוף ל-[Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE).
