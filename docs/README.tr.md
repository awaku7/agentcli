<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Evrensel Yapay Zeka Ağ Geçidi</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Çevreniz, özgürlüğünüz.
</p>

<p align="center">
  Dosya işlemleri / Web araması / Görüntü oluşturma ve analiz / PDF ve Excel çıkarma / IoT kontrolü / MCP entegrasyonu<br>
  24 providers / 3 kullanıcı arayüzü / Paralel araç yürütme / Agent Skills pazar yeri
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="README.translations.md">Read this in your language</a>
</p>

______________________________________________________________________

## Neden uag?

**Satıcıya bağlı kalmaktan kurtulun.** Çoğu AI asistanı sizi belirli bir sağlayıcıya veya bulut hizmetine bağlar. uag farklıdır.

- **Makinenizde yerel olarak çalışır**. Verileriniz sizinle kalır (yaptığınız API çağrıları hariç).
- **Sağlayıcı özgürlüğü**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 21 sağlayıcı, hepsine tek bir arayüzden erişilebilir. Ortam değişkenlerini yeniden yapılandırarak bunlar arasında geçiş yapın; yeniden yükleme yok, geçiş yok.
- **229 araç**: Dosya G/Ç, web araması, görüntü oluşturma, Gmail, BLE cihaz tarama, MCP sunucu entegrasyonu — **130 araç paralel güvenlidir** (iş parçacığı havuzu aracılığıyla en fazla 8 eşzamanlı yürütme, "UAGENT_PARALLEL_WORKERS" aracılığıyla yapılandırılabilir). LLM aynı anda birden fazla araç çağrısı başlattığında, uag bunları otomatik olarak paralelleştirir.
- **3 kullanıcı arayüzü + A2A**: CLI, GUI, Web ve Aracıdan Aracıya protokolü. Aynı motor, herhangi bir arayüz.
- **Ajan Becerileri**: Piyasadan topluluk tarafından oluşturulan becerileri yükleyin. Uag'ı sonsuza kadar uzatın.

uag **kendi şartlarınıza göre yapay zeka asistanınızdır**. Bir sağlayıcıya bağlı değil, bir arayüze bağlı değil, bir platforma bağlı değil.

## Hızlı Başlangıç

```bash
pip install uag
uag
```

İlk başlatmada kurulum sihirbazı, sağlayıcı yapılandırmasında size yol gösterir.
Tüm ortam değişkenleri için [docs/ENVIRONMENT.md](ENVIRONMENT.md) adresine bakın.

## Özellikler

### 🧠 Çoklu Sağlayıcı Mimarisi

OpenAI / PFN (PLaMo) / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / Novita / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / Sakana AI (Fugu) / SAKURA AI Engine / Together AI / Vercel AI Gateway

Tüm sağlayıcılar aynı araç setini ve arayüzü paylaşır. 'UAGENT_PROVIDER' ayarını yaparak geçiş yapın; kod değişikliği yok, ayrı kurulum yok.

### ⚡ Paralel Takım Yürütme

LLM aynı anda birden fazla araç talep ettiğinde bunları **otomatik olarak paralelleştirir**.
130 araç 'x_parallel_safe' olarak işaretlenmiştir ve bir 'ThreadPoolExecutor' aracılığıyla eşzamanlı olarak çalıştırılır (varsayılan olarak 8 iş parçacığı; değiştirmek için 'UAGENT_PARALLEL_WORKERS' ayarlayın).

**Örnek**: "İskandinav başkentlerindeki hava durumunu kontrol edin" sorusunu sorun → Yüksek Lisans \`search_web'i çalıştırıyor × 5 ülke → 5 aramanın tümü paralel olarak yürütülüyor → sonuçlar tek bir grupta toplanıyor.

Salt okunur araçlar (dosya arama, karma hesaplama, dizin listeleme, çeviri, veritabanı sorguları vb.) agresif bir şekilde paralelleştirilmiştir.

### 🧩 Eklenti Sistemi (Claude Code uyumlu)

uagent, Claude Code uyumlu bir eklenti sistemi uygular. Eklentiler; becerileri, aracıları, MCP sunucularını, kancaları ve daha fazlasını `.claude-plugin/plugin.json` bildirimiyle bağımsız dizinlerde bir araya getirir.

**Desteklenen bileşenler: beceriler, alt aracılar, MCP sunucuları, kancalar (12 yaşam döngüsü olayı), eğik çizgi komutları, çıktı stilleri, userConfig, bağımlılıklar, kanallar, marketler**

**CLI commands**:

```
:plugin list                         # Yüklü eklentileri listele
:plugin install <source> [--scope]
:plugin install <name>@<marketplace>  # Market üzerinden yükle
:plugin remove <name>                # Kaldır
:plugin enable/disable <name>        # Aç veya kapat
:plugin marketplace add/remove/list  # Marketleri yönet
:plugin init <name>                  # Yeni eklenti iskeleti oluştur
```

Ayrıntılar için tam belgelere bakın. [DEVELOP_PLUGIN.md](../src/uagent/docs/DEVELOP_PLUGIN.md)

### 🔄 Oturum Sürekliliği

- **Oturum sırasında sağlayıcı değiştir** `UAGENT_PROVIDER` ile — konuşma geçmişi korunur.
- **Önceki oturumları yeniden yükle** `:load <index>` ile — kaldığınız yerden devam edin.

### 🛠 229 Araç

| Kategori | Araçlar |
|---|---|
| **Dosya İşlemleri** | okuma/yazma/oluşturma/silme/arama/grep/hash/zip, ayrıştırma_eml (.eml dosyaları) |
| **Web** | fetch_url, search_web, ekran görüntüsü, tarayıcı_oynatma yazarı |
| **Medya** | created_image, analyze_image, img2img, audio_speech, audio_transcribe |
| **Belgeler** | PDF/PPTX/DOCX/RTF/ODT çıkarma, Excel yapılandırılmış çıkarma |
| **Tahmin** | 9 model ile zaman serisi tahmini (AutoARIMA, Prophet, LightGBM, CatBoost, TimesFM vb.), otomatik model seçimi, grafik oluşturma, i18n |
| **İletişim** | gmail_send, gmail_read, bluesky, discord_channel, takımlar_webhook, **pybitchat** (BLE Mesh) — bkz. [COMMUNICATION.md](COMMUNICATION.md) ve [BITCHAT.md](BITCHAT.md) |
| **IoT** | BACnet、Modbus TCP、OPC UA、SwitchBot（Cloud + BLE）、ECHONET Lite、Matter、UPnP、reverse_geocode |
| **Bulut API’leri** | `aws_api`, `gcp_api`, `azure_api` — AWS, Google Cloud, and Azure API operations; write operations require explicit confirmation |
| **Geliştirme Araçları** | workspace_status, git_ops, python_compile, lint_format, run_tests, db_query, **29 kaynak kodu gezgini (idx ailesi)** |
| **MCP** | Harici MCP sunucularına bağlanın, araçları listeleyin, çalıştırın — [OAuth / Proxy guide](MCP_OAUTH_PROXY_GUIDE.md) |
| **A2A** | Aracıdan aracıya iletişim (diğer uag örnekleri veya A2A uyumlu sunucularla) |
| **Sistem** | env değişkenleri, sistem özellikleri, saat, tarih hesaplaması, uuid_gen, slugify, quantities ||
| **Kaynak Gezintisi** | Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL, VBA, LotusScript, Makefile için **29 idx aracı** — tüm dosyayı okumadan bir işlev/sınıf dizini veya belirli bir tanım edinin |

#### Depo incelemesi ve kapsamı

- `workspace_status`: Etkin çalışma alanı Git dalını, değişiklikleri, yukarı akış senkronizasyon durumunu, Python çalışma zamanını ve ortak proje işaretleyicilerini, dosyaları değiştirmeden raporlayın.
- `git_review`: Git değişikliklerini, riskli dosyaları, test adaylarını ve gizli bulguları gizli değerleri açığa çıkarmadan özetleyin.
- `security_scan`: depo dosyalarını olası sırlar ve riskli yapılandırma dosyaları için tarayın.
- `coverage_report`: Python, TypeScript/JavaScript, Rust, Go, Java/Kotlin, .NET için kapsamı çalıştırın ve normalleştirin, C/C++, Ruby, PHP, Swift ve Dart/Flutter.
- Eksik kapsam bağımlılıkları, yürütme istendiğinde otomatik olarak kurulabilir; \`dry_run' hiçbir zaman paketleri yüklemez.

Parametreler, çıktı ve güvenlik ayrıntıları için [Depo Analiz Araçları](REPOSITORY_TOOLS.md) konusuna bakın.

### 🖥 4 Arayüz + VS Kod Uzantısı

| Modu | Komut | Amaç |
|---|---|---|
| **CLI** | 'uag' | Hızlı terminal tabanlı operasyon |
| **GUI** | 'uagg' | tkinter aracılığıyla Masaüstü Kullanıcı Arayüzü |
| **Web** | 'uagw' | Tarayıcı tabanlı erişim |
| **A2A Sunucusu** | 'uaga' | Çoklu aracı iletişimi için Agent2Agent protokolü |
| **VS Kodu** | — | [Uzantı](VSCODE.md) Sohbet Paneli, Açıklama, Yeniden Düzenleme, Hata Düzeltme ve Araç Ağacı Görünümü ile |

Kurulum, komutlar, tuş atamaları ve yapılandırma gibi VS Code uzantısıyla ilgili ayrıntılar için [VSCODE.md](VSCODE.md) adresine bakın.

### 🏠 IoT Cihaz Kontrolü

- **Madde**: Denetleyici/köprü/cihaz topolojisinin salt okunur denetimi

Bkz. [IOT_USECASE.md](IOT_USECASE.md)

### 🎯 Temsilci Becerileri Pazarı

Topluluk becerileri için [SkillsMP](https://skillsmp.com) ve [ClawHub](https://clawhub.ai)'a göz atmak için `:skills mp_search`.
Uag'ın yeteneklerini anında kurun ve genişletin.

### 🤖 Otomatik Pilot (`:otomatik`)

uag **birden fazla LLM turunda bağımsız olarak bir hedefi takip edebilir**. Yinelemeli iyileştirme gerektiren karmaşık, çok adımlı görevler için mükemmeldir.

- **Nasıl çalışır**: Her turda bir ana sorgu (A Adımı) ve ardından "TAMAM MI, DEVAM ET" kararını veren bir gözden geçiren değerlendirmesi (Adım B) bulunur.
- **Aynı sağlayıcı, aynı API**: İncelemeyi yapan kişinin kararı, Responses API desteği de dahil olmak üzere ana sorguyla aynı kod yolunu kullanır.
- **Ayrı jüri üyesi LLM** (isteğe bağlı): İnceleyen için farklı bir sağlayıcı/model kullanmak üzere `UAGENT_AP_PROVIDER`ı ayarlayın (örn. değerlendirme için daha ucuz bir model kullanın).
- **İstediğiniz zaman çıkın**: Yanıtın ortasında bile olsa hemen durdurmak için 'x' tuşuna basın. Veya hedefe ne zaman ulaşılacağına incelemecinin karar vermesine izin verin.
- **Ayarlanabilir**: bütçeyi kontrol etmek için `--max-rounds N`.

Belgelerin tamamı için [README_AUTO.md](README_AUTO.md) adresine bakın.

### 🧩 Grup Durum Yöneticisi

uag, uzun süredir devam eden çok dosyalı görevlerdeki ilerlemeyi izleyebilir. LLM düzinelerce dosyayı işlediğinde, 'batch_state' bekleyen, tamamlanmış ve başarısız olan dosyaların listesini diskte tutar. Oturum sona ererse veya tur zaman aşımına uğrarsa, bir sonraki çalıştırma kaldığı yerden devam eder; hiçbir şey kaybolmaz.

### 🛡 Döngüdeki İnsan

'human_ask', LLM'nin yıkıcı işlemler (dosya silme, üzerine yazma, kabuk komutları) gerçekleştirmeden önce duraklatılmasına ve onayınızı istemesine olanak tanır. Kontrol sizde olsun.

### 🛑 Kesinti (c tuşu / Durdurma düğmesi)

LLM yanıt oluşturmayı istediğiniz zaman durdurun ve LLM'ye geri bir durdurma komutu enjekte edin.

| Arayüz | Nasıl kesintiye uğratılır |
|---|---|
| **CLI** | LLM akışı sırasında 'c' tuşuna basın; mevcut yanıt durur ve LLM'nin buna göre yanıt vermesi için kullanıcı mesajı olarak "Durdur" gönderilir |
| **WEB kullanıcı arayüzü** | Kırmızı **■ Durdur** düğmesine tıklayın (LLM işlemi sırasında otomatik olarak görünür) |
| **Masaüstü GUI** | Kırmızı **■** düğmesine tıklayın (LLM işlemi sırasında otomatik olarak görünür) |

Kesinti, "hızlı enjeksiyon" olarak çalışır: sadece iptal etmek yerine, LLM'ye bir kullanıcı mesajı olarak "Durdur"u geri gönderir ve kesintiyi zarif bir şekilde sonlandırmasına veya onaylamasına olanak tanır.

Otomatik pilot modundan çıkmak için 'x' tuşuna basın (bkz. [README_AUTO.md](README_AUTO.md)).

### 🕵️ Tarayıcı Otomasyonu ve Web Denetleyicisi

İki tamamlayıcı Oyun Yazarı tabanlı araç:

- **browser_playwright**: Gerçek tarayıcı oturumlarını otomatikleştirin; gezinin, tıklayın, formları doldurun, verileri çıkarın, çok sayfalı akışları yönetin. Başsız veya başlı çalışır.
- **playwright_inspector**: Her adımda tarayıcı geçişlerini kaydedin, DOM anlık görüntülerini ve ekran görüntülerini yakalayın. Web etkileşimlerinde hata ayıklamak veya zaman içinde sayfa değişikliklerini denetlemek için kullanışlıdır.

### 🔄 Dinamik Takım Yükleme

'tool_catalog' ve 'tool_load', çalışma zamanında araçları keşfetmenize ve etkinleştirmenize olanak tanır.
Başlangıçta her şeyi yüklemenize gerek yok; yalnızca ihtiyacınız olanı, ihtiyacınız olduğunda etkinleştirin.

### 🦀 Rust Native Tools

### 🌐 i18n / L10n

日本語 / İngilizce / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / ve daha fazlası.
Geçiş yapmak için `UAGENT_LANG`ı ayarlayın. Yeni bir yerel ayar eklemek için [ADD_LOCALE.md](../src/uagent/docs/DEVELOP_I18N.md) adresine bakın.

Bu README'nin çevirileri [docs/README.translations.md](README.translations.md) adresinde mevcuttur.

### 🔒 Şifrelenmiş Ortam Değişkenleri

API anahtarlarını ve sırlarını, şifrelenmiş bir ".env" dosyası olan ".env.sec" dosyasında saklayın.
'Uag_envsec' ile yönetin.

## Yapılandırma ve Ayrıntılar

- **Ortam değişkenleri**: [docs/ENVIRONMENT.md](ENVIRONMENT.md)
- **Kurulum sihirbazı**: `python -m uagent.setup_cli`
- **Şifrelenmiş ortam**: `uag_envsec` — `.env`yi `.env.sec` olarak şifreleyin
- **Responses API**: Responses API modu için \`UAGENT_RESPONSES=1'i ayarlayın (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Sakana AI (Fugu) için otomatik olarak etkinleştirildi.
- **Geliştirici belgeleri**: [DEVELOP.md](../src/uagent/docs/DEVELOP.md)
- **Tool flow**: [TOOL_FLOW.md](../src/uagent/docs/TOOL_FLOW.md)
- **Küçük LLM ipuçları**: [SLM_TIPS.md](SLM_TIPS.md)

## Proje Felsefesi

uag, **sizin koşullarınıza göre makinenizde yapay zekanız olmayı hedefliyor.**

- SaaS bağımlılığı yok — yerel olarak çalışıyor
- Sağlayıcıya bağlı kalmanıza gerek yok; istediğiniz zaman geçiş yapın
- Kullanıcı arayüzüne kilitlenme yok — CLI / GUI / Web / A2A
- Özelliğe bağlı kalma yok; araçlar ve becerilerle genişletin

Satıcıya bağımlı kalmadan ücretsiz bir yapay zeka aracısı deneyimi.

### ✨ Kendi araçlarınızı oluşturun

[tr.md](TOOL_CREATOR_GUIDE.tr.md)
Adım adım kılavuz için buraya bakın.

## Katkıda bulunma

Katkılarınızı bekliyoruz! Hata raporları, özellik önerileri, belge iyileştirmeleri, çeviriler ve pull isteklerinin tümü takdir edilir.

- **Issues**: Hatalar veya özellik istekleri için GitHub sayısını açın.
- **Pull istekleri**: Depoyu fork edin, değişikliklerinizi yapın ve bir PR gönderin. Geliştirme kurulumu ve yönergeler için [DEVELOP.md](../src/uagent/docs/DEVELOP.md) dosyasına bakın.

Realtime Ses ve AEC3

## Realtime ses modu, tam çift yönlü mikrofonu ve hoparlör giriş/çıkışını destekler. AEC3 arka ucu eksikse uag, pywebrtc-audio'ı otomatik olarak yükler.

**Gerçek zamanlı sağlayıcılar**: OpenAI Realtime, Azure OpenAI GPT Realtime, Google Gemini Live, xAI Grok Voice ve Amazon Bedrock Nova Sonic. Bedrock çift yönlü akış SDK'sı yalnızca Bedrock seçildiğinde otomatik olarak yüklenir.

```bat
python scheck.py realtime
```

AEC3 gerçek mikrofon sinyalini (yakın) ve hoparlöre (uzak) gönderilen sesi kullanır. Tanılamayı yalnızca ses sorunlarını araştırırken etkinleştirin.

```bat
set UAGENT_REALTIME_AUDIO_DEBUG=1
python scheck.py realtime
```

### OpenAI Realtime Function Calling

OpenAI Realtime, güvenlikle sınırlı bir Function Calling entegrasyonunu destekler. Geçerli bağdaştırıcı salt okunur get_current_time işlevini otomatik olarak kullanıma sunar. Yıkıcı araçlar ve cihaz kontrolleri, açık bir izin verilenler listesi ve onay akışı gerektirir. Grok gerçek zamanlı, ayrı bir bağdaştırıcı kullanır ve bu OpenAI'e özgü Function Calling yolunu kullanmaz.

## Mimari ve operasyonel değişmezler

A2A yaşam döngüsü, I18N bağlamları, isteğe bağlı bağımlılıkların kurulumu, araç güvenliği, sağlayıcı yetenekleri, OAuth güven sınırları, yapılandırılmış olaylar ve kabul doğrulamasını kapsayan kalıcı uygulama sözleşmeleri için [ARCHITECTURE.md](ARCHITECTURE.md) dosyasına bakın.
