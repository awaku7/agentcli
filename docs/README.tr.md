<p align = "center">
 <img src = "https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt = "uag logo" width = "720">
</p>

<h1 align = "center">uag — Evrensel AI Ağ Geçidi</h1>

<p align="center">
 <b>Evrensel <b>A</b>I <b>G</b>yolu — Ortamınız, özgürlüğünüz.
</p>

<p align="center">
 Dosya işlemleri / Web araması / Görüntü oluşturma ve analiz / PDF ve Excel çıkarma / Nesnelerin İnterneti kontrolü / MCP entegrasyonu<br>
 24 sağlayıcı / 3 kullanıcı arayüzü / Paralel araç yürütme / Temsilci Beceri pazarı
</p>

<p align="center">
 <a href="https://github.com/awaku7/agentcli">GitHub</a>
 ·
 <a href="https://pypi.org/project/uag/">PyPI</a>
 ·
 <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Bunu kendi dilinizde okuyun</a>
</p>

______________________________________________________________________

## Neden uag?

**Satıcıya bağlı kalmaktan kurtulun.** Çoğu AI asistanı sizi belirli bir sağlayıcıya veya bulut hizmetine bağlar. uag farklıdır.

- Makinenizde **yerel olarak çalışır**. Verileriniz yanınızda kalır (yaptığınız API çağrı hariç).
- **Sağlayıcı özgürlüğü**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, Novita, HuggingFace... 24 sağlayıcı, hepsine tek bir arayüzden erişilebilir. Ortam değişkenlerini yeniden yapılandırarak bunlar arasında geçiş yapın — yeniden yükleme yok, geçiş yok.
- **222 araç**: Dosya G/Ç, web araması, görüntü oluşturma, Gmail, BLE cihaz taraması, MCP sunucu entegrasyonu — **130 tanesi statik olarak paralel güvenli olarak işaretlenmiştir** (en fazla 8 tanesi iş parçacığı havuzu aracılığıyla eşzamanlı olarak yürütülür, "UAGENT_PARALLEL_WORKERS" aracılığıyla yapılandırılabilir). LLM aynı anda birden fazla araç çağrısı başlattığında, uag bunları otomatik olarak paralelleştirir.
- **3 kullanıcı arayüzü + A2A**: CLI, GUI, Web ve Aracıdan Aracıya protokolü. Aynı motor, tüm arayüzler.
- **IoT'ye hazır**: SwitchBot, ECHONET Lite, Matter, UPnP — ev cihazlarınızı yapay zeka aracılığıyla kontrol edin.
- **Ajan Becerileri**: Piyasadan topluluk tarafından oluşturulan becerileri yükleyin. uag'yi sonsuza kadar genişletin.

uag, **kendi koşullarınıza göre yapay zeka yardımcınızdır**. Bir sağlayıcıya bağlı değil, bir arayüze bağlı değil, bir platforma bağlı değil.

## Hızlı Başlangıç

```bash
pip kurulumu uag
uag
```

İlk başlatmada, kurulum sihirbazı sağlayıcı yapılandırmasında size yol gösterir.
Tüm ortamlar için [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) adresine bakın değişkenler.

## Bilgisayar Kullanımı

Bilgisayar Kullanımı isteğe bağlıdır ve hem görünür bir Playwright tarayıcı çalışma zamanını
hem de bir masaüstü çalışma zamanını destekler. Etkinleştirildiğinde, her iki çalışma zamanı da oluşturulur ve kaydedilir;
seçilen çalışma zamanı `UAGENT_COMPUTER_ENVIRONMENT` tarafından kontrol edilir:

```bat
set UAGENT_COMPUTER_USE=1
set UAGENT_COMPUTER_ENVIRONMENT=tarayıcı
```

Bunun yerine işletim sistemi masaüstü çalışma zamanını seçmek için `masaüstü'nü kullanın. Çalışma zamanı kaynakları normal çıkışta, "Ctrl-C"de ve işlem kapatıldığında birlikte kapatılır. Tarayıcı tabanlı CI veya duman testleri için `UAGENT_COMPUTER_HEADLESS=1\` ayarlayın.
Entegrasyon ve güvenlik ayrıntıları için [docs/COMPUTER_USE_IMPLEMENTATION.md](docs/COMPUTER_USE_IMPLEMENTATION.md)
adresine bakın.

## Gerçek Zamanlı Ses ve AEC3

Gerçek zamanlı ses modu, OpenAI Gerçek Zamanlı, Azure OpenAI GPT Gerçek Zamanlı, xAI Grok Ses API, Google Gemini Multimodal Live API ve tam çift yönlü mikrofon ve hoparlör G/Ç'li Amazon Bedrock Nova Sonic'i destekler. Gerekli `pywebrtc-audio` AEC3 arka ucu otomatik olarak yüklenir ve Bedrock'un isteğe bağlı çift yönlü akış SDK'sı yalnızca Bedrock sağlayıcısı seçildiğinde otomatik olarak yüklenir:

```bash
python scheck.py gerçek zamanlı
```

AEC3 boru hattı gerçek mikrofon sinyalini (`yakın`) alır ve hoparlöre iletilen sesi (`uzak`) böylece asistanın konuşurken dinle. Tanılamayı yalnızca ses sorunlarını araştırırken etkinleştirin:

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Gerçek Zamanlı İşlev Çağrısı

OpenAI Gerçek zamanlı, güvenliği sınırlı bir İşlev Çağrısı entegrasyonunu destekler. Geçerli gerçek zamanlı bağdaştırıcı salt okunur 'get_current_time'ı otomatik olarak kullanıma sunar. Yıkıcı araçlar ve cihaz kontrolleri, açık bir izin verilenler listesi ve onay akışı olmadan açığa çıkmaz. Grok gerçek zamanlı, ayrı bir bağdaştırıcı kullanır ve OpenAI'e özgü bu işlev çağrısı yolunu kullanmaz.

## Özellikler

### 🧠 Çoklu Sağlayıcı Mimarisi

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / llama.cpp / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot) AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway
Tüm sağlayıcılar aynı araç setini ve arayüzü paylaşır. `UAGENT_PROVIDER` ayarını yaparak geçiş yapın — kod değişikliği yok, ayrı kurulum yok.

#### Ollama ve llama.cpp

Ollama ve llama.cpp ayrı sağlayıcılardır. Ollama kendi hizmet ve model yönetimini kullanırken `llama.cpp`, OpenAI uyumlu bir lama sunucusuna bağlanır:

```bash
# Ollama
UAGENT_PROVIDER=ollama
UAGENT_OLLAMA_BASE_URL=http://localhost:11434/v1
UAGENT_OLLAMA_DEPNAME=llama3.1
# llama.cpp / llama-server
UAGENT_PROVIDER=llama_cpp
UAGENT_LLAMA_CPP_BASE_URL=http://localhost:8080/v1
UAGENT_LLAMA_CPP_DEPNAME=local-model
UAGENT_LLAMA_CPP_API_KEY=dummy
```

Llama.cpp sağlayıcısı Sohbet Tamamlamaları uyumlu yol. Uyumlu bir proxy yapılandırılmadığı sürece `UAGENT_RESPONSES=0` değerini koruyun.

### ⚡ Paralel Araç Yürütme

LLM aynı anda birden fazla araç talep ettiğinde, uag bunları **otomatik olarak paralelleştirir**.
130 araç statik olarak `x_parallel_safe` olarak işaretlenir ve bir `ThreadPoolExecutor` (varsayılan olarak 8 iş parçacığı; set) aracılığıyla eşzamanlı olarak yürütülür `UAGENT_PARALLEL_WORKERS` değişecek).
**Örnek**: "İskandinav başkentlerinde hava durumunu kontrol et" seçeneğini sorun → LLM, `search_web'i tetikledi × 5 ülke → 5 aramanın tümü paralel olarak yürütülüyor → sonuçlar tek bir grupta toplanıyor. Mevcut sayım, bir 'TOOL_SPEC' tanımlayan araç modüllerine dayanmaktadır (şu anda 222, 2 Rust destekli araç dahil) `src/uagent/tools_rust/`). `http_request`yönteme duyarlı güvenlik kullanır:`GET`/`HEAD`/`OPTIONS\` çağrıları paralel olarak çalışabilir, ancak yazma yöntemleri seri kalır.
Salt okunur araçlar (dosya arama, karma hesaplama, dizin listeleme, çeviri, veritabanı sorguları vb.) agresif bir şekilde paralelleştirilmiştir.

### 🧩 Eklenti Sistemi (Claude Kod Uyumlu)

uagent, **Claude Kod uyumlu bir eklenti sistemi** uygular. Eklentiler, becerileri, aracıları, MCP sunucularını, kancaları ve daha fazlasını bir ".claude-plugin/plugin.json" bildirimiyle bağımsız dizinlerde bir araya getirir.
**Desteklenen bileşenler**: Beceriler, Alt aracılar, MCP sunucuları, Kancalar (12 yaşam döngüsü olayı), Eğik çizgi komutları, Çıkış stilleri, userConfig, Bağımlılıklar, Kanallar, Pazaryerleri
**CLI komutlar**:

```
:eklenti listesi # Yüklü eklentileri listele
:eklenti yükleme <kaynak> [--kapsam] # Yükle (dir/zip/git/http)
:eklenti yükleme <ad>@<marketplace> # Pazar yerinden yükle
:eklenti kaldır <ad> # Kaldır
:eklenti etkinleştirme/devre dışı bırakma <ad> # Toggle
:eklenti pazaryeri ekle/kaldır/liste # Yönet pazar yerleri
:plugin init <name> # Scaffold yeni eklentisi
```

Tüm belgeler için [DEVELOP_PLUGIN.md](src/uagent/docs/DEVELOP_PLUGIN.md) adresine bakın.

### 🔄 Oturum Devamlılığı

- \*\*`UAGENT_PROVIDER` ile oturum ortasında sağlayıcıları değiştirin — konuşma geçmişi korunur.
- **Geçmiş oturumları `:load <index>` ile yeniden yükleyin** — kaldığınız yerden devam edin.
- **Araç sonucunu önbelleğe alma**, aynı araç çağrısı tekrarlandığında gereksiz yeniden çalıştırmayı önler.

### 🛠 229 Araçlar

| Kategori | Araçlar |
|---|---|
| **Dosya İşlemleri** | okuma/yazma/oluşturma/silme/arama/grep/hash/zip, dosya_türü, ayrıştırma_eml (.eml dosyaları), `yol_takma adı' | | **Web** | fetch_url, search_web, ekran görüntüsü, tarayıcı_playwright, `url_alias`, `public_transit_route`([guide](docs/PUBLIC_TRANSIT_ROUTE.md)) | | **Medya** | created_image, analyze_image, img2img, audio_speech, audio_transcribe | | **Belgeler** | PDF/PPTX/DOCX/RTF/ODT çıkarma, Excel yapılandırılmış çıkarma | | **Tahmin** | 9 modelle zaman serisi tahmini (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM, vb.), otomatik model seçimi, grafik oluşturma, i18n | | **İletişim** | gmail_send, gmail_read, bluesky, discord_channel, takımlar_webhook, **pybitchat** (BLE Mesh) — bkz. [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) ve [BITCHAT.md](https://github.com/awaku7/agentcli/blob/main/docs/BITCHAT.md) | | **IoT** | SwitchBot (Bulut + BLE), ECHONET Lite, Matter, UPnP, ters_geocode | | **Bulut API'leri** |`aws_api`, `gcp_api`, `azure_api\` — genel AWS, Google Bulut ve Azure API işlemleri; yazma işlemleri açık onay gerektirir |
| **Geliştirme Araçları** | çalışma alanı_durumu, git_ops, git_review, güvenlik_scan, kapsama_raporu, python_compile, lint_format, run_tests, db_query, **29 kaynak kodu gezgini (idx ailesi)** |
| **MCP** | Harici MCP sunucularına bağlanın, araçları listeleyin, çalıştırın — [OAuth / Proxy kılavuzu](docs/MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Aracıdan aracıya iletişim (diğer uag örnekleri veya A2A uyumlu sunucularla) |
| **Sistem** | env değişkenleri, sistem özellikleri, saat, tarih hesaplaması, [miktarlar](docs/QUANTITIES.md), [geodesic_distance](docs/GEODESIC_DISTANCE.md), uuid_gen, slugify |
| **Kaynak Gezintisi** | \*\*Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile için **29 idx aracı** — tüm dosyayı okumadan bir işlev/sınıf dizini veya belirli bir tanım elde edin |

#### Depo incelemesi ve kapsamı

- `workspace_status`: etkin çalışma alanının Git şubesini, değişikliklerini, yukarı akış senkronizasyon durumunu, Python çalışma zamanını ve ortak durumunu rapor edin dosyaları değiştirmeden proje işaretçileri.
- `git_review`: Gizli değerleri açığa çıkarmadan Git değişikliklerini, riskli dosyaları, test adaylarını ve gizli bulguları özetleyin.
- `security_scan`: olası sırlar ve riskli yapılandırma dosyaları için depo dosyalarını tarayın.
- `coverage_report`: Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET, C/C++, Ruby için kapsamı çalıştırın ve normalleştirin PHP, Swift ve Dart/Flutter.
- Eksik kapsam bağımlılıkları, yürütme istendiğinde otomatik olarak kurulabilir; \`dry_run' hiçbir zaman paketleri yüklemez.
  Parametreler, çıktı ve güvenlik ayrıntıları için [Depo Analiz Araçları](docs/REPOSITORY_TOOLS.md) adresine bakın.
  Araç bağımsız değişkenlerinde tekrarlanan dosya yollarını ve URL'leri kısaltmak için [Yol ve URL takma adlarına](docs/PATH_URL_ALIASES.md) bakın.

### 🖥 4 Arayüzler + VS Kod Uzantısı

| Modu | Komut | Amaç |
|---|---|---|
| **CLI** | `uag` | Hızlı terminal tabanlı operasyon |
| **GUI** | 'uagg' | Tkinter aracılığıyla Masaüstü Kullanıcı Arayüzü |
| **Web** | 'uagw' | Tarayıcı tabanlı erişim |
| **A2A Sunucu** | 'uaga' | Çoklu aracı iletişimi için Agent2Agent protokolü |
| **VS Kodu** | — | [Uzantı](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) Sohbet Paneli, Açıklama, Yeniden Düzenleme, Hatayı Düzeltme ve Araç Ağacı Görünümü ile |
VS Code uzantısı — kurulum, ayrıntılar için [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) adresine bakın. komutlar, tuş atamaları ve konfigürasyon.

### 🏠 IoT Cihaz Kontrolü

- **BACnet**: BACnet/IP cihazlarını (HVAC, aydınlatma, güç sayaçları) okuma/yazma. Anında bildirimler için COV aboneliği
- **Modbus TCP**: Tutma/giriş kayıtlarını ve bobinlerini okuma/yazma. Yoklama tabanlı değişiklik izleme
- **OPC UA**: Adres alanına göz atın, değişkenleri okuyun/yazın, veri değişikliklerine abone olun
- **SwitchBot**: Bulut toplu kontrolü ve BLE tarama/kontrol. Anket tabanlı abonelik
- **ECHONET Lite**: Ev aletlerinden (AC, ışıklar, su ısıtıcıları vb.) gelen INF bildirimlerini keşfedin, kontrol edin ve abone olun
- **Madde**: Durum değişikliği izleme için okuma/yazma kontrolü + nitelik aboneliği
- **UPnP**: Cihaz keşfi ve IGD bağlantı noktası yönlendirme
  Bkz. [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md)

### 🎯 Agent Skills Marketplace

`:topluluk için [SkillsMP](https://skillsmp.com) ve [ClawHub](https://clawhub.ai)'a göz atmak için skills mp_search` beceriler.
uag'nin yeteneklerini anında kurun ve genişletin.

### 🤖 Otomatik Pilot (`:auto`)

uag **birden fazla LLM turda bağımsız olarak bir hedefi takip edebilir**. Yinelemeli iyileştirme gerektiren karmaşık, çok adımlı görevler için mükemmeldir.

- **Nasıl çalışır**: Her turda bir ana sorgu (A Adımı) ve ardından "TAMAM mı yoksa DEVAM ET" kararı veren bir gözden geçiren kararı (Adım B) bulunur
- **Aynı sağlayıcı, aynı API**: Gözden geçirenin kararı, Yanıtlar API desteği de dahil olmak üzere ana sorguyla aynı kod yolunu kullanır.
- **Ayrı jüri LLM** (isteğe bağlı): Kullanmak için `UAGENT_AP_PROVIDER`ı ayarlayın inceleyen için farklı bir sağlayıcı/model (ör. değerlendirme için daha ucuz bir model kullanın).
- **İstediğiniz zaman çıkın**: Yanıtın ortasında bile hemen durmak için 'x' tuşuna basın. Veya hedefe ne zaman ulaşılacağına incelemecinin karar vermesine izin verin.
- **Yapılandırılabilir**: bütçeyi kontrol etmek için `--max-rounds N`.
  Tüm belgeler için [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) adresine bakın.

### 🧩 Toplu Durum Yöneticisi

uag uzun süredir devam eden çok dosyalı görevlerdeki ilerlemeyi izleyebilir. LLM düzinelerce dosyayı işlediğinde, "batch_state" bekleyen, tamamlanan ve başarısız olan dosyaların listesini diskte saklar. Oturum sona ererse veya bir tur zaman aşımına uğrarsa, bir sonraki çalıştırma kaldığı yerden devam eder; hiçbir şey kaybolmaz.

### 🛡 Döngüdeki İnsan

`human_ask`, LLM'ün yıkıcı işlemler (dosya silme, üzerine yazma, kabuk komutları) gerçekleştirmeden önce duraklatılmasına ve onayınızı istemesine olanak tanır. Kontrol sizde kalır.

### 🛑 Kesinti (c tuşu / Durdurma düğmesi)

İstediğiniz zaman LLM yanıt oluşturmayı durdurun ve LLM'e geri bir durdurma komutu enjekte edin.
| Arayüz | |
|---|---|
| **CLI** | LLM akışı sırasında `c` tuşuna basın — mevcut yanıt durur ve LLM'ün buna göre yanıt vermesi için `"Durdur"` bir kullanıcı mesajı olarak gönderilir |
| **WEB kullanıcı arayüzü** | Kırmızı **■ Durdur** düğmesine tıklayın (LLM işlemi sırasında otomatik olarak görünür) |
| **Masaüstü GUI** | Kırmızı **■** düğmesine tıklayın (LLM işlemi sırasında otomatik olarak görünür) |
Kesinti, "bilgi istemi enjeksiyonu" olarak çalışır: yalnızca iptal etmek yerine, LLM'e bir kullanıcı mesajı olarak ""Durdur""u geri gönderir ve kesintiyi zarif bir şekilde sonlandırmasına veya kesintiyi kabul etmesine olanak tanır.
Otomatik pilot modundan çıkmak için "x" tuşuna basın (bkz. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md)).

### 🕵️ Tarayıcı Otomasyonu ve Web Denetçisi

İki tamamlayıcı Playwright tabanlı araç:

- **browser_playwright**: Gerçek tarayıcı oturumlarını otomatikleştirin - gezinin, tıklayın, formları doldurun, verileri çıkarın, yönetin çok sayfalı akışlar. Başsız veya başlı çalışır.
- **playwright_inspector**: Her adımda tarayıcı geçişlerini kaydedin, DOM anlık görüntülerini ve ekran görüntülerini yakalayın. Web etkileşimlerinde hata ayıklamak veya zaman içinde sayfa değişikliklerini denetlemek için kullanışlıdır.

### 🔄 Dinamik Araç Yükleme

`tool_catalog` ve `tool_load`, araçları çalışma zamanında keşfetmenize ve etkinleştirmenize olanak tanır.
Başlangıçta her şeyi yüklemenize gerek yoktur; yalnızca ihtiyacınız olanı, ihtiyacınız olduğunda etkinleştirin.

### 🦀 Rust Yerel Araçlar

`uuid_gen` ve `slugify`, Performans için Rust (PyO3 aracılığıyla).
Doğrudan önceden oluşturulmuş bir `.pyd'den yüklenirler — **`pip kurulumuna' gerek yoktur\*\*.
Harici geliştiriciler ayrıca Rust tabanlı araçlar da gönderebilir:
wrapper `.py`nin yanına bir `.pyd` yerleştirin, `uagent.tools.rust_helper`dan `load_rust_pyd()` kullanın ve
kullanıcılar araca sahip olsun herhangi bir ekstra bağımlılık olmadan. Bakınız
[TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md).

### 🌐 i18n / L10n

日本語 / Türkçe / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / ve daha fazlası.
Geçiş yapmak için `UAGENT_LANG` ayarını yapın. Yeni bir yerel ayar eklemek için [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) adresine bakın.
Bu README'nin çevirileri şu adreste mevcuttur: [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md).

### 🔒 Şifrelenmiş Ortam Değişkenleri

API anahtarlarını ve gizli dizilerini şifrelenmiş bir ".env" dosyası olan ".env.sec" içinde depolayın.
Şunlarla yönetin: `uag_envsec`.

## Yapılandırma ve Ayrıntılar

- **Ortam değişkenleri**: [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md)
- **Kurulum sihirbazı**: `python -m uagent.setup_cli`
- **Şifrelenmiş env**: `uag_envsec` — `.env'yi `.env.sec\` olarak şifreleyin
- **Yanıtlar API**: Yanıtlar API modu için \`UAGENT_RESPONSES=1'i ayarlayın (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Sakana AI (Fugu) için otomatik olarak etkinleştirildi.
- **Geliştirici belgeleri**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Araç akışı**: [TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) — araçların LLM'lere nasıl gönderildiği (tür maskesi, tool_catalog, GPT-5.4+ yerel tool_search)
- **Küçük LLM ipuçları**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/docs/SLM_TIPS.md)

## Proje Felsefesi

uag, **sizin koşullarınıza göre, makinenizde yapay zekanız olmayı hedefliyor.**

- SaaS bağımlılığı yok — yerel olarak çalışıyor
- Sağlayıcıya kilitleme yok — istediğiniz zaman geçiş yapın
- Kullanıcı arayüzüne kilitlenme yok — CLI / GUI / Web / A2A
- Özellik kilitleme yok — araçlar ve becerilerle genişletin

Satıcıdan bağımsız, ücretsiz bir AI aracısı deneyimi kilitleyin.

### ✨ Kendi Araçlarınızı Yaratın

uag için yeni bir araç yazmak çok basittir —
`TOOL_SPEC` ve `run_tool()` ile tek bir `.py` dosyası oluşturun, onu `UAGENT_EXTERNAL_TOOLS_DIR` içine yerleştirin ve
hemen kullanıma hazır olsun. Rust geliştiricileri, kullanıcılar için
sıfır ekstra bağımlılık içeren önceden oluşturulmuş bir \`.pyd' gönderin.

Adım adım kılavuz için [TOOL_CREATOR_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/TOOL_CREATOR_GUIDE.md)
adresine bakın.

## Katkıda Bulunma

Katkılarınızı bekliyoruz! Hata raporları, özellik önerileri, belge iyileştirmeleri, çeviriler ve çekme istekleri — hepsi takdire şayandır.

- **Sorunlar**: Hatalar veya özellik istekleri için bir GitHub sorunu açın.
- **Çekme istekleri**: Depoyu çatallayın, değişikliklerinizi yapın ve bir PR gönderin. Geliştirme kurulumu ve yönergeleri için [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) adresine bakın.
- **Çeviriler**: README çevirileri ve yerel ayar eklemeleri kabul edilir. Bkz. [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md).
- **Araçlar ve Beceriler**: Yeni araç eklentileri ve Aracı Becerileri, pazar aracılığıyla katkıda bulunabilir.

### Geliştirme kontrolleri (PR'den önce)

Yalnızca testi yükleyin öncelikle bağımlılıklar. Çalışma zamanı
bağımlılık listesinin dışında tutulurlar:

```bash
python -m pip install -e ".[test]"
python -m pip install black ruff
```

GitHub tarafından kullanılan kontrollerin aynısını çalıştırın Bastırmadan önceki eylemler:

```bash
python -m ruff check src testler
python -m black --src testlerini kontrol edin
python scripts/tool_json_i18n_batch.py status
python -m pytest -q .
```

Daha hızlı bir yerel yineleme için yalnızca etkilenen testleri çalıştırın:

```bash
pytest -q testler/<affected_area>
```

İlgili olduğunda ek kontroller:

```bash
python -m py_compile src/uagent/
mypy src/uagent
```

Yerel ayar (`.po`) düzenlemelerinden sonra: \`python scripts/compile_locales.py' ve 'python scripts/po_qc_summary.py'.

Çalışma zamanı politikası (ayrıntılar [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) §6.1'de): yardımcılar yerine yükseltir 'sys.exit'; araç ana bilgisayarı 'SystemExit'/'Exception' aracını hata dizelerine dönüştürür, böylece tek bir araç süreci sonlandıramaz. Başlangıçta başarısız hızlı çıkışlar kasıtlı olarak kalır.

## Mimari ve operasyonel değişmezler

A2A yaşam döngüsünü, I18N bağlamlarını, isteğe bağlı bağımlılık kurulumunu, araç güvenliğini, sağlayıcı yeteneklerini, OAuth güven sınırlarını, yapılandırılmış olayları ve kabul doğrulamayı kapsayan dayanıklı sözleşmeler için [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) adresine bakın.

## Kurumsal Politika Motoru

Araçlar, sağlayıcılar, kimlik bilgileri, MCP sunucuları, ağlar, beceriler ve eklentiler için kuruluş düzeyindeki politikalar desteklenir. `UAGENT_POLICY_FILE`ı bir JSON/YAML politika dosyasına ayarlayın; Yapılandırma örnekleri, roller, onay ve izin verilenler listeleri için [docs/ENTERPRISE_POLICY.md](docs/ENTERPRISE_POLICY.md) adresine bakın.

### Çalışma zamanı kurtarma ve orkestrasyon

Bkz. [RESTART_RECOVERY.md](docs/RESTART_RECOVERY.md) / Dayanıklı kurtarma, bağımlılığa duyarlı yürütme, çoklu aracı düzenleme ve uzaktan A2A kullanımı için [DAG_SCHEDULER.md](docs/DAG_SCHEDULER.md) / [MULTI_AGENT_RUNTIME.md](docs/MULTI_AGENT_RUNTIME.md).

Bkz. Paylaşılan çalışma zamanı lideri kiralama koordinasyonu için [DISTRIBUTED_COORDINATION.md](docs/DISTRIBUTED_COORDINATION.md).
