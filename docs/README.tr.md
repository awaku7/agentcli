<p align="center">
  <img src="https://raw.githubusercontent.com/awaku7/agentcli/main/assets/uag-logo.svg" alt="UAG — Universal AI Gateway" width="620">
</p>
<h1 align="center">UAG</h1>
<p align="center"><strong>Universal AI Gateway</strong><br>Yapay zekâ modelleriniz. Araçlarınız. Ortamınız.</p>

<p align="center">
  <a href="https://github.com/awaku7/agentcli/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/awaku7/agentcli/ci.yml?style=flat-square&label=CI" alt="CI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/v/uag?style=flat-square" alt="PyPI"></a>
  <a href="https://pypi.org/project/uag/"><img src="https://img.shields.io/pypi/pyversions/uag?style=flat-square" alt="Python versions"></a>
  <a href="../LICENSE"><img src="https://img.shields.io/github/license/awaku7/agentcli?style=flat-square" alt="License"></a>
  <a href="https://pepy.tech/projects/uag"><img src="https://static.pepy.tech/personalized-badge/uag?period=total&units=INTERNATIONAL_SYSTEM&left_color=grey&right_color=green&left_text=downloads" alt="Downloads"></a>
</p>
<p align="center"><a href="../README.md">English</a> · <a href="README.translations.md">Diğer diller</a></p>

---

**UAG, yerel çalışmayı önceliklendiren açık kaynaklı bir yapay zekâ ajanı çalışma ortamıdır.** Seçtiğiniz dil modelini kullandığınız araçlara ve sistemlere bağlar. Kod, dosya, tarayıcı, hizmet ve cihazlarla tek bir arayüzden çalışabilir; iş akışlarınızı tek bir model sağlayıcısına bağlamak zorunda kalmazsınız.

| **Modelinizi seçin** | **Gerçek araçlara bağlanın** | **Kontrol sizde kalsın** |
| :--- | :--- | :--- |
| OpenAI, Claude, Gemini, Grok, Bedrock ve Ollama gibi bulut ve yerel modeller | Dosyalar, kod, web, MCP, Agent Skills, eklentiler, bulut ve IoT | Yerel çalıştırma, insan onayı, kimlik bilgisi saklama ve yapılandırılabilir politikalar |

> UAG **model sağlayıcısı değil, ajan yürütme katmanıdır**. Harici modellere ve bağlı hizmetlere yapılan çağrılar yapılandırmaya bağlıdır. Yerel öncelikli çalışma, tümüyle çevrimdışı kullanım veya bütün araçların varsayılan olarak yalıtılması anlamına gelmez.

## Hızlı başlangıç
<!-- README-SYNC:quick-start -->

**Python 3.11 veya üzeri** gerekir. UAG'yi [PyPI](https://pypi.org/project/uag/) üzerinden yükleyin ve etkileşimli CLI'yi açın:

~~~bash
python -m pip install --upgrade uag
uag
~~~

İlk çalıştırmada kurulum sihirbazı model sağlayıcısını seçmenize ve kimlik bilgilerini ayarlamanıza yardımcı olur. Ortam değişkenleri veya kimlik bilgisi deposu da kullanılabilir. Daha fazla sağlayıcı ve araç bağımlılığını önceden kurmak için:

~~~bash
python -m pip install "uag[core,providers,tools]"
~~~

Ardından şu istekleri deneyin:

~~~text
> Bu Git deposunda neler değişti? Riskleri özetle.
> Bu kitaplığın en güncel belgelerini bul ve geçiş adımlarını açıkla.
> Bu dosyaları incele ve kısa bir rapor hazırla.
> :help
~~~

Yeni kullanıcılar Git ve sanal ortamları da açıklayan Windows kurulum kılavuzuna ve yapılandırma başvurusuna bakabilir: [Quickstart (Windows)](QUICKSTART.md) · [Environment](ENVIRONMENT.md).

## Arayüzler
<!-- README-SYNC:interfaces -->

Tüm giriş noktaları aynı ajan çalışma ortamını ve araç kaydını kullanır.

| Arayüz | Başlatma | Kullanım amacı |
| :--- | :--- | :--- |
| **CLI** | `uag` | Terminal ve otomasyon |
| **Desktop** | `uagg` | Yerel masaüstü görüşmeleri |
| **Web** | `uagw` | Tarayıcıdaki görüşmeler ve odalar |
| **A2A** | `uaga` | Ajanlar arası entegrasyon |
| **VS Code** | [Eklenti kılavuzu](VSCODE.md) | Kodla birlikte çalışma |

Desktop ve Web, ilk `uag[core,providers,tools]` kurulumuna dahil olmayan ek bağımlılıklar gerektirir:

~~~bash
# Desktop GUI (PySide6 and platform integrations)
python -m pip install "uag[platform]"

# Web UI (authentication dependencies, FastAPI, and Uvicorn)
python -m pip install "uag[web]" fastapi uvicorn
~~~

Web sunucusu başlangıçta FastAPI ve Uvicorn kurmayı deneyebilir. Önceden yüklemek otomatik kurulum bağımlılığını önler. Ayrıntılar: [CLI usage](USAGE.md) · [Environment](ENVIRONMENT.md).

## UAG ile neler yapabilirsiniz?
<!-- README-SYNC:capabilities -->

| Yetenek | UAG'nin sağladıkları |
| :--- | :--- |
| **Modelden bağımsız iş akışları** | `UAGENT_PROVIDER` ile bulut ve yerel sağlayıcılar arasında geçiş; araçları yeniden yazmaya gerek yok |
| **Kod ve dosyalar** | Depo gezinme, Git inceleme, lint, testler, dosya işlemleri ve tarayıcı otomasyonu |
| **Genişletilebilir araçlar** | 200'den fazla araç, `tool_catalog` / `tool_load` ile dinamik keşif, özel Python ve Rust araçları |
| **Bağlı ajanlar** | MCP, A2A, Claude Code uyumlu eklentiler, Agent Skills ve alt ajanlar |
| **Uzun süren işler** | Otomatik pilot, bağımsız okuma işlemlerinin paralel yürütülmesi, zamanlama, kurtarma ve kalıcı oturumlar |
| **Terminalin ötesinde** | Bulut, iletişim, belgeler, medya, gerçek zamanlı ses ve desteklenen IoT protokolleri |

### Tek çalışma ortamı, birçok entegrasyon
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

**Desteklenen model sağlayıcılarına örnekler** aşağıdadır. Sağlayıcıya özel ayarlar ortam kılavuzundadır.

**OpenAI · Anthropic · Gemini · Vertex AI · Azure OpenAI · Amazon Bedrock · Grok · DeepSeek · OpenRouter · Ollama · llama.cpp · LM Studio**

[ENVIRONMENT.md](ENVIRONMENT.md)

### Beceriler ve eklentilerle özelleştirme
<!-- README-SYNC:extensions -->

Çekirdeği değiştirmeden UAG'yi genişletin. SkillsMP veya ClawHub'dan Agent Skills kurun, MCP sunucularına bağlanın ya da araçlar, beceriler, ajanlar ve kancalar içeren Claude Code uyumlu eklentiler yükleyin.

~~~text
:skills mp_search browser automation
:plugin list
:plugin install <source>
:plugin marketplace list
~~~

Özel araçlar `TOOL_SPEC` ve `run_tool()` sağlayabilir; Rust tabanlı araçlar da desteklenir. Kılavuzlar: [Tool Creator Guide](../TOOL_CREATOR_GUIDE.md) · [Plugin Development Guide](../src/uagent/docs/DEVELOP_PLUGIN.md) · [MCP OAuth / Proxy](MCP_OAUTH_PROXY_GUIDE.md).

## Gerçek iş akışları için
<!-- README-SYNC:workflows -->

### Bağlam ve bellek
<!-- README-SYNC:context-memory -->

Büyük araç çıktıları modelin etkin bağlamını doldurmak yerine **artifact** olarak saklanabilir. Ajan daha sonra `artifact_read` ile yalnızca ilgili bölümü alır. Oturumlar varsayılan olarak SQLite'da tutulur; geçmiş arama ve açık bellek incelemesi de vardır.

- [Context compression](CONTEXT_COMPRESSION.tr.md)
- [Memory](MEMORY.md)
- [Session portability](SESSION_PORTABILITY.md)

### Otomasyon ve iş birliği
<!-- README-SYNC:automation -->

UAG, paralel bağımsız okuma işlemleri, çoklu ajan koordinasyonu, oturum kurtarma ve çok turlu işler için otomatik pilotu destekler. `:auto` ile başlatın; **F12** mevcut yanıtı keser ve otomatik pilotun durmasını ister.

- [Auto-pilot](README_AUTO.md)
- [Timers and scheduled tasks](SET_TIMER.md)
- [Multi-agent runtime](MULTI_AGENT_RUNTIME.md)

### Güvenlik ve gözlemlenebilirlik
<!-- README-SYNC:security -->

Hassas işlemler `human_ask` onayı gerektirebilir. Kimlik bilgileri işletim sisteminin güvenli deposunda veya şifreli dosyalarda saklanabilir. Web arayüzü yapılandırıldığında OIDC ile oturum açma ve erişim denetimini destekler. OpenTelemetry izleme ve ölçümleri **isteğe bağlıdır**.

- [Enterprise policies](ENTERPRISE_POLICY.md)
- [MXC sandbox](SANDBOX_MXC.md)
- [Remote Web / A2A MXC defaults](REMOTE_MXC_DEFAULT.md)
- [Web identity and rooms](WEB_IDENTITY_MEMORY.md)
- [OpenTelemetry design](UAG_OPENTELEMETRY_DESIGN.md)
- [Developer observability](../src/uagent/docs/DEVELOP_OBSERVABILITY.md)

Bu denetimler yapılandırılabilir; **her aracın bir sandbox içinde yalıtıldığına dair genel garanti vermez**. UAG'yi güvenilmeyen kullanıcılara veya ağlara açmadan önce dağıtım ve politika kılavuzlarını okuyun.

### Diller, cihazlar ve ses
<!-- README-SYNC:languages -->

UAG **38 yerel ayar** için kaynaklar (İngilizce ve 37 çeviri), isteğe bağlı tam çift yönlü ses ve SwitchBot, Matter, ECHONET Lite, BACnet, Modbus TCP ve OPC UA araçları sunar.

- [Translations](README.translations.md)
- [IoT use cases](IOT_USECASE.md)
- [Communication tools](COMMUNICATION.md)

## Belgeler
<!-- README-SYNC:documentation -->

Bu belgelerle başlayın, sonra ayrıntılara geçin:

| Buradan başlayın | Daha ayrıntılı |
| :--- | :--- |
| [Quickstart (Windows)](QUICKSTART.md) | [Architecture](ARCHITECTURE.md) |
| [CLI usage](USAGE.md) | [Context management](UAG_CONTEXT_MANAGEMENT_DESIGN.md) |
| [Environment and providers](ENVIRONMENT.md) | [Enterprise policy](ENTERPRISE_POLICY.md) |
| [Agent Skills and plugins](../src/uagent/docs/DEVELOP_PLUGIN.md) | [Tool flow](../src/uagent/docs/TOOL_FLOW.md) |
| [MCP and OAuth](MCP_OAUTH_PROXY_GUIDE.md) | [Computer Use](COMPUTER_USE_IMPLEMENTATION.md) |
| [VS Code extension](VSCODE.md) | [Developer guide](../src/uagent/docs/DEVELOP.md) |

Tam belge dizinine ve diğer dillere de göz atabilirsiniz: [Documentation](./) · [Other languages](README.translations.md).

## Geliştirme ve katkı
<!-- README-SYNC:contributing -->

~~~bash
git clone https://github.com/awaku7/agentcli.git
cd agentcli
python -m pip install -e ".[core,providers,test]"
~~~

**Python kodu** değiştiren bir pull request öncesinde ilgili testleri ve proje denetimlerini çalıştırın:

~~~bash
python -m ruff check src tests
python -m black --check src tests
python -m pytest -q .
~~~

Katkı kuralları ve geliştirici kılavuzu aşağıdadır. Hata bildirimleri, belge geliştirmeleri, araçlar, çeviriler ve odaklı pull requestler memnuniyetle karşılanır: [AGENTS.md](../AGENTS.md) · [Developer guide](../src/uagent/docs/DEVELOP.md).

## Lisans
<!-- README-SYNC:license -->

UAG şu lisans kapsamında dağıtılır: [Apache License 2.0](../LICENSE).
