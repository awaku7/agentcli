<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — שער AI אוניברסלי</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — הסביבה שלך, החופש שלך.
</p>

<p align="center">
  פעולות קבצים / חיפוש באינטרנט / יצירת וניתוח תמונות / חילוץ PDF ו-Excel / בקרת IoT / שילוב MCP<br>
  15+ ספקים / 3 ממשקי משתמש / ביצוע כלים מקביל / שוק מיומנויות סוכן
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">קרא את זה בשפה שלך</a>
</p>

---

## למה UAG?

**השתחרר מהנעילת הספק.** רוב עוזרי הבינה המלאכותית קושרים אותך לספק או לשירות ענן ספציפי. uag שונה.

- **פועל באופן מקומי** במחשב שלך. הנתונים שלך נשארים איתך (למעט קריאות API שאתה מבצע).
- **חופש הספק**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15+ ספקים, כולם נגישים מממשק אחד. החלף ביניהם על ידי הגדרה מחדש של משתני סביבה - ללא התקנה מחדש, ללא העברה.
- **112 כלים**: קלט/פלט קבצים, חיפוש באינטרנט, יצירת תמונות, סריקת מכשירי BLE, שילוב שרת MCP - ו-**55 מהם פועלים במקביל**. כאשר ה-LLM יורה מספר קריאות כלים בו-זמנית, uag מבצעת אותן אוטומטית באמצעות מאגר אשכולות.
- **3 ממשקי משתמש + A2A**: CLI, GUI, אינטרנט ופרוטוקול סוכן לסוכן. אותו מנוע, כל ממשק.
- **מוכן ל-IoT**: SwitchBot, ECHONET Lite, Matter, UPnP - שלטו במכשירים הביתיים שלכם באמצעות AI.
- **מיומנויות סוכן**: התקן מיומנויות שנבנו בקהילה מהשוק. להאריך את uag בלי סוף.

uag הוא **עוזר הבינה המלאכותית שלך בתנאים שלך**. לא קשור לספק, לא קשור לממשק, לא קשור לפלטפורמה.

## התחלה מהירה

```באש
pip install uag
uag
```

בהפעלה הראשונה, אשף ההגדרה ילווה אותך דרך תצורת הספק.
ראה [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) עבור כל משתני הסביבה.

## תכונות

### 🧠 ארכיטקטורה מרובה ספקים

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

כל הספקים חולקים את אותו ערכת כלים וממשק. החלף על ידי הגדרת 'UAGENT_PROVIDER' - ללא שינויי קוד, ללא התקנות נפרדות.

### ⚡ ביצוע כלי מקביל

כאשר ה-LLM מבקש מספר כלים בו-זמנית, uag **מקביל** אותם באופן אוטומטי.
55 כלים מסומנים 'x_parallel_safe' ומופעלים במקביל באמצעות 'ThreadPoolExecutor' בעל 4 חוטים.

**דוגמה**: שאל "בדוק את מזג האוויר בבירות נורדיות" → LLM מפעיל `search_web` × 5 מדינות → כל 5 החיפושים פועלים במקביל → התוצאות נאספו באצווה אחת.

כלים לקריאה בלבד (חיפוש קבצים, חישוב גיבוב, רישום ספריות, תרגום, שאילתות DB וכו') עוברים מקבילים באופן אגרסיבי.

### 🔄 המשכיות הפגישה

- **החלף ספק באמצע הסשן** עם `UAGENT_PROVIDER` - היסטוריית השיחות נשמרת.
- **טען מחדש את הפעלות הקודמות** עם `:load <index>` - המשך מהמקום שהפסקת.
- **שמירת תוצאות הכלי במטמון** מונעת ביצוע מחדש מיותר כאשר אותה קריאת כלי חוזרת.

### 🛠 112 כלים

| קטגוריה | כלים |
|---|---|
| **פעולות קובץ** | read/write/create/delete/search/grep/hash/zip |
| **אינטרנט** | fetch_url, search_web, צילום מסך, browser_playwright |
| **מדיה** | gener_image, analys_image, img2img, audio_speech, audio_transscribe |
| **מסמכים** | חילוץ PDF/PPTX/DOCX/RTF/ODT, חילוץ מובנה של Excel |
| **IoT** | SwitchBot (ענן + BLE), ECHONET Lite, Matter, UPnP |
| **כלי פיתוח** | git_ops, python_compile, lint_format, run_tests, db_query, **11 כלי idx** |
| **MCP** | התחבר לשרתי MCP חיצוניים, רשום כלים, בצע |
| **A2A** | תקשורת סוכן לסוכן (עם מופעי uag אחרים או שרתים תואמי A2A) |
| **מערכת** | env vars, מפרט מערכת, זמן, חישוב תאריך |
| **ניווט קוד מקור** | **11 כלי idx** (Python, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin) — קבל אינדקס פונקציות/מחלקות או הגדרה ספציפית מבלי לקרוא את כל הקובץ |

### 🖥 3 ממשקים + A2A

| מצב | פקודה | מטרה |
|---|---|---|
| **CLI** | `uag` | פעולה מהירה מבוססת טרמינלים |
| **GUI** | `uagg` | ממשק משתמש שולחני באמצעות tkinter |
| **אינטרנט** | `uagw` | גישה מבוססת דפדפן |
| **שרת A2A** | `uaga` | פרוטוקול Agent2Agent לתקשורת מרובת סוכנים |

### 🏠 בקרת מכשירי IoT

- **SwitchBot**: בקרת אצווה בענן וסריקה/בקרה BLE
- **ECHONET Lite**: גלה ושלוט במכשירי חשמל ביתיים (AC, אורות, מחממי מים וכו') ברשת המקומית
- **עניין**: בדיקה לקריאה בלבד של טופולוגיה של בקר/גשר/מכשיר
- **UPnP**: גילוי מכשירים והעברת יציאות IGD

ראה [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` כדי לדפדף ב-[SkillsMP](https://skillsmp.com) ו-[ClawHub](https://clawhub.ai) לקבלת כישורי קהילה.
התקן והרחיב את היכולות של uag תוך כדי תנועה.

### 🧩 מנהל מצב אצווה

uag יכול לעקוב אחר התקדמות לאורך משימות מרובות קבצים. כאשר ה-LLM מעבד עשרות קבצים, `batch_state` ממשיך את רשימת הקבצים הממתינים, שהושלמו ונכשלו לדיסק. אם ההפעלה מסתיימת או שהסבב נגמר, הריצה הבאה תתחדש מהמקום שבו היא נעצרה - שום דבר לא הולך לאיבוד.

### 🛡 אדם-בלולאה

`human_ask` מאפשר ל-LLM להשהות ולבקש את אישורך לפני ביצוע פעולות הרסניות (מחיקת קבצים, כתיבה, פקודות מעטפת). אתה נשאר בשליטה.

### 🕵️ אוטומציה של דפדפן ומפקח אינטרנט

שני כלים משלימים המבוססים על מחזאי:

- **browser_playwright**: הפוך הפעלות דפדפן אמיתיות לאוטומטיות - נווט, לחץ, מלא טפסים, חילוץ נתונים, טפל בזרימות מרובות עמודים. עובד בלי ראש או עם ראש.
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
- **Responses API**: הגדר 'UAGENT_RESPONSES=1' עבור מצב API של תגובות (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **מסמכי מפתח**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **טיפים קטנים LLM**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## פילוסופיית הפרויקט

uag שואפת להיות **ה-AI שלך, במחשב שלך, בתנאים שלך.**

- אין תלות ב-SaaS - פועל באופן מקומי
- אין נעילת ספק - החלף בכל עת
- אין נעילת ממשק משתמש - CLI / GUI / אינטרנט / A2A
- ללא נעילת תכונה - הרחבה עם כלים ומיומנויות

חוויית סוכן בינה מלאכותית בחינם, ללא נעילת ספקים.
