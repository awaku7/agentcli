<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="720">
</p>

<h1 align="center">uag — Evrensel Yapay Zeka Ağ Geçidi</h1>

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

## Neden uag?

**Satıcıya bağlı kalmaktan kurtulun.** Çoğu AI asistanı sizi belirli bir sağlayıcıya veya bulut hizmetine bağlar. uag farklıdır.

- **Makinenizde yerel olarak çalışır**. Verileriniz sizinle kalır (yaptığınız API çağrıları hariç).
- **Sağlayıcı özgürlüğü**: OpenAI, Claude, Gemini, DeepSeek, Ollama, Azure, Bedrock, HuggingFace... 15'ten fazla sağlayıcı, hepsine tek bir arayüzden erişilebilir. Ortam değişkenlerini yeniden yapılandırarak bunlar arasında geçiş yapın; yeniden yükleme yok, geçiş yok.
- **131 araç**: Dosya G/Ç, web araması, görüntü oluşturma, Gmail, BLE cihaz tarama, MCP sunucu entegrasyonu — **76 araç paralel güvenlidir** (iş parçacığı havuzu aracılığıyla en fazla 8 eşzamanlı yürütme, "UAGENT_PARALLEL_WORKERS" aracılığıyla yapılandırılabilir). LLM aynı anda birden fazla araç çağrısı başlattığında, uag bunları otomatik olarak paralelleştirir.
- **3 kullanıcı arayüzü + A2A**: CLI, GUI, Web ve Aracıdan Aracıya protokolü. Aynı motor, herhangi bir arayüz.
- **IoT'ye hazır**: SwitchBot, ECHONET Lite, Matter, UPnP — ev cihazlarınızı yapay zeka aracılığıyla kontrol edin.
- **Ajan Becerileri**: Piyasadan topluluk tarafından oluşturulan becerileri yükleyin. Uag'ı sonsuza kadar uzatın.

uag **kendi şartlarınıza göre yapay zeka asistanınızdır**. Bir sağlayıcıya bağlı değil, bir arayüze bağlı değil, bir platforma bağlı değil.

## Hızlı Başlangıç

```bash
pip install uag
uag
```

İlk başlatmada kurulum sihirbazı, sağlayıcı yapılandırmasında size yol gösterir.
Tüm ortam değişkenleri için [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md) adresine bakın.

## Özellikler

### 🧠 Çoklu Sağlayıcı Mimarisi

OpenAI / Azure / Bedrock / OpenRouter / Ollama / Gemini / Vertex AI / Claude / Grok / NVIDIA / DeepSeek / Z.AI (Zhipu AI) / HuggingFace / Alibaba Cloud (Qwen) / KIMI (Moonshot AI) / Xiaomi MiMo / LM Studio / MiniMax / **Sakana AI (Fugu)**

Tüm sağlayıcılar aynı araç setini ve arayüzü paylaşır. 'UAGENT_PROVIDER' ayarını yaparak geçiş yapın; kod değişikliği yok, ayrı kurulum yok.

### ⚡ Paralel Takım Yürütme

LLM aynı anda birden fazla araç talep ettiğinde bunları **otomatik olarak paralelleştirir**.
76 araç 'x_parallel_safe' olarak işaretlenmiştir ve bir 'ThreadPoolExecutor' aracılığıyla eşzamanlı olarak çalıştırılır (varsayılan olarak 8 iş parçacığı; değiştirmek için 'UAGENT_PARALLEL_WORKERS' ayarlayın).

**Örnek**: "İskandinav başkentlerindeki hava durumunu kontrol edin" sorusunu sorun → Yüksek Lisans `search_web'i çalıştırıyor × 5 ülke → 5 aramanın tümü paralel olarak yürütülüyor → sonuçlar tek bir grupta toplanıyor.

Salt okunur araçlar (dosya arama, karma hesaplama, dizin listeleme, çeviri, veritabanı sorguları vb.) agresif bir şekilde paralelleştirilmiştir.

### 🔄 Oturum Sürekliliği

- **Switch providers mid-session** with `UAGENT_PROVIDER` — conversation history is preserved.
- **Reload past sessions** with `:load <index>` — pick up where you left off.
- **Tool result caching** avoids redundant re-execution when the same tool call repeats.

### 🛠 131 Araç

| Kategori | Araçlar |
|---|---|
| **Dosya İşlemleri** | okuma/yazma/oluşturma/silme/arama/grep/hash/zip, ayrıştırma_eml (.eml dosyaları) |
| **Web** | fetch_url, search_web, ekran görüntüsü, tarayıcı_oynatma yazarı |
| **Medya** | created_image, analyze_image, img2img, audio_speech, audio_transcribe |
| **Belgeler** | PDF/PPTX/DOCX/RTF/ODT çıkarma, Excel yapılandırılmış çıkarma |
| **İletişim** | gmail_send, gmail_read, bluesky, discord_channel, takımlar_webhook — bkz. [COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| **IoT** | SwitchBot (Bulut + BLE), ECHONET Lite, Matter, UPnP |
| **Geliştirme Araçları** | git_ops, python_compile, lint_format, run_tests, db_query, **13 kaynak kodu gezgini (idx ailesi)** |
| **MCP** | Harici MCP sunucularına bağlanın, araçları listeleyin, çalıştırın |
| **A2A** | Aracıdan aracıya iletişim (diğer uag örnekleri veya A2A uyumlu sunucularla) |
| **Sistem** | env değişkenleri, sistem özellikleri, saat, tarih hesaplaması |
| **Kaynak Gezintisi** | Python, PHP, TypeScript, Java, C#, Dart, C/C++, Rust, Go, Swift, Kotlin, COBOL için **13 idx aracı** — tüm dosyayı okumadan bir işlev/sınıf dizini veya belirli bir tanım edinin |

### 🖥 4 Arayüz + VS Kod Uzantısı

| Modu | Komut | Amaç |
|---|---|---|
| **CLI** | 'uag' | Hızlı terminal tabanlı operasyon |
| **GUI** | 'uagg' | tkinter aracılığıyla Masaüstü Kullanıcı Arayüzü |
| **Web** | 'uagw' | Tarayıcı tabanlı erişim |
| **A2A Sunucusu** | 'uaga' | Çoklu aracı iletişimi için Agent2Agent protokolü |
| **VS Kodu** | — | [Uzantı](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) Sohbet Paneli, Açıklama, Yeniden Düzenleme, Hata Düzeltme ve Araç Ağacı Görünümü ile |

Kurulum, komutlar, tuş atamaları ve yapılandırma gibi VS Code uzantısıyla ilgili ayrıntılar için [VSCODE.md](https://github.com/awaku7/agentcli/blob/main/VSCODE.md) adresine bakın.

### 🏠 IoT Cihaz Kontrolü

- **SwitchBot**: Bulut toplu kontrolü ve BLE tarama/kontrol
- **ECHONET Lite**: Yerel ağdaki ev aletlerini (klima, ışıklar, su ısıtıcıları vb.) keşfedin ve kontrol edin
- **Madde**: Denetleyici/köprü/cihaz topolojisinin salt okunur denetimi
- **UPnP**: Cihaz keşfi ve IGD bağlantı noktası iletme

Bkz. [IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/IOT_USECASE.md)

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

Belgelerin tamamı için [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md) adresine bakın.

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

Otomatik pilot modundan çıkmak için 'x' tuşuna basın (bkz. [README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/README_AUTO.md)).

### 🕵️ Tarayıcı Otomasyonu ve Web Denetleyicisi

İki tamamlayıcı Oyun Yazarı tabanlı araç:

- **browser_playwright**: Gerçek tarayıcı oturumlarını otomatikleştirin; gezinin, tıklayın, formları doldurun, verileri çıkarın, çok sayfalı akışları yönetin. Başsız veya başlı çalışır.
- **playwright_inspector**: Her adımda tarayıcı geçişlerini kaydedin, DOM anlık görüntülerini ve ekran görüntülerini yakalayın. Web etkileşimlerinde hata ayıklamak veya zaman içinde sayfa değişikliklerini denetlemek için kullanışlıdır.

### 🔄 Dinamik Takım Yükleme

'tool_catalog' ve 'tool_load', çalışma zamanında araçları keşfetmenize ve etkinleştirmenize olanak tanır.
Başlangıçta her şeyi yüklemenize gerek yok; yalnızca ihtiyacınız olanı, ihtiyacınız olduğunda etkinleştirin.

### 🌐 i18n / L10n

日本語 / İngilizce / 简体中文 / 繁體中文 / 한국어 / Español / Français / Русский / ve daha fazlası.
Geçiş yapmak için `UAGENT_LANG`ı ayarlayın. Yeni bir yerel ayar eklemek için [ADD_LOCALE.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/ADD_LOCALE.md) adresine bakın.

Bu README'nin çevirileri [docs/README.translations.md](https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md) adresinde mevcuttur.

### 🔒 Şifrelenmiş Ortam Değişkenleri

API anahtarlarını ve sırlarını, şifrelenmiş bir ".env" dosyası olan ".env.sec" dosyasında saklayın.
'Uag_envsec' ile yönetin.

## Yapılandırma ve Ayrıntılar

- **Ortam değişkenleri**: [ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/ENVIRONMENT.md)
- **Kurulum sihirbazı**: `python -m uagent.setup_cli`
- **Şifrelenmiş ortam**: `uag_envsec` — `.env`yi `.env.sec` olarak şifreleyin
- **Responses API**: Responses API modu için `UAGENT_RESPONSES=1'i ayarlayın (OpenAI/Azure/Bedrock/OpenRouter/Ollama/Alibaba/LM Studio/Sakana AI). Sakana AI (Fugu) için otomatik olarak etkinleştirildi.
- **Geliştirici belgeleri**: [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md)
- **Küçük LLM ipuçları**: [SLM_TIPS.md](https://github.com/awaku7/agentcli/blob/main/SLM_TIPS.md)

## Proje Felsefesi

uag, **sizin koşullarınıza göre makinenizde yapay zekanız olmayı hedefliyor.**

- SaaS bağımlılığı yok — yerel olarak çalışıyor
- Sağlayıcıya bağlı kalmanıza gerek yok; istediğiniz zaman geçiş yapın
- Kullanıcı arayüzüne kilitlenme yok — CLI / GUI / Web / A2A
- Özelliğe bağlı kalma yok; araçlar ve becerilerle genişletin

Satıcıya bağımlı kalmadan ücretsiz bir yapay zeka aracısı deneyimi.
