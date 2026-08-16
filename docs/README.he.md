<p align="center">
 <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">1__PHAI align="center">1uag align="center">
 <b>U</b>niversal <b>A</b>I <b>G</b>ateway — הסביבה שלך, החופש שלך.
</p>

<p align="center">
 פעולות קבצים / חיפוש Web / יצירה וניתוח של תמונות / חילוץ PDF ו-Excel / שליטה ב-IoT / 2 MCP רכיבי UI / < MCP ביצוע כלים מקביל / Agent Skills Marketplace
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">Py ·</a>
 href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">קרא את זה בשפה שלך</a>
</p>

______________________________________________________________________

## למה uag?

**השתחרר מהנעילת הספק.** רוב עוזרי הבינה המלאכותית קושרים אותך לספק או לשירות ענן ספציפי. uag שונה.

- **פועל באופן מקומי** במחשב שלך. הנתונים שלך נשארים איתך (למעט API שיחות שאתה מבצע).
- **חופש הספק**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 ספקים, כולם נגישים מממשק יחיד. החלפה ביניהם על ידי הגדרה מחדש של משתני סביבה - ללא התקנה מחדש, ללא העברה.
- **222 כלים**: קלט/פלט של קבצים, חיפוש אינטרנט, יצירת תמונות, Gmail, סריקת מכשירי BLE, שילוב שרתים MCP - **130 מסומנים סטטית כבטוחים במקביל** (עד 8 מופעלים במקביל דרך מאגר שרשורים, ניתן להגדרה באמצעות ALL_WENT_PAR). כאשר LLM מפעיל מספר שיחות כלים בו-זמנית, uag מקביל אותן באופן אוטומטי.
- **3 ממשקי משתמש + A2A**: CLI, GUI, Web ופרוטוקול סוכן לסוכן. אותו מנוע, כל ממשק.
- **מוכן ל-IoT**: SwitchBot, ECHONET Lite, Matter, UPnP - שלטו במכשירים הביתיים שלכם באמצעות AI.
- **מיומנויות סוכן**: התקן מיומנויות שנבנו בקהילה מהשוק. הארך את uag ללא סוף.

uag הוא **עוזר הבינה המלאכותית שלך בתנאים שלך**. לא קשור לספק, לא קשור לממשק, לא קשור לפלטפורמה.

## התחלה מהירה

```bash
pip התקנת uag
uag
```

בהפעלה הראשונה, אשף ההגדרה ידריך אותך דרך תצורת הספק.
עיין ב-[docs/ENVIRONMENT.md](https://github.com/awadocku7/agentincli/environment/environment/environment.html) משתנים.

## Computer Use

Computer Use מצטרף ותומך הן בזמן ריצה גלוי של הדפדפן Playwright
והן בזמן ריצה של שולחן העבודה. כאשר מופעל, שני זמני הריצה נוצרים ונרשמים;

````bat
set UAGENT_COMPUTER_USE=1
`להשתמש בשולחן העבודה במקום הפעלה של שולחן העבודה. Runtime משאבים
סגורים יחד ביציאה רגילה, `Ctrl-C` ובכיבוי התהליך. הגדר
`UAGENT_COMPUTER_HEADLESS=1` עבור בדיקות CI או עשן מבוססי דפדפן.
עיין ב-[docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
לפרטי השילוב והבטיחות.

## קול בזמן אמת ו-AEC3

מצב הקול בזמן אמת תומך ב-OpenAI בזמן אמת, Azure OpenAI GPT בזמן אמת, xAI Grok קול API, Google Gemini Multimodal Live API ובמיקרופון אמזון Bedrock Nova Sonic ורמקול מלא דופלקס. הקצה האחורי 'pywebrtc-audio' AEC3 הנדרש מותקן אוטומטית, וה-SDK האופציונלי של Bedrock להזרמת סטרימינג דו-כיוונית מותקן אוטומטית רק כאשר נבחר ספק ה-Bedrock:

```bash
python scheck.py realtime
````

ה-AEC3 ה-AEC3\`\`מקבל את האות בפועל של מיקרופון השמע ל-AEC3` (`רחוק\`) כדי שהעוזר יוכל להקשיב תוך כדי דיבור. הפעל אבחון רק בעת חקירת בעיות אודיו:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI פונקציית זמן אמת שיחות

OpenAI פונקציה בטיחות-זמן אמת אינטגרציה תומכת בשיחה. המתאם הנוכחי בזמן אמת חושף לקריאה בלבד את 'get_current_time' באופן אוטומטי. כלים הרסניים ובקרות מכשירים אינם נחשפים ללא רשימת היתרים וזרימת אישור מפורשת. Grok בזמן אמת משתמש במתאם נפרד ואינו משתמש בנתיב הקריאה לפונקציה הספציפית הזו ל-OpenAI.

## מאפיינים

### 🧠 ארכיטקטורת ספקים מרובים

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Claude / Grok / ZAIPU / ZAIPU /. AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

כל הספקים חולקים את אותם כלים וממשק. החלף על ידי הגדרת 'UAGENT_PROVIDER' — ללא שינויי קוד, ללא התקנות נפרדות.

#### Ollama ו-llama.cpp

Ollama ו-llama.cpp הם ספקים נפרדים. אולמה משתמשת בניהול שירות ומודל משלה, בעוד ש-`llama.cpp` מתחבר לנקודת קצה תואמת `לאמה-שרת` OpenAI:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1

# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEYdum=`llama . הספק משתמש בנתיב התואם ל-Chat Completions. שמור על `UAGENT_RESPONSES=0` אלא אם מוגדר פרוקסי תואם.

### ⚡ ביצוע כלי מקביל

כאשר LLM מבקש מספר כלים בו-זמנית, uag **מקביל באופן אוטומטי** אותם.
130 כלים 'safe_' מסומנים באופן סטטי כ-'safe_' כלים. `ThreadPoolExecutor` (8 שרשורים כברירת מחדל; הגדר את `UAGENT_PARALLEL_WORKERS` לשינוי).

**דוגמה**: שאל "בדוק את מזג האוויר בבירות נורדיות" → LLM יורה `search_web` × 5 מדינות → כל 5 החיפושים פועלים במקביל 

**הכלי שנאסף על בסיס מודול אחד מוגדר על בסיס מודול נוכחי. a `TOOL_SPEC` (כרגע 222, כולל 2 הכלים בעלי גיבוי חלודה ב-`src/uagent/tools_rust/`). `http_request` משתמש בבטיחות רגישה לשיטה: קריאות `GET`/`HEAD`/`OPTIONS` עשויות לפעול במקביל, בעוד ששיטות הכתיבה נשארות טוריות.

כלים לקריאה בלבד (חיפוש קבצים, חישוב גיבוב, רישום ספריות, תרגום, שאילתות DB וכו') עוברות במקביל במקביל.

__#4 מערכת Plugin תואם)

uagent מיישמת מערכת **Claude תואמת תוסף קוד**. תוספים מאגדים מיומנויות, סוכנים, MCP שרתים, הוקס ועוד לתוך ספריות עצמאיות עם מניפסט של `.claude-plugin/plugin.json`.

**רכיבים נתמכים**: מיומנויות, סוכני משנה, MCP שרתים, Hooks (12 אירועים במחזור חיים), פקודות Slash, תלויות במשתמש, פלט, סגנונות Marketplaces

**CLI פקודות**:

```

:plugin list # רשימת תוספים מותקנים
:plugin install <source> [--scope] # Install (dir/zip/git/http)
:plugin install <name>@<marketplace> # Install from market

> : #plugin remove en Toggle
> :plugin marketplace add/remove/list # Manage Marketplaces
> :plugin init <name> # Scaffold new plugin

````

ראה [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) לתיעוד מלא 🔎# Session 🏄 המשכיות

- **החלף ספק באמצע הסשן** עם `UAGENT_PROVIDER` — היסטוריית השיחות נשמרת.
- **טען מחדש הפעלות קודמות** עם `:load <index>` — המשך מהמקום שהפסקת.
- **שמירת תוצאות הכלי במטמון** מונעת ביצוע חוזר מיותרות ⎏ 9 כלים

| קטגוריה | כלים |
|---|---|
| **פעולות קובץ** | read/write/create/delete/search/grep/hash/zip, file_type, parse_eml (קבצי.eml), `path_alias` |
| **Web** | fetch_url, search_web, screenshot, browser_playwright, `url_alias`, `public_transit_route` ([מדריך](docs/PUBLIC_TRANSIT_ROUTE.md)) |
| **מדיה** | gener_image, analys_image, img2img, audio_speech, audio_transcribe |
| **מסמכים** | חילוץ PDF/PPTX/DOCX/RTF/ODT, חילוץ מובנה של Excel |
| **תחזית** | חיזוי סדרות זמן עם 9 דגמים (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM וכו'), בחירת דגם אוטומטי, יצירת עלילה, i18n |
| **תקשורת** | gmail_send, gmail_read, bluesky, discord_channel, teams_webhook, **pybitchat** (BLE Mesh) - ראה [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) ו [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) |
| **IoT** | SwitchBot (Cloud + BLE), ECHONET Lite, Matter, UPnP, reverse_geocode |
| **ממשק API של ענן** | `aws_api`, `gcp_api`, `azure_api` - פעולות כלליות של AWS, Google Cloud וAzure API; פעולות כתיבה דורשות אישור מפורש |
| **כלי פיתוח** | workspace_status, git_ops, git_review, security_scan, coverage_report, python_compile, lint_format, run_tests, db_query, **29 קוד מקור נווט (משפחת idx)** |
| **MCP** | התחבר לשרתים MCP חיצוניים, רשום כלים, בצע - [OAuth / Proxy guide](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | תקשורת בין סוכן לסוכן (עם uag מופעים אחרים או שרתים תואמים A2A) |
| **מערכת** | env vars, מפרט מערכת, זמן, חישוב תאריך, [quantities](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **נוב מקור** | **29 כלים idx** עבור Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile — קבל אינדקס פונקציה/מחלקה או הגדרה ספציפית בלי לקרוא את כל הקובץ |

#####

####
 דווח על כיסוי_מצב מאגר פעיל: ענף Git של סביבת העבודה, שינויים, מצב סנכרון במעלה הזרם, זמן ריצה Python וסמני פרוייקט נפוצים ללא שינוי קבצים.
- `git_review`: סיכום שינויים ב-Git, קבצים מסוכנים, מועמדי בדיקה וממצאים סודיים מבלי לחשוף ערכים סודיים.
- `security_scan`: סריקת קבצי מאגר וסיכון סבירים עבור קבצי קונפיגורציה וסיכון `coverage_report`: הפעל ונרמל את הכיסוי עבור Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby, PHP, Swift ו-Dart/Flutter.
- ניתן להתקין תלות כיסוי חסרות באופן אוטומטי כאשר מתבקשת ביצוע; `dry_run` אף פעם לא מתקין חבילות.

עיין ב[כלי ניתוח מאגר](docs/REPOSITORY_TOOLS.md) לפרמטרים, פלט ופרטי בטיחות.

ראה [כינויים של נתיב וכתובת URL](docs/PATH_URL_ALIASES.md) לקיצור נתיבי קבצים חוזרים ו-#
 נתיבי קבצים חוזרים. 🖥 4 ממשקים + הרחבת קוד VS

| מצב | פקודה | מטרה |
|---|---|---|
| **CLI** | `uag` | פעולה מהירה מבוססת טרמינלים |
| **GUI** | `uagg` | ממשק משתמש למחשב שולחני באמצעות tkinter |
| **Web** | `uagw` | גישה מבוססת דפדפן |
| **A2A שרת** | `uaga` | פרוטוקול Agent2Agent לתקשורת מרובת סוכנים |
| **קוד VS** | — | [הרחבה](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) עם פאנל צ'אט, הסבר, Refactor, תיקון שגיאה ותצוגת עץ של כלים |

עיין ב-[VSCODE.md](https://github.com/awaku7/agentcli/blob/VSCODE ב-VSdocODE/VSCODE לפרטים על ההתקנה - קוד VSdocODE/VSCODE. פקודות, חיבורי מקשים ותצורה.

### 🏠 IoT Device Control

- **BACnet**: קריאה/כתיבה של התקני BACnet/IP (HVAC, תאורה, מדי כוח). מנוי COV להתראות דחיפה
- **Modbus TCP**: קריאה/כתיבה של אוגרי החזקה/קלט וסלילים. ניטור שינויים מבוסס סקרים
- **OPC UA**: דפדוף במרחב כתובות, קריאה/כתיבה משתנים, הירשם לשינויים בנתונים
- **SwitchBot**: בקרת אצווה בענן וסריקה/בקרה BLE. מנוי מבוסס סקרים
- **ECHONET Lite**: גלה, שלט והירשם להודעות INF ממכשירי חשמל ביתיים (AC, תאורה, מחממי מים וכו')
- **עניין**: בקרת קריאה/כתיבה + מנוי לניטור שינוי מצב
- **UPnP**:
גילוי העברת מכשירים ו-IGD [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:skills mp_search` כדי לדפדף ב-[SkillsMP].com].com](skillsmplaw) ו-https://skillsmplaw for community. מיומנויות.
התקן והרחיב את היכולות של uag תוך כדי תנועה.

### 🤖 טייס אוטומטי (`:auto`)

uag יכול **לרדוף אחר מטרה באופן אוטונומי לאורך LLM סבבים מרובים**. מושלם למשימות מורכבות מרובות שלבים שצריכות חידוד איטרטיבי.

- **איך זה עובד**: לכל סבב יש שאילתה ראשית (שלב א') ואחריה פסק דין של המבקר (שלב ב') שמחליט "השלמה או המשך?"
- **אותו ספק, אותו ספק, אותו קוד הביקורת API** זהה: כולל תגובות API תמיכה.
- **שופט נפרד LLM** (אופציונלי): הגדר את 'UAGENT_AP_PROVIDER' להשתמש בספק/דגם אחר עבור המבקר (למשל השתמש במודל זול יותר לשיפוט).
- **צא בכל עת**: הקש על מקש 'x' כדי להפסיק מיד, אפילו באמצע התגובה. או תן למבקר להחליט מתי היעד מושג.
- **ניתן להגדרה**: `--max-rounds N` כדי לשלוט בתקציב.

עיין ב-[README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) לתיעוד מלא 🏎#
ch מנהל

uag יכול לעקוב אחר התקדמות במשימות מרובות קבצים ארוכות. כאשר LLM מעבד עשרות קבצים, `batch_state` ממשיך את רשימת הקבצים הממתינים, שהושלמו ונכשלו לדיסק. אם ההפעלה מסתיימת או שהסבב נגמר, הריצה הבאה תתחדש מהמקום בו היא נעצרה - שום דבר לא הולך לאיבוד.

### 🛡 Human-in-the-Loop

`human_ask` מאפשר ל-LLM להשהות ולבקש את אישורך לפני ביצוע פעולות הרסניות (מחיקת קבצים, פקודות חלוף). אתה נשאר בשליטה.

### 🛑 פסיק (מקש c / לחצן עצירה)

עצור LLM יצירת תגובה בכל עת והזריק פקודת עצור בחזרה ל-LLM.

| ממשק | איך להפריע |
|---|---|
| **CLI** | הקש על מקש `c` במהלך הזרמת LLM - התגובה הנוכחית נעצרת, ו`"עצור"` נשלחת כהודעת משתמש כך שה-LLM מגיב בהתאם |
| **ממשק WEB** | לחץ על הלחצן האדום **■ עצור** (מופיע אוטומטית במהלך עיבוד LLM) |
| **מחשב שולחני GUI** | לחץ על הלחצן האדום **■** (מופיע אוטומטית במהלך עיבוד LLM) |

ההפרעה פועלת כ"הזרקה מיידית": במקום פשוט לבטל, היא מחזירה את `"עצור"` אל LLM כהודעת משתמש, ומאפשרת לו לסיים בחן או לאשר את ההפרעה האוטומטית של `
xit כדי לראות את ההפרעה האוטומטית (
xit). [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ אוטומציה של דפדפן ו-Web Inspector

שניים משלימים Playwright⎎ דפדפן מבוססי דפדפן כלים אמיתיים:-** ** כלים למשחק אמיתי של דפדפן:⏏ לנווט, ללחוץ, למלא טפסים, לחלץ נתונים, לטפל בזרימות מרובות עמודים. עובד ללא ראש או עם ראש.
- **מחזאי_מפקח**: הקלט מעברי דפדפן, צלם תמונות DOM וצילומי מסך בכל שלב. שימושי לאיתור באגים באינטראקציות באינטרנט או לביקורת שינויים בעמודים לאורך זמן.

### 🔄 טעינת כלים דינמיים

`כלים_קטלוג` ו-`כלים_טעינה` מאפשרים לך לגלות ולהפעיל כלים בזמן ריצה.
אין צורך לטעון הכל בעת האתחול - הפעל רק את מה שאתה צריך, כאשר אתה צריך את זה.## Rustative כלים

`uuid_gen` ו-`slugify` מיושמים ב-Rust (באמצעות PyO3) לביצועים.
הם נטענים ישירות מ-`.pyd` בנוי מראש - **אין צורך בהתקנת pip**.

מפתחים חיצוניים יכולים גם לשלוח כלים מבוססי-Rust: הצב `.pyd`, שימוש `._`py` ליד ה-`._`pyd`. מ-`uagent.tools.rust_helper`, ו
משתמשים מקבלים את הכלי ללא תלות נוספת. ראה
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本丞 / אנגלית / 简一繁體中文 / 한국어 / Español / Français / Русский / ועוד.
הגדר את 'UAGENT_LANG' כדי לעבור. ראה [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) כדי להוסיף מקום חדש.

תרגומים של README זה זמינים ב- [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 משתני סביבה מוצפנים

אחסן API מפתחות וסודות בקובץ ``.env.` `uag_envsec`.

## תצורה ופרטים

- **משתני סביבה**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **אשף ההתקנה**: `python -m __cli**'encrypted_PH_2. `uag_envsec` — הצפין `.env` בתור `.env.sec`
- **תגובות API**: הגדר `UAGENT_RESPONSES=1` למצב תגובות API (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibabana/LM Studio/). מופעל אוטומטית עבור Sakana AI (Fugu).
- **מסמכי מפתח**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **זרימת כלים**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) - כיצד כלים נשלחים ל-LLMs (מסיכת ז'אנר, קטלוג_כלים, GPT-5.4+ כלי_חיפוש מקורי)
- **טיפים קטנים**:__PH [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## פילוסופיית הפרויקט

uag שואפת להיות **בינה מלאכותית שלך, במחשב שלך, בתנאים שלך.**

- אין תלות ב-SaaS — פועל מקומית
- אין נעילה של ספק — החלף בכל עת
- אין נעילת ממשק משתמש — CLI / Web / A2A כלים - ללא נעילה - כלים - A2A ומיומנויות

חוויית סוכן בינה מלאכותית חינמית, ללא נעילת ספקים.

### ✨ צור כלים משלך

כתיבת כלי חדש עבור uag היא פשוטה - צור קובץ `.py` יחיד עם 
`TOOL_SPEC` ו-`run_tool()_ENT_TEXTER()_T, הכנס אותו ב ו
זה זמין באופן מיידי. למפתחי Rust, שלח '.pyd' בנוי מראש עם
אפס תלות נוספת למשתמשים.

ראה [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
למדריך שלב אחר שלב
.## תרומה

תרומות יתקבלו בברכה! דוחות באגים, הצעות לתכונה, שיפורים בתיעוד, תרגומים ובקשות משיכה - הכל מוערך.

- **בעיות**: פתח בעיה של GitHub עבור באגים או בקשות תכונות.
- **משוך בקשות**: עזוב את ה-repo, בצע את השינויים שלך ושלח יחסי ציבור. ראה [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) להגדרת פיתוח והנחיות.
- **תרגומים**: README תרגומים ותוספות מקומיות יתקבלו בברכה. ראה [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **כלים ומיומנויות**: ניתן לתרום תוספי כלים חדשים ומיומנויות סוכן דרך השוק. תלות תחילה. הם נשמרים מחוץ לרשימת התלות בזמן ריצה:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
````

הרץ את אותן בדיקות שבהן השתמשו GitHub פעולות לפני דחיפה:
\`bash
s tests
python -m black --check src tests
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .

```

עבור איטרציה מקומית מהירה יותר, הפעל רק את הבדיקות המושפעות:
`
`` tests/<affected_area>
```

בדיקות נוספות כשרלוונטי:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

.potehon. סקריפטים/compile_locales.py` ו-`python scripts/po_qc_summary.py\`.

Runtime מדיניות (פרטים ב-[DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.): `mds/DEVELOP.`it helpers in plaas של `md. the tool host turns tool `SystemExit`/`Exception\` into error strings so a single tool cannot kill the process. Startup fail-fast exits remain intentional.

## ארכיטקטורה ושינויים תפעוליים

עיין ב-[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) עבור חוזים עמידים המכסים מחזור חיים של A2A, הקשרי I18N, התקנת תלות אופציונלית, בטיחות כלי, יכולות ספק, גבולות אמון OAuth,⎏ וקבלה, אימות מובנה של OAuth.## מנוע מדיניות ארגוני

תמיכה במדיניות ברמת הארגון עבור כלים, ספקים, אישורים, שרתים MCP, רשתות, מיומנויות ותוספים. הגדר את 'UAGENT_POLICY_FILE' לקובץ מדיניות JSON/YAML; ראה [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) לדוגמאות תצורה, תפקידים, אישורים ורשימות היתרים.

### Runtime שחזור ותזמור

ראה [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md) לשחזור עמיד, ביצוע מודע לתלות, תזמור מרובה סוכנים ושימוש מרחוק ב-A2A.

ראה [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md) לתיאום חכירה מוביל בזמן ריצה משותפת.
