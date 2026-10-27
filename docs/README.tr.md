<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="uag logo" width="680">
</p>

<h1 align="center">uag</h1>

<p align="center">
  <strong>Universal AI Gateway</strong><br>
  Tek yerel ajan. Her model. Her araç. Sizin ortamınız, sizin kurallarınız.
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
  <a href="https://github.com/awaku7/agentcli/discussions">Discussions</a> ·
  <a href="https://github.com/awaku7/agentcli/blob/main/docs/README.translations.md">Translations</a>
</p>

______________________________________________________________________

**uag neden var?**

uag, tercih ettiğiniz modeli gerçekten kullandığınız araçlara bağlayan, yerel öncelikli bir AI ajanıdır.
Dosyalar, tarayıcılar, kod tabanları, iletişim, bulut API'leri, IoT cihazları, MCP sunucuları ve çoklu ajan iş akışları için tek ve genişletilebilir bir çalışma zamanı sağlar.

- **Sağlayıcı özgürlüğü** — OpenAI, Anthropic, Gemini, Azure, Bedrock, Ollama, llama.cpp, Grok, DeepSeek ve daha fazlası.
- **Yerel öncelikli çalıştırma** — ajan çalışma zamanınız ve araç çalıştırma işlemleri makinenizde kalır; yalnızca seçtiğiniz API çağrıları dışarı çıkar.
- **Tek araç katmanı** — aynı araçlar CLI, masaüstü GUI, web arayüzü, VS Code ve A2A üzerinden çalışır.
- **Tasarımdan paralel** — bağımsız, yalnızca okuma yapan işlemler eşzamanlı yürütülebilir.
- **Genişletilebilir** — çekirdeği değiştirmeden araçlar, eklentiler, Agent Skills, MCP sunucuları ve Rust destekli araçlar ekleyin.
- **Güvenlik odaklı** — yıkıcı işlemler, kimlik bilgileri, cihaz kontrolleri ve ağ yazma işlemleri açık onay ve politika denetimlerini destekler.

> **Kısacası:** uag, AI modelleriniz ile gerçek ortamınız arasındaki kontrol düzlemidir.

> **🧠 Bağlam duyarlı araç sonuçları** — Mümkün olduğunda, büyük boyutlu araç sonuçları aktif model bağlamının dışında tutulur. uag bunları Artifact olarak depolar ve bunun yerine modele kararlı bir Artifact referansı içeren sınırlı bir önizleme iletir. Bu, bir araç büyük bir sonuç ürettiğinde takip eden turlar için gereken girdi token sayısını önemli ölçüde azaltabilir.
> [Ayrıntılı bağlam sıkıştırma kılavuzu](CONTEXT_COMPRESSION.tr.md)

## Hızlı başlangıç

**Python 3.11+**

```bash
python -m pip install --upgrade uag
uag
```

İlk başlatma kurulum sihirbazını açar. Sihirbaz bir sağlayıcıyı yapılandırmanıza yardımcı olur ve seçilen ayarları yerel ortamınızda saklar.

Yaygın özellik grupları için:

```bash
python -m pip install "uag[core,providers,tools]"
```

```text
> What files changed in this repository?
> Search the web for today's AI news and summarize the top five stories.
> :help
```

[Quickstart](QUICKSTART.md) · [Environment](ENVIRONMENT.md)

## Arayüzler

| Arayüz | Komut | En uygun kullanım |
|---|---|---|
| **CLI** | `uag` | Hızlı, klavye öncelikli çalışma |
| **Desktop GUI** | `uagg` | Yerel bir masaüstü deneyimi |
| **Web UI** | `uagw` | Tarayıcı tabanlı erişim |
| **A2A server** | `uaga` | Ajanlar arası iletişim |
| **VS Code** | Extension | Editörde araçları açıklama, yeniden düzenleme, düzeltme ve tarama |

Tüm arayüzler aynı sağlayıcı yapılandırmasını, araç kayıt defterini, güvenlik kurallarını ve oturum verilerini paylaşır.

~~~bash
# Desktop GUI
python -m pip install "uag[platform]"

# Web UI
python -m pip install "uag[web]" fastapi uvicorn
~~~

[Interface options](USAGE.md) · [Environment](ENVIRONMENT.md)

## Neler oluşturabilirsiniz

Sağlayıcı adaptörleri, aşağıdakiler dâhil olmak üzere barındırılan ve yerel çalışma zamanlarını kapsar:

- Dosyaları okuyun, oluşturun, düzenleyin, arayın, özetleyin, arşivleyin ve inceleyin
- Git değişikliklerini inceleyin, gizli bilgileri tarayın, testleri çalıştırın, lint uygulayın, derleyin ve kapsamı ölçün
- Büyük Python, TypeScript, JavaScript, Go, Rust, C/C++, Java, C#, COBOL, VBA ve diğer kod tabanlarında gezinin
- Çok sayfalı iş akışları ve indirmeler dâhil olmak üzere tarayıcıları Playwright ile otomatikleştirin

- **MCP** — OAuth etkin hizmetler de dâhil olmak üzere harici araç sunucularına bağlanın
- **A2A** — diğer ajanlar ve uyumlu sunucularla koordinasyon sağlayın
- **Cloud** — yazma işlemleri için onayla AWS, Google Cloud ve Azure API erişimi
- **Communication** — Gmail, Bluesky, Discord, Microsoft Teams ve pybitchat
- **IoT** — SwitchBot, ECHONET Lite, Matter, BACnet, Modbus TCP, OPC UA ve UPnP
- **Media** — görüntü oluşturma/düzenleme, ses transkripsiyonu/sentezi, kamera yakalama ve QR kodları
- **Documents** — PDF, PowerPoint, Word, Excel, CSV, JSON, YAML, SQL ve günlük analizi

- **SwitchBot** — Cloud ve BLE keşfi, durum, kontrol, toplu işlemler ve abonelikler
- **ECHONET Lite** — INF bildirimleri de dâhil olmak üzere Japon ev aletlerini keşfedin ve kontrol edin
- **Matter** — uç noktalar, kümeler, öznitelikler, durum geçmişi, abonelikler ve kontrol
- **BACnet / Modbus TCP / OPC UA** — endüstriyel ve bina otomasyonu okuma, yazma, gezinme ve izleme
- **UPnP** — cihaz keşfi, WAN durumu ve yönlendirici port eşleme yönetimi

### uag nereye oturur?

uag bir tarafta insanlar ve arayüzler, diğer tarafta modeller, araçlar ve gerçek dünya sistemleri arasında yer alır.
Konuşmayı koordine eder, yetenekleri seçer, güvenlik kurallarını uygular ve iş akışının sürdürülebilir olmasını sağlar.

~~~mermaid
flowchart LR
    UI["CLI · Desktop · Web · VS Code · A2A"] --> UAG["UAG agent runtime"]
    UAG --> MODELS["Hosted & local models"]
    UAG --> TOOLS["Tools & extensions"]
    UAG --> STATE["Sessions & context"]
    TOOLS --> SYSTEMS["Files · Code · Web · MCP · Cloud · IoT"]
    POLICY["Confirmation · Credentials · Policy"] -.-> UAG
~~~

### Eklentiler, Agent Skills ve marketplace'ler

Çekirdeği çatallamadan uag'ı uzmanlaşmış bir ajana dönüştürün:

- **Claude Code uyumlu eklentileri** bir dizinden, ZIP'ten, Git deposundan, HTTP kaynağından veya marketplace'ten kurun
- Becerileri, alt ajanları, MCP sunucularını, kancaları, slash komutlarını, çıktı stillerini, bağımlılıkları ve kanalları paketleyin
- [SkillsMP](https://skillsmp.com) ve [ClawHub](https://clawhub.ai) üzerinden topluluk yeteneklerine göz atın
- `UAGENT_EXTERNAL_TOOLS_DIR` aracılığıyla özel kuruluş becerilerini ve araçlarını yerel olarak ekleyin

```text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
```

[Plugin Development Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP_PLUGIN.md) sayfasına bakın.

- Dosyalar, web, medya, belgeler, kod, bulut, iletişim ve IoT için **200+ araç**
- **Dinamik keşif ve yükleme** — yetenekleri bulmak için `tool_catalog`, yalnızca gerektiğinde etkinleştirmek için `tool_load` kullanın
- **Kod zekâsı** — `code_map`, dile özgü `idx` gezginleri, Git incelemesi, test çalıştırma, lint, derleme ve kapsam ölçümü
- Yetenekler, ajanlar, MCP sunucuları, kancalar, komutlar ve marketplace'lerle **Claude Code uyumlu eklentiler**
- SkillsMP ve ClawHub'dan **Agent Skills**
- `TOOL_SPEC` ve `run_tool()` kullanan **özel Python araçları**
- Hafif yerel uzantılar için **Rust destekli araçlar**

[Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [MCP OAuth / Proxy Guide](MCP_OAUTH_PROXY_GUIDE.md)

## Gerçek iş akışları için tasarlandı

### 🧠 Bağlam duyarlı araç sonuçları

Mümkün olduğunda, büyük boyutlu araç sonuçları aktif model bağlamının dışında tutulur. uag bunları Artifact olarak depolar ve bunun yerine modele kararlı bir Artifact referansı içeren sınırlı bir önizleme iletir. Bu, bir araç büyük bir sonuç ürettiğinde takip eden turlar için gereken girdi token sayısını önemli ölçüde azaltabilir.

`:load <index>` ile önceki konuşmaları sürdürün. Araç sonuçları önbelleğe alınabilir ve uygulamayı yeniden oluşturmadan sağlayıcılar değiştirilebilir.

[Context compression](CONTEXT_COMPRESSION.tr.md) · [Memory](MEMORY.md) · [Session portability](SESSION_PORTABILITY.md)

### Auto-pilot

İsteğe bağlı bir inceleyici modeliyle çok turlu çalışma için `:auto` kullanın. `--max-rounds N` ile tur sınırı belirleyin. Auto-pilot'u durdurmak için **F12**'e, mevcut yanıtı durdurmak için **F12**'ye basın.

Bağımsız, yalnızca okuma yapan işlemler güvenli olduğunda eşzamanlı yürütülür. Web aramaları, dosya inceleme, depo analizi ve benzer iş yükleri yapılandırılabilir bir worker havuzuyla (`UAGENT_PARALLEL_WORKERS`) paralel olarak tamamlanabilir. Yazma işlemleri serileştirilir veya onay gerektirir.

Oturum sürekliliği, araç sonucu önbelleğe alma, toplu işlem durumu, yeniden başlatma kurtarma, DAG zamanlama ve çoklu ajan orkestrasyonu; karmaşık işleri tek seferlik olmaktan çıkarıp sürdürülebilir hale getirir.

[Auto-pilot](README_AUTO.md) · [Timers](SET_TIMER.md) · [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### 🌍 Özel, çok dilli ve politika farkındalıklı

`human_ask`, hassas işlemlerden önce duraklar. Dosya silme, üzerine yazma, kabuk komutları, cihaz kontrolleri, kimlik bilgisi işlemleri ve ağ yazma işlemleri onay ve politika kurallarıyla yönetilebilir.

Uzun süre geçerli gizli bilgileri istemlere yerleştirmek yerine kimlik bilgileri deposunu kullanın:

Web UI, Authorization Code + PKCE kullanarak OIDC oturum açmayı, doğrulanmış ID tokenlarını, sunucu tarafı oturumları ve proje/oda erişim kontrollerini içerir. Doğrulanmış Microsoft Entra ID grup talepleri, yapılandırıldığında dizin destekli erişim politikasına besleme yapabilir. Windows Active Directory, OAuth ve trusted-proxy dağıtımları, açıkça doğrulanmış kimlik adaptörleri aracılığıyla entegre olabilir; Windows AD, dağıtıma özgü bir Kerberos/Negotiate doğrulayıcısı gerektirir ve varsayılan olarak etkin değildir.

uag, Agent, LLM, araç, Context, Memory ve alma işlemlerine yönelik isteğe bağlı, sağlayıcıdan bağımsız OpenTelemetry izleme ve ölçümleri içerir. Gözlemlenebilirlik varsayılan olarak devre dışıdır.

Yerel öncelikli çalışma, UAG'nin varsayılan olarak tamamen çevrimdışı olduğu veya tüm araçların yalıtıldığı anlamına gelmez. Harici modellere ve bağlı hizmetlere yapılan çağrılar yapılandırmaya bağlıdır.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A](REMOTE_MXC_DEFAULT.md)
- [Web identity](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry](UAG_OPENTELEMETRY_DESIGN.md)

### 🌍 Çok dilli çeviri

- `translate_text`, `provider=auto`, `provider=deepl` veya `provider=google` seçenekleri aracılığıyla Google Translate’ı ve resmi DeepL Python istemcisini destekler.
- Araç tanımları, yer tutucular ve teknik tanımlayıcılar korunmuş olarak 37 dilde ve İngilizce’de (toplam 38) mevcuttur.

Tam çift yönlü ses; OpenAI Realtime, Azure OpenAI, xAI Grok Voice, Gemini Live ve Bedrock Nova Sonic üzerinden, isteğe bağlı AEC3 yankı iptali ve güvenlikle sınırlandırılmış gerçek zamanlı işlev çağrısıyla kullanılabilir.

[Translations](README.translations.md) · [IoT](IOT_USECASE.md) · [Communication](COMMUNICATION.md)

## Belgeler

| Konu | Belgeleme |
|---|---|
| Environment variables | [docs/ENVIRONMENT.md](https://github.com/awaku7/agentcli/blob/main/docs/ENVIRONMENT.md) |
| Architecture and invariants | [docs/ARCHITECTURE.md](https://github.com/awaku7/agentcli/blob/main/docs/ARCHITECTURE.md) |
| Computer Use | [docs/COMPUTER_USE_IMPLEMENTATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMPUTER_USE_IMPLEMENTATION.md) |
| Repository tools | [docs/REPOSITORY_TOOLS.md](https://github.com/awaku7/agentcli/blob/main/docs/REPOSITORY_TOOLS.md) |
| IoT use cases | [docs/IOT_USECASE.md](https://github.com/awaku7/agentcli/blob/main/docs/IOT_USECASE.md) |
| Communication tools | [docs/COMMUNICATION.md](https://github.com/awaku7/agentcli/blob/main/docs/COMMUNICATION.md) |
| Auto-pilot | [docs/README_AUTO.md](https://github.com/awaku7/agentcli/blob/main/docs/README_AUTO.md) |
| MCP OAuth / Proxy | [docs/MCP_OAUTH_PROXY_GUIDE.md](https://github.com/awaku7/agentcli/blob/main/docs/MCP_OAUTH_PROXY_GUIDE.md) |
| VS Code extension | [docs/VSCODE.md](https://github.com/awaku7/agentcli/blob/main/docs/VSCODE.md) |
| Developer guide | [src/uagent/docs/DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) |
| Tool flow | [src/uagent/docs/TOOL_FLOW.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/TOOL_FLOW.md) |

[Quickstart](QUICKSTART.md) · [Architecture](ARCHITECTURE.md) · [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md)

## Geliştirme ve katkıda bulunma

```bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
```

PR öncesi kontrolleri çalıştırın:

```bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
```

Tam geliştirme iş akışı için [DEVELOP.md](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) sayfasına bakın.

Hata raporları, özellik fikirleri, belge iyileştirmeleri, çeviriler, araçlar, beceriler ve pull request'ler memnuniyetle karşılanır. Büyük değişikliklerden önce lütfen bir issue veya discussion açın. [Developer Guide](https://github.com/awaku7/agentcli/blob/main/src/uagent/docs/DEVELOP.md) sayfasını okuyun ve pull request göndermeden önce yukarıdaki kontrolleri çalıştırın.

## Lisans

[Apache License 2.0](https://github.com/awaku7/agentcli/blob/main/LICENSE) kapsamında lisanslanmıştır.
