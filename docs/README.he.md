<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>מודלי הבינה המלאכותית שלך. הכלים שלך. הסביבה שלך.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">שפות נוספות</a></p>

---

**UAG היא סביבת ריצה בקוד פתוח לסוכני בינה מלאכותית, המעדיפה עבודה מקומית.** היא מחברת את מודל השפה שתבחר לכלים ולמערכות שבהם אתה משתמש. ניתן לעבוד עם קוד, קבצים, דפדפנים, שירותים ומכשירים דרך ממשק אחיד, בלי להיות תלוי בספק מודלים אחד.

| **בחר מודל** | **חבר כלים אמיתיים** | **שמור על שליטה** |
| :--- | :--- | :--- |
| מודלים מקומיים ומתארחים כגון OpenAI, Claude, Gemini, Grok, Bedrock ו-Ollama | קבצים, קוד, אינטרנט, MCP, Agent Skills, תוספים, ענן ו-IoT | הרצה מקומית, אישור אנושי, אחסון פרטי גישה ומדיניות ניתנת להגדרה |

> UAG היא **שכבת הרצה לסוכנים, לא ספקית מודלים**. פניות למודלים ולשירותים חיצוניים תלויות בתצורה. העדפת הרצה מקומית אינה מבטיחה עבודה מלאה ללא אינטרנט או בידוד אוטומטי של כל הכלים.

## התחלה מהירה
<!-- README-SYNC:quick-start -->

נדרש **Python 3.11 ומעלה**. התקן את UAG מ-[PyPI](https://pypi.org/project/uag/) והפעל את ממשק שורת הפקודה האינטראקטיבי:

~~~bash
python -m pip install --upgrade uag
uag
~~~

בהפעלה הראשונה אשף ההתקנה מסייע לבחור ספק מודלים ולהגדיר פרטי גישה. אפשר גם להשתמש במשתני סביבה או במאגר אישורים. כדי להתקין מראש עוד תלויות של ספקים וכלים:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

לאחר מכן נסה את הבקשות הבאות:

~~~text
> מה השתנה במאגר Git הזה? סכם את הסיכונים.
> מצא את התיעוד העדכני ביותר לספרייה והסבר את שלבי המעבר.
> בדוק את הקבצים האלה והכן דוח קצר.
> :help
~~~

למשתמשים חדשים מומלץ לקרוא את מדריך ההתקנה ל-Windows, כולל Git וסביבות וירטואליות, ואת תיעוד התצורה: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## ממשקים
<!-- README-SYNC:interfaces -->

כל הממשקים משתמשים באותה סביבת ריצה ובאותו רישום כלים.

| ממשק | הפעלה | מתאים ל- |
| :--- | :--- | :--- |
| **CLI** | `uag` | מסוף ואוטומציה |
| **Desktop** | `uagg` | שיחות ביישום שולחני |
| **Web** | `uagw` | שיחות וחדרים בדפדפן |
| **A2A** | `uaga` | חיבור בין סוכנים |
| **VS Code** | [מדריך הרחבה](VSCODE.md) | עבודה לצד קוד המקור |

Desktop ו-Web דורשים תלויות נוספות שאינן כלולות בהתקנה הראשונית `uag[core,providers,tools]`:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

שרת האינטרנט עשוי לנסות להתקין FastAPI ו-Uvicorn בעת ההפעלה. התקנה מראש מונעת תלות בהתקנה האוטומטית. לפרטים: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## מה אפשר לבנות עם UAG
<!-- README-SYNC:capabilities -->

| יכולת | מה UAG מספקת |
| :--- | :--- |
| **תהליכים בלתי תלויים במודל** | החלפת ספק מקומי או מרוחק עם `UAGENT_PROVIDER` בלי לכתוב את הכלים מחדש |
| **קוד וקבצים** | ניווט במאגרים, בדיקות Git, lint, בדיקות תוכנה, עבודה עם קבצים ואוטומציית דפדפן |
| **כלים ניתנים להרחבה** | יותר מ-200 כלים, איתור דינמי באמצעות `tool_catalog` / `tool_load`, כלים מותאמים ב-Python וב-Rust |
| **סוכנים מחוברים** | MCP, A2A, תוספים תואמי Claude Code, Agent Skills וסוכני משנה |
| **משימות ארוכות** | טייס אוטומטי, קריאות עצמאיות במקביל, תזמון, שחזור ומפגשים שמורים |
| **מעבר למסוף** | ענן, תקשורת, מסמכים, מדיה, קול בזמן אמת ופרוטוקולי IoT נתמכים |

### סביבת ריצה אחת, חיבורים רבים
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

**דוגמאות לספקי מודלים נתמכים** מופיעות בהמשך. הגדרות ייעודיות מפורטות בתיעוד הסביבה.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### התאמה אישית עם כישורים ותוספים
<!-- README-SYNC:extensions -->

הרחב את UAG בלי לשנות את הליבה. התקן Agent Skills מ-SkillsMP או ClawHub, חבר שרתי MCP או טען תוספים תואמי Claude Code הכוללים כלים, כישורים, סוכנים ו-hooks.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

כלים מותאמים יכולים לספק `TOOL_SPEC` ו-`run_tool()`; נתמכים גם כלים המבוססים על Rust. מדריכים: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## מיועד לתהליכי עבודה אמיתיים
<!-- README-SYNC:workflows -->

### הקשר וזיכרון
<!-- README-SYNC:context-memory -->

אפשר לשמור פלטים גדולים של כלים כ**ארטיפקטים** במקום להעמיס על ההקשר הפעיל של המודל. בהמשך הסוכן קורא רק את החלק הנחוץ בעזרת `artifact_read`. מפגשים נשמרים כברירת מחדל ב-SQLite, עם חיפוש בהיסטוריה ובדיקה מפורשת של הזיכרון.

- [Context compression](CONTEXT_COMPRESSION.he.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### אוטומציה ושיתוף פעולה
<!-- README-SYNC:automation -->

UAG תומכת בקריאות עצמאיות מקבילות, תיאום בין סוכנים, שחזור מפגשים וטייס אוטומטי למשימות מרובות שלבים. מפעילים עם `:auto`; מקש **F12** עוצר את התשובה הנוכחית ומבקש לעצור את הטייס האוטומטי.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### אבטחה וניטור
<!-- README-SYNC:security -->

פעולות רגישות עשויות לדרוש אישור `human_ask`. ניתן לשמור פרטי גישה במנהל האישורים של מערכת ההפעלה או בקובץ מוצפן. ממשק Web תומך בהתחברות OIDC ובבקרת גישה לאחר הגדרה. מעקב ומדדים של OpenTelemetry הם **אופציונליים**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

הגנות אלה ניתנות להגדרה אך **אינן מבטיחות** שכל כלי ירוץ בבידוד בתוך ארגז חול. קרא את מדריכי הפריסה והמדיניות לפני פתיחת UAG למשתמשים או לרשתות שאינם מהימנים.

### שפות, מכשירים וקול
<!-- README-SYNC:languages -->

UAG מספקת משאבים ל-**38 הגדרות שפה** (אנגלית ו-37 תרגומים), יכולות קול דו-כיווני אופציונליות וכלים ל-SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP ו-OPC UA.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## תיעוד
<!-- README-SYNC:documentation -->

התחל במדריכים הבאים והעמק לפי הצורך:

| התחלה כאן | מידע נוסף |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

ניתן לעיין גם בכל התיעוד ובשפות האחרות: [Documentation](./) · [Other languages](README.translations.md).

## פיתוח ותרומה
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

לפני בקשת מיזוג המשנה **קוד Python**, יש להריץ בדיקות רלוונטיות ובקרות הפרויקט:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

כללי התרומה ומדריך המפתחים מופיעים בהמשך. נשמח לדיווחי באגים, שיפורי תיעוד, כלים, תרגומים ובקשות מיזוג ממוקדות: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## רישיון
<!-- README-SYNC:license -->

UAG מופצת תחת הרישיון: [Apache License 2.0](../LICENSE).
