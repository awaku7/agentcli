<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - שער AI אוניברסלי</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — הסביבה שלך, החופש שלך.
</p>

<p align="center">
  פעולות קבצים / חיפוש באינטרנט / יצירה וניתוח של תמונות / PDF ו-Excel חילוץ / IoT בקרה / שילוב של MCP<br>
  24 providers / 3 ממשקי משתמש / ביצוע כלי מקביל / שוק Agent Skills
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## למה UAG?

**השתחרר מהנעילת הספק.** רוב עוזרי הבינה המלאכותית קושרים אותך לספק או לשירות ענן ספציפי. uag שונה.

- **פועל באופן מקומי** במחשב שלך. הנתונים שלך נשארים איתך (למעט קריאות API שאתה מבצע).
- **חופש הספק**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21+ ספקים, כולם נגישים מממשק אחד. החלף ביניהם על ידי הגדרה מחדש של משתני סביבה - ללא התקנה מחדש, ללא העברה.
- **222 כלים**: קלט/פלט של קבצים, חיפוש באינטרנט, יצירת תמונות, Gmail, סריקת מכשירי BLE, שילוב שרת MCP - **130 בטוחים במקביל** (עד 8 מופעלים במקביל דרך מאגר שרשורים, ניתנים להגדרה באמצעות `UAGENT_PARALLEL_WORKERS`). כאשר ה-LLM יורה שיחות כלים מרובות בו-זמנית, uag מקביל אותן באופן אוטומטי.
- **3 ממשקי משתמש + A2A**: CLI, GUI, אינטרנט ופרוטוקול סוכן לסוכן. אותו מנוע, כל ממשק.
- **מיומנויות סוכן**: התקן מיומנויות שנבנו בקהילה מהשוק. להאריך את uag בלי סוף.

uag הוא **עוזר הבינה המלאכותית שלך בתנאים שלך**. לא קשור לספק, לא קשור לממשק, לא קשור לפלטפורמה.

## התחלה מהירה

```bash
pip install uag
uag
```

בהפעלה הראשונה, אשף ההגדרה ילווה אותך דרך תצורת הספק.
ראה [docs/ENVIRONMENT.md](ENVIRONMENT.md) עבור כל משתני הסביבה.

## תכונות

### 🧠 ארכיטקטורה מרובה ספקים

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

כל הספקים חולקים את אותו ערכת כלים וממשק. החלף על ידי הגדרת 'UAGENT_PROVIDER' - ללא שינויי קוד, ללא התקנות נפרדות.

### ⚡ ביצוע כלי מקביל

כאשר ה-LLM מבקש מספר כלים בו-זמנית, uag **מקביל** אותם באופן אוטומטי.
130 כלים מסומנים 'x_parallel_safe' ומופעלים במקביל דרך 'ThreadPoolExecutor' (8 שרשורים כברירת מחדל; הגדר את 'UAGENT_PARALLEL_WORKERS' לשינוי).

**דוגמה**: שאל "בדוק את מזג האוויר בבירות נורדיות" → LLM מפעיל `search_web` × 5 מדינות → כל 5 החיפושים פועלים במקביל → התוצאות נאספו באצווה אחת.

כלים לקריאה בלבד (חיפוש קבצים, חישוב גיבוב, רישום ספריות, תרגום, שאילתות DB וכו') מקבילים בצורה אגרסיבית.

### 🧩 מערכת תוספים (תואמת Claude Code)

uagent מיישמת מערכת תוספים תואמת Claude Code. תוספים מאגדים מיומנויות, סוכנים, שרתי MCP, הוקים ועוד לתוך ספריות עצמאיות עם מניפסט `.claude-plugin/plugin.json`.

**רכיבים נתמכים: מיומנויות, סוכני משנה, שרתי MCP, הוקים (12 אירועי מחזור חיים), פקודות סלאש, סגנונות פלט, userConfig, תלויות, ערוצים, שווקים**

**CLI commands**:

```
:plugin list                         # רשימת תוספים מותקנים
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # התקנה מ-marketplace
:plugin remove <name>                # הסרת התקנה
:plugin enable/disable <name>        # החלפה
:plugin marketplace add/remove/list  # ניהול שווקים
:plugin init <name>                  # יצירת שלד לתוסף חדש
```

עיינו בתיעוד המלא לפרטים. [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md)

### 🔄 המשכיות הפגישה

- **החלפת ספק באמצע הסשן** עם `UAGENT_PROVIDER` — היסטוריית השיחה נשמרת.
- **טעינת סשנים קודמים מחדש** באמצעות `:load <index>` — המשיכו מהמקום שבו עצרתם.

### 🛠 222 כלים

| קטגוריה | כלים |
|---|---|
| **פעולות קובץ** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (קבצי.eml) |
| **אינטרנט** | fetch_url, search_web, צילום מסך, browser_playwright |
| **מדיה** | gener_image, analys_image, img2img, audio_speech, audio_transscribe |
| **מסמכים** | חילוץ PDF/PPTX/DOCX/RTF/ODT, חילוץ מובנה של Excel |
| **תחזית** | חיזוי סדרות זמן עם 9 מודלים (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM וכו'), בחירת מודל אוטומטית, יצירת גרפים, i18n |
| **תקשורת** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook , **pybitchat** (BLE Mesh) — ראה [COMMUNICATION.md](COMMUNICATION.md) and [BITCHAT.md](BITCHAT.md)|
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **ממשקי API בענן** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **כלי פיתוח** | git_ops, python_compile, lint_format, run_tests, db_query, **29 נווטי קוד מקור (משפחת idx)** |
| **MCP** | התחבר לשרתי MCP חיצוניים, רשום כלים, בצע — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | תקשורת סוכן לסוכן (עם מופעי uag אחרים או שרתים תואמי A2A) |
| **מערכת** | env vars, מפרט מערכת, זמן, חישוב תאריך, uuid_gen, slugify, quantities ||
| **נוב מקור** | **29 כלים idx** עבור Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — קבל אינדקס פונקציה/מעמד או הגדרה ספציפית מבלי לקרוא את כל הקובץ |

### 🖥 4 ממשקים + הרחבת קוד VS

| מצב | פקודה | מטרה |
|---|---|---|
| **CLI** | `uag` | פעולה מהירה מבוססת טרמינלים |
| **GUI** | `uagg` | ממשק משתמש שולחני באמצעות tkinter |
| **אינטרנט** | `uagw` | גישה מבוססת דפדפן |
| **שרת A2A** | `uaga` | פרוטוקול Agent2Agent לתקשורת מרובת סוכנים |
| **קוד VS** | — | [הרחבה](VSCODE.md) עם לוח צ'אט, הסבר, Refactor, תיקון שגיאה ותצוגת עץ של כלים |

ראה [VSCODE.md](VSCODE.md) לפרטים על תוסף VS Code - התקנה, פקודות, חיבורי מקשים ותצורה.

### 🏠 בקרת מכשירי IoT

- **עניין**: בדיקה לקריאה בלבד של טופולוגיה של בקר/גשר/התקן

ראה [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` כדי לדפדף ב-[SkillsMP](https://skillsmp.com) ו-[ClawHub](https://clawhub.ai) לקבלת כישורי קהילה.
התקן והרחיב את היכולות של uag תוך כדי תנועה.

### 🤖 טייס אוטומטי (`:auto`)

uag יכולה **לרדוף אחר יעד באופן אוטונומי על פני מספר סבבי LLM**. מושלם למשימות מורכבות מרובות שלבים שצריכות עידון איטרטיבי.

- **איך זה עובד**: לכל סבב יש שאילתה ראשית (שלב א') ואחריה שיקול דעת של המבקר (שלב ב') שמחליט "השלם או המשך?"
- **אותו ספק, אותו API**: שיקול הדעת משתמש בנתיב הקוד הזהה בתור השאילתה הראשית - כולל תמיכה ב-Respons API.
- **שופט נפרד LLM** (אופציונלי): הגדר את 'UAGENT_AP_PROVIDER' להשתמש בספק/דגם אחר עבור המבקר (למשל, השתמש במודל זול יותר לשיפוט).
- **צא בכל עת**: הקש על מקש 'x' כדי לעצור מיד, אפילו באמצע התגובה. או לתת למבקר להחליט מתי היעד מושג.
- **ניתן להגדרה**: `--max-rounds N` כדי לשלוט בתקציב.

ראה [README_AUTO.md](README_AUTO.md) לתיעוד מלא.

### 🧩 מנהל מצב אצווה

uag יכול לעקוב אחר התקדמות לאורך משימות מרובות קבצים. כאשר ה-LLM מעבד עשרות קבצים, `batch_state` ממשיך את רשימת הקבצים הממתינים, שהושלמו ונכשלו לדיסק. אם ההפעלה מסתיימת או שהסבב נגמר, הריצה הבאה תתחדש מהמקום שבו היא נעצרה - שום דבר לא הולך לאיבוד.

### 🛡 אדם-בלולאה

`human_ask` מאפשר ל-LLM להשהות ולבקש את אישורך לפני ביצוע פעולות הרסניות (מחיקת קבצים, כתיבה, פקודות מעטפת). אתה נשאר בשליטה.

### 🛑 פסיקה (מקש c / לחצן עצירה)

עצור את יצירת תגובת LLM בכל עת והזריק פקודת עצור בחזרה ל-LLM.

| ממשק | איך להפריע |
|---|---|
| **CLI** | הקש על מקש `c` במהלך הזרמת LLM - התגובה הנוכחית נעצרת, ו`"עצור"` נשלחת כהודעת משתמש כך שה-LLM מגיב בהתאם |
| **ממשק WEB** | לחץ על הלחצן האדום **■ עצור** (מופיע אוטומטית במהלך עיבוד LLM) |
| **ממשק משתמש למחשב שולחני** | לחץ על הלחצן האדום **■** (מופיע אוטומטית במהלך עיבוד LLM) |

ההפרעה פועלת כ"הזרקה מהירה": במקום פשוט להפסיק, היא מחזירה את `"עצור"` אל ה-LLM כהודעת משתמש, ומאפשרת לו לסיים בחינניות או לאשר את ההפרעה.

הקש על מקש 'x' כדי לצאת ממצב טייס אוטומטי (ראה [README_AUTO.md](README_AUTO.md)).

### 🕵️ אוטומציה של דפדפן ומפקח אינטרנט

שני כלים משלימים המבוססים על מחזאי:

- **browser_playwright**: הפוך הפעלות דפדפן אמיתיות לאוטומטיות - נווט, לחץ, מלא טפסים, חילוץ נתונים, טפל בזרימות מרובי עמודים. עובד בלי ראש או עם ראש.
- **מחזאי_מפקח**: הקלט מעברי דפדפן, צלם תמונות DOM וצילומי מסך בכל שלב. שימושי לאיתור באגים באינטראקציות באינטרנט או לביקורת שינויים בדפים לאורך זמן.

### 🔄 טעינת כלים דינמיים

`כלים_קטלוג` ו`כלים_טעינת` מאפשרים לך לגלות ולאפשר כלים בזמן ריצה.
אין צורך לטעון הכל בעת ההפעלה - הפעל רק את מה שאתה צריך, כאשר אתה צריך את זה.

### 🦀 Rust Native Tools

`uuid_gen` ו-`slugify` ממומשים ב-Rust (באמצעות PyO3) לשיפור הביצועים.

### 🌐 i18n / L10n

日本語 / אנגלית / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / ועוד.
הגדר את 'UAGENT_LANG' כדי לעבור. ראה [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) כדי להוסיף מקום חדש.

תרגומים של README זה זמינים ב-[docs/README.translations.md](README.translations.md).

### 🔒 משתני סביבה מוצפנים

אחסן מפתחות וסודות API ב-`.env.sec` - קובץ `.env` מוצפן.
נהל עם `uag_envsec`.

## תצורה ופרטים

- **משתני סביבה**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **אשף ההתקנה**: `python -m uagent.setup_cli`
- **env מוצפן**: `uag_envsec` - הצפין `.env` בתור `.env.sec`
- **Responses API**: הגדר 'UAGENT_RESPONSES=1' למצב תגובות API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). מופעל אוטומטי עבור Sakana AI (Fugu).
- **מסמכי מפתח**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **טיפים קטנים LLM**: [SLM_TIPS.md](SLM_TIPS.md)

## פילוסופיית הפרויקט

uag שואפת להיות **ה-AI שלך, במחשב שלך, בתנאים שלך.**

- אין תלות ב-SaaS - פועל באופן מקומי
- אין נעילת ספק - החלף בכל עת
- אין נעילת ממשק משתמש - CLI / GUI / אינטרנט / A2A
- ללא נעילת תכונה - הרחבה עם כלים ומיומנויות

חוויית סוכן בינה מלאכותית חינמית, ללא נעילת ספקים.

### ✨ צור כלים משלך

[he.md](TOOL_CREATOR_GUIDE.he.md)
לעיון במדריך שלב אחר שלב, ראו כאן.

## תרומה

תרומות יתקבלו בברכה! דוחות באגים, הצעות לתכונות, שיפורים בתיעוד, תרגומים ובקשות משיכה - הכל מוערך.

- **Issues**: פתח בעיה של GitHub עבור באגים או בקשות תכונה.
- **בקשות משיכה**: צרו fork של המאגר, בצעו את השינויים ושלחו PR. להגדרת סביבת הפיתוח ולהנחיות, עיינו ב-[DEVELOP.md](../src/uagent/docs/DEVELOP.md).

Realtime קול וAEC3

## Realtime מצב קול תומך במיקרופון דופלקס מלא ובקלט/פלט רמקול. אם הקצה העורפי AEC3 חסר, uag מתקין אוטומטית את pywebrtc-audio.

**ספקי זמן אמת**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice ו-Amazon Bedrock Nova Sonic. ה-SDK לסטרימינג דו-כיווני של Bedrock מותקן אוטומטית רק כאשר Bedrock נבחר.

```bat
python scheck.py realtime
```

AEC3 משתמש באות המיקרופון בפועל (קרוב) ובשמע שנשלח למעשה לרמקול (רחוק). אפשר אבחון רק בעת חקירת בעיות שמע.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime תומך באינטגרציה של Function Calling מוגבלת לבטיחות. המתאם הנוכחי חושף את הפונקציה לקריאה בלבד get_current_time באופן אוטומטי. כלים הרסניים ובקרות מכשירים דורשים רשימת היתרים וזרימת אישור מפורשת. Grok בזמן אמת משתמש במתאם נפרד ואינו משתמש בנתיב Function Calling הספציפי הזה ל-OpenAI.
