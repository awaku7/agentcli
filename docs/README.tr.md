<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logosu" width="720">
</p>

<h1 align="center">uag — Evrensel AI Geçidi</h1>

<p align="center">
  <b>U</b>niversal <b>A</b>I <b>G</b>ateway — Ortamın, özgürlüğün.
</p>

<p align="center">
  Dosya işlemleri / Web arama / Görsel oluşturma ve analiz / PDF ve Excel çıkarımı / IoT kontrolü / MCP entegrasyonu<br>
  15+ sağlayıcı / 3 arayüz / Paralel araç yürütme / Ajan Beceri Marketi
</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli">GitHub</a>
  ·
  <a href="https://pypi.org/project/uag/">PyPI</a>
  ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Kendi dilinizde okuyun</a>
</p>

---

## Neden uag?

**Satıcı bağımlılığından kurtulun.** Çoğu AI asistanı sizi belirli bir sağlayıcıya veya bulut hizmetine bağlar. uag farklıdır.

- **Kendi makinenizde yerel olarak çalışır.** Verileriniz sizde kalır (yaptığınız API çağrıları hariç).
- **Sağlayıcı özgürlüğü**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock... 15'ten fazla sağlayıcı, tek bir arayüzden erişilebilir. Ortam değişkenlerini yeniden yapılandırarak aralarında geçiş yapın — yeniden kurulum veya taşıma gerektirmez.
- **131 araç**: Dosya G/Ç, web arama, görsel oluşturma, BLE cihaz taraması, MCP sunucu entegrasyonu — ve bunların **76'i paralel çalışır**. LLM aynı anda birden çok araç çağrısı yaptığında, uag bunları otomatik olarak bir iş parçacığı havuzu üzerinden yürütür.
- **3 Arayüz + A2A**: CLI, GUI, Web ve Ajanlar Arası Protokol. Aynı motor, herhangi bir arayüz.
- **IoT hazır**: SwitchBot, ECHONET Lite, Matter, UPnP — ev cihazlarınızı AI ile kontrol edin.
- **Ajan Becerileri**: Pazar yerinden topluluk tarafından oluşturulmuş becerileri yükleyin. uag'ı sınırsızca genişletin.

uag, **sizin koşullarınıza göre AI asistanınızdır.** Bir sağlayıcıya, bir arayüze veya bir platforma bağlı değildir.

## Hızlı Başlangıç

```bash
pip install uag
uag
```

İlk çalıştırmada, kurulum sihirbazı sizi sağlayıcı yapılandırması boyunca yönlendirir.
Tüm ortam değişkenleri için [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) bölümüne bakın.

## Özellikler

### 🧠 Çoklu Sağlayıcı Mimarisi

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax

Tüm sağlayıcılar aynı araç setini ve arayüzü paylaşır. `UAGENT_PROVIDER` ayarını değiştirerek geçiş yapın — kod değişikliği veya ayrı kurulum gerektirmez.

### ⚡ Paralel Araç Yürütme

LLM aynı anda birden çok araç talep ettiğinde, uag bunları **otomatik olarak paralelleştirir**.
76 araç `x_parallel_safe` olarak işaretlenmiştir ve 4 iş parçacıklı bir `ThreadPoolExecutor` aracılığıyla eşzamanlı olarak çalışır.

**Örnek**: "İskandinav başkentlerinde hava durumunu kontrol et" → LLM, `search_web` × 5 ülkeyi başlatır → 5 aramanın tümü paralel çalışır → sonuçlar tek bir toplu işte toplanır.

Salt okunur araçlar (dosya arama, karma hesaplama, dizin listeleme, çeviri, DB sorguları vb.) agresif bir şekilde paralelleştirilir.

### 🔄 Oturum Sürekliliği

- **Oturum ortasında sağlayıcı değiştirin** `UAGENT_PROVIDER` ile — konuşma geçmişi korunur.
- **Geçmiş oturumları yeniden yükleyin** `:load <index>` ile — kaldığınız yerden devam edin.
- **Araç sonuç önbellekleme**, aynı araç çağrısı tekrarlandığında gereksiz yeniden yürütmeyi önler.

### 🛠 131 Araç

| Kategori | Araçlar |
|---|---|
| **Dosya İşlemleri** | okuma/yazma/oluşturma/silme/arama/grep/karma/zip |
| **Web** | fetch_url, search_web, ekran görüntüsü, browser_playwright |
| **Medya** | görsel_oluşturma, görsel_analiz, img2img, ses_konuşma, ses_yazıya_dökme |
| **Belgeler** | PDF/PPTX/DOCX/RTF/ODT çıkarımı, Excel yapılandırılmış çıkarımı |
| **IoT** | SwitchBot (Bulut + BLE), ECHONET Lite, Matter, UPnP |
| **Geliştirme Araçları** | git_ops, python_compile, lint_format, run_tests, db_query, **13 idx tools** |
| **MCP** | Harici MCP sunucularına bağlanma, araçları listeleme, yürütme |
| **A2A** | Ajanlar arası iletişim (diğer uag örnekleri veya A2A uyumlu sunucularla) |
| **Sistem** | ortam değişkenleri, sistem özellikleri, saat, tarih hesaplama |

### 🖥 3 Arayüz + A2A

| Mod | Komut | Amaç |
|---|---|---|
| **CLI** | `uag` | Hızlı terminal tabanlı işlem |
| **GUI** | `uagg` | tkinter ile masaüstü arayüzü |
| **Web** | `uagw` | Tarayıcı tabanlı erişim |
| **A2A Sunucusu** | `uaga` | Çoklu ajan iletişimi için Ajan2Ajan protokolü |

### 🏠 IoT Cihaz Kontrolü

- **SwitchBot**: Bulut toplu kontrol ve BLE tarama/kontrol
- **ECHONET Lite**: Yerel ağdaki ev aletlerini (klima, ışıklar, su ısıtıcıları vb.) keşfedin ve kontrol edin
- **Matter**: Denetleyici/köprü/cihaz topolojisinin salt okunur incelemesi
- **UPnP**: Cihaz keşfi ve IGD port yönlendirme

[IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md) bölümüne bakın.

### 🎯 Ajan Beceri Marketi

`:skills mp_search` ile [SkillsMP](https://skillsmp.com) ve [ClawHub](https://clawhub.ai) üzerindeki topluluk becerilerine göz atın.
uag'ın yeteneklerini anında yükleyin ve genişletin.

### 🧩 Toplu İş Durum Yöneticisi

uag, uzun süren çok dosyalı görevlerde ilerlemeyi takip edebilir. LLM düzinelerce dosyayı işlerken, `batch_state` bekleyen, tamamlanan ve başarısız dosyaların listesini diske kaydeder. Oturum sona ererse veya bir tur zaman aşımına uğrarsa, bir sonraki çalıştırma kaldığı yerden devam eder — hiçbir şey kaybolmaz.

### 🛡 İnsan Katılımlı Döngü

`human_ask`, LLM'nin yıkıcı işlemleri (dosya silme, üzerine yazma, kabuk komutları) gerçekleştirmeden önce durmasını ve onayınızı istemesini sağlar. Kontrol sizde kalır.

### 🕵️ Tarayıcı Otomasyonu ve Web Denetçisi

Playwright tabanlı iki tamamlayıcı araç:

- **browser_playwright**: Gerçek tarayıcı oturumlarını otomatikleştirin — gezinme, tıklama, form doldurma, veri çıkarma, çok sayfalı akışları yönetme. Görünmez veya görünür modda çalışır.
- **playwright_inspector**: Tarayıcı geçişlerini kaydedin, her adımda DOM anlık görüntüleri ve ekran görüntüleri yakalayın. Web etkileşimlerinde hata ayıklama veya sayfa değişikliklerini zaman içinde denetleme için kullanışlıdır.

### 🔄 Dinamik Araç Yükleme

`tool_catalog` ve `tool_load` ile çalışma zamanında araçları keşfedin ve etkinleştirin.
Başlangıçta her şeyi yüklemek gerekmez — yalnızca ihtiyacınız olanı, ihtiyacınız olduğunda etkinleştirin.

### 🌐 i18n / L10n

日本語 / English / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / ve daha fazlası.
Değiştirmek için `UAGENT_LANG` ayarını yapın. Yeni bir yerel ayar eklemek için [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) bölümüne bakın.

Bu README'nin çevirileri [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) dosyasında mevcuttur.

### 🔒 Şifrelenmiş Ortam Değişkenleri

API anahtarlarını ve sırlarını `.env.sec` (şifrelenmiş bir `.env` dosyası) içinde saklayın.
`uag_envsec` ile yönetin.

## Yapılandırma ve Detaylar

- **Ortam değişkenleri**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Kurulum sihirbazı**: `python -m uagent.setup_cli`
- **Şifrelenmiş ortam**: `uag_envsec` — `.env` dosyasını `.env.sec` olarak şifreler
- **Responses API**: Responses API modu için `UAGENT_RESPONSES=1` ayarlayın (OpenAI/Azure/Bedrock/OpenRouter/Ollama/LM Studio)
- **Geliştirici dökümanları**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Küçük LLM ipuçları**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Proje Felsefesi

uag, **sizin makinenizde, sizin koşullarınızla, sizin AI'ınız** olmayı hedefler.

- SaaS bağımlılığı yok — yerel olarak çalışır
- Sağlayıcı bağımlılığı yok — istediğiniz zaman değiştirin
- Arayüz bağımlılığı yok — CLI / GUI / Web / A2A
- Özellik bağımlılığı yok — araçlar ve becerilerle genişletin

Satıcı bağımlılığı olmayan, ücretsiz bir AI ajan deneyimi.
