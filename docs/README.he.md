<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag - שער AI אוניברסלי</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Your environment, your freedom.
</p>

<p align="center">
  File ops / Web search / Image generation &amp; analysis / PDF &amp; Excel extraction / IoT control / MCP integration<br>
  15+ providers / 3 UIs / Parallel tool execution / Agent Skills marketplace
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Read this in your language</a>
</p>

---

## למה UAG?

**השתחרר מהנעילת הספק.** רוב עוזרי הבינה המלאכותית קושרים אותך לספק או לשירות ענן ספציפי. uag שונה.

- **פועל באופן מקומי** במחשב שלך. הנתונים שלך נשארים איתך (למעט קריאות API שאתה מבצע).
- **חופש הספק**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15+ ספקים, כולם נגישים מממשק אחד. החלף ביניהם על ידי הגדרה מחדש של משתני סביבה - ללא התקנה מחדש, ללא העברה.
- **131 כלים**: קלט/פלט של קבצים, חיפוש באינטרנט, יצירת תמונות, Gmail, סריקת מכשירי BLE, שילוב שרת MCP - **76 בטוחים במקביל** (עד 8 מופעלים במקביל דרך מאגר שרשורים, ניתנים להגדרה באמצעות `UAGENT_PARALLEL_WORKERS`). כאשר ה-LLM יורה שיחות כלים מרובות בו-זמנית, uag מקביל אותן באופן אוטומטי.
- **3 ממשקי משתמש + A2A**: CLI, GUI, אינטרנט ופרוטוקול סוכן לסוכן. אותו מנוע, כל ממשק.
- **מוכן ל-IoT**: SwitchBot, ECHONET Lite, Matter, UPnP - שלטו במכשירים הביתיים שלכם באמצעות AI.
- **מיומנויות סוכן**: התקן מיומנויות שנבנו בקהילה מהשוק. להאריך את uag בלי סוף.

uag הוא **עוזר הבינה המלאכותית שלך בתנאים שלך**. לא קשור לספק, לא קשור לממשק, לא קשור לפלטפורמה.

## התחלה מהירה

```bash
pip install uag
uag
```

בהפעלה הראשונה, אשף ההגדרה ילווה אותך דרך תצורת הספק.
ראה [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) עבור כל משתני הסביבה.

## תכונות

### 🧠 ארכיטקטורה מרובה ספקים

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax** / **Fuguana

כל הספקים חולקים את אותו ערכת כלים וממשק. החלף על ידי הגדרת 'UAGENT_PROVIDER' - ללא שינויי קוד, ללא התקנות נפרדות.

### ⚡ ביצוע כלי מקביל

כאשר ה-LLM מבקש מספר כלים בו-זמנית, uag **מקביל** אותם באופן אוטומטי.
76 כלים מסומנים 'x_parallel_safe' ומופעלים במקביל דרך 'ThreadPoolExecutor' (8 שרשורים כברירת מחדל; הגדר את 'UAGENT_PARALLEL_WORKERS' לשינוי).

**דוגמה**: שאל "בדוק את מזג האוויר בבירות נורדיות" → LLM מפעיל `search_web` × 5 מדינות → כל 5 החיפושים פועלים במקביל → התוצאות נאספו באצווה אחת.

כלים לקריאה בלבד (חיפוש קבצים, חישוב גיבוב, רישום ספריות, תרגום, שאילתות DB וכו') מקבילים בצורה אגרסיבית.

### 🔄 המשכיות הפגישה

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 כלים

| קטגוריה | כלים |
|---|---|
| **פעולות קובץ** | read/write/create/delete/search/grep/hash/zip, parse_eml (קבצי.eml) |
| **אינטרנט** | fetch_url, search_web, צילום מסך, browser_playwright |
| **מדיה** | gener_image, analys_image, img2img, audio_speech, audio_transscribe |
| **מסמכים** | חילוץ PDF/PPTX/DOCX/RTF/ODT, חילוץ מובנה של Excel |
| **תקשורת** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook — ראה [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (ענן + BLE), ECHONET Lite, Matter, UPnP |
| **כלי פיתוח** | git_ops, python_compile, lint_format, run_tests, db_query, **13 נווטי קוד מקור (משפחת idx)** |
| **MCP** | התחבר לשרתי MCP חיצוניים, רשום כלים, בצע |
| **A2A** | תקשורת סוכן לסוכן (עם מופעי uag אחרים או שרתים תואמי A2A) |
| **מערכת** | env vars, מפרט מערכת, זמן, חישוב תאריך |
| **נוב מקור** | **13 כלים idx** עבור Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL — קבל אינדקס פונקציה/מעמד או הגדרה ספציפית מבלי לקרוא את כל הקובץ |

### 🖥 4 ממשקים + הרחבת קוד VS

| מצב | פקודה | מטרה |
|---|---|---|
| **CLI** | `uag` | פעולה מהירה מבוססת טרמינלים |
| **GUI** | `uagg` | ממשק משתמש שולחני באמצעות tkinter |
| **אינטרנט** | `uagw` | גישה מבוססת דפדפן |
| **שרת A2A** | `uaga` | פרוטוקול Agent2Agent לתקשורת מרובת סוכנים |
| **קוד VS** | — | [הרחבה](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) עם לוח צ'אט, הסבר, Refactor, תיקון שגיאה ותצוגת עץ של כלים |

ראה [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) לפרטים על תוסף VS Code - התקנה, פקודות, חיבורי מקשים ותצורה.

### 🏠 בקרת מכשירי IoT

- **SwitchBot**: בקרת אצווה בענן וסריקה/בקרה BLE
- **ECHONET Lite**: גלה ושלוט במכשירי חשמל ביתיים (AC, אורות, מחממי מים וכו') ברשת המקומית
- **עניין**: בדיקה לקריאה בלבד של טופולוגיה של בקר/גשר/התקן
- **UPnP**: גילוי מכשירים והעברת יציאות IGD

ראה [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

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

ראה [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) לתיעוד מלא.

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

הקש על מקש 'x' כדי לצאת ממצב טייס אוטומטי (ראה [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ אוטומציה של דפדפן ומפקח אינטרנט

שני כלים משלימים המבוססים על מחזאי:

- **browser_playwright**: הפוך הפעלות דפדפן אמיתיות לאוטומטיות - נווט, לחץ, מלא טפסים, חילוץ נתונים, טפל בזרימות מרובי עמודים. עובד בלי ראש או עם ראש.
- **מחזאי_מפקח**: הקלט מעברי דפדפן, צלם תמונות DOM וצילומי מסך בכל שלב. שימושי לאיתור באגים באינטראקציות באינטרנט או לביקורת שינויים בדפים לאורך זמן.

### 🔄 טעינת כלים דינמיים

`כלים_קטלוג` ו`כלים_טעינת` מאפשרים לך לגלות ולאפשר כלים בזמן ריצה.
אין צורך לטעון הכל בעת ההפעלה - הפעל רק את מה שאתה צריך, כאשר אתה צריך את זה.

### 🌐 i18n / L10n

日本語 / אנגלית / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / ועוד.
הגדר את 'UAGENT_LANG' כדי לעבור. ראה [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) כדי להוסיף מקום חדש.

תרגומים של README זה זמינים ב-[docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 משתני סביבה מוצפנים

אחסן מפתחות וסודות API ב-`.env.sec` - קובץ `.env` מוצפן.
נהל עם `uag_envsec`.

## תצורה ופרטים

- **משתני סביבה**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **אשף ההתקנה**: `python -m uagent.setup_cli`
- **env מוצפן**: `uag_envsec` - הצפין `.env` בתור `.env.sec`
- **Responses API**: הגדר 'UAGENT_RESPONSES=1' למצב תגובות API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). מופעל אוטומטי עבור Sakana AI (Fugu).
- **מסמכי מפתח**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **טיפים קטנים LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## פילוסופיית הפרויקט

uag שואפת להיות **ה-AI שלך, במחשב שלך, בתנאים שלך.**

- אין תלות ב-SaaS - פועל באופן מקומי
- אין נעילת ספק - החלף בכל עת
- אין נעילת ממשק משתמש - CLI / GUI / אינטרנט / A2A
- ללא נעילת תכונה - הרחבה עם כלים ומיומנויות

חוויית סוכן בינה מלאכותית חינמית, ללא נעילת ספקים.
