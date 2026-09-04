# KULLANIM (Komut satırı seçenekleri)

Bu belge, uag giriş noktaları için kullanılabilen komut satırı seçeneklerini açıklamaktadır.

______________________________________________________________________

## Giriş noktaları

| Komut | Python modülü | Arayüz |
|---|---|---|
| `uag` | `python -m uagent` | CLI (stdin döngüsü) |
| `uagg` | `python -m uagent.gui` | GUI (tkinter) |
| `uagw` | `python -m uagent.web` | Web sunucusu (FastAPI) |
| `uaga` | `python -m uagent.a2a.server` | A2A HTTP sunucusu |

______________________________________________________________________

## CLI başlatma seçenekleri (`uag`)

### `--workdir` / `-C <yol>`

Çalışma dizini. Ayarlanmazsa, `UAGENT_WORKDIR` ortam değişkenine, ardından da geçerli dizine başvurulur.
Dizin yoksa oluşturulur.

### `--tool-genre-mask <int>`

Araç türü bit maskesi. Belirtildiğinde, etkileşimli tür seçimi istemi atlanır.

| Bit | Tür | Açıklama |
|-----|-------|-------------|
| 1 | basic | Temel dosya/sohbet araçları |
| 2 | comm | İletişim araçları (Bluesky, Teams) |
| 4 | office | Ofis paketi araçları (Excel, PDF, PPTX) |
| 8 | devel | Geliştirme araçları (git, lint, derleme) |
| 16 | iot | IoT cihaz araçları (SwitchBot, ECHONET, Matter, UPnP) |
| 32 | exec | Komut yürütme araçları |
| 64 | external | Harici eklenti araçları |
| 128 | media | Görüntü/ses oluşturma ve analiz |
| 256 | file | Dosya yönetimi araçları |
| 512 | index | Kaynak/dizin gezinme araçları |
| 1024 | dev | Geliştirici ve depo araçları |
| 2048 | web | Web ve tarayıcı araçları |
| 4096 | utility | Yardımcı ve destek araçları |
| 8191 | all | Tüm araçlar |

Örnekler:

```
uag --tool-genre-mask 1 # sadece temel
uag --tool-genre-mask 9 # temel + geliştirme (1 + 8)
uag --tool-genre-mask 8191    # tüm araçlar
```

### `--use-tool` / `--no-use-tool`

Araç tanımlarının LLM'e gönderilmesini etkinleştirir veya devre dışı bırakır. `UAGENT_USE_TOOL` ortam değişkenini geçersiz kılar.

- `--use-tool`, araç gönderimini zorla etkinleştirir.
- `--no-use-tool`, araç gönderimini zorla devre dışı bırakır.

Devre dışı bırakıldığında, LLM hiçbir araç tanımı almaz ve hiçbir aracı çağıramaz.

### `--computer-use` / `--no-computer-use`

Bilgisayar Kullanımını etkinleştirir veya devre dışı bırakır. `UAGENT_COMPUTER_USE` ortam değişkenini geçersiz kılar.

### `--inject-message` / `-M <message>`

Başlangıçta LLM'e bir mesaj ekler ve işlem tamamlandıktan sonra çıkar. Bu, `--non-interactive` seçeneğini de içerir.

### `--embedded`

Kısıtlı veya tekrarlanabilirliğe duyarlı dağıtımlar için gömülü mod.

- Oturum deposunu devre dışı bırakır.
- Açıkça etkinleştirilmedikçe araç yönetimi araçlarını (`tool_catalog`, `tool_load`, `unload_tool`) gizler.
- `--tool-genre-mask` seçeneğini yok sayar; araçları açıkça yüklemek için `--enable-tool` seçeneğini kullanın.

### `--enable-tool <ad>`

Başlangıçta bir aracı açıkça yükler. Bu seçenek tekrarlanabilir ve virgülle ayrılmış adlar da kabul edilir.

```
uag --embedded --enable-tool handle_mcp_v2 --enable-tool human_ask
uag --embedded --enable-tool handle_mcp_v2,human_ask
```

Belirtilen sıra korunur ve LLM'e sunulan araç sırasına yansıtılır. Açıkça etkinleştirilen araçlar, otomatik olarak kaldırılmaya karşı sabitlenir.

### `--plugin-dir <yol>`

Eklentileri belirtilen dizinden yükler. Bu seçenek tekrarlanabilir.

______________________________________________________________________

## Yalnızca CLI seçenekleri

### `--inject-message-auto <hedef-seçenekleri>`

Etkileşimli olmayan, enjekte edilmiş bir hedeften otomatik pilotu başlatır. Değer, `:auto` ile aynı seçenekleri kullanır; değer seçenekler içeriyorsa tamamını tırnak içine alın.

```
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Öğeleri sırala --max-rounds 10"
uag --embedded --enable-tool handle_mcp_v2 --inject-message-auto "Öğeleri sırala --infinite"
```

Normal mod, gözden geçirenin karar yolunu kullanır. Tekli LLM sentinel modunu etkinleştirmek için `UAGENT_AUTO_SENTINEL=1` ayarını yapın. Bu modda, hedef LLM her yanıtı tam olarak şunlardan biriyle bitirmelidir:

- `<AUTO_CONTINUE>` — başka bir tur çalıştır
- `<AUTO_COMPLETE>` — başarıyla bitir

Eksik veya geçersiz işaretleyiciler, otomatik pilotu güvenli bir şekilde durdurur. Bu, hedef LLM'ü yine de çalıştırır; yalnızca ek denetleyici LLM çağrısını önler.

### `--non-interactive`

Etkileşimsiz mod. stdin döngüsünü başlatmaz. Konumsal bir argüman olarak bir dosya yolu verilirse, bu işlenir ve program hemen sonlandırılır.

```
uag --non-interactive README.md
uag --non-interactive --workdir /tmp/project
```

______________________________________________________________________

## Web sunucusu seçenekleri (`uagw`)

### `--host <address>`

Web sunucusunun bağlanma adresi (varsayılan: `127.0.0.1`, `UAGENT_WEB_HOST` ile geçersiz kılınabilir).

Varsayılan olarak, web sunucusu yalnızca localhost'ta (`127.0.0.1`) dinleme yapar. Ağdaki diğer makinelerden erişilebilir hale getirmek için `--host 0.0.0.0` kullanın.

```
uagw --host 0.0.0.0
uagw --host 192.168.1.10
```

### `--tool-genre-mask <int>`

Yukarıda açıklanan bit maskesini kullanarak araç türlerini seçin. Belirtildiğinde, etkileşimli tür istem atlanır.

### `--use-tool` / `--no-use-tool`

LLM'e araç tanımlarının gönderilmesini etkinleştirir veya devre dışı bırakır. `UAGENT_USE_TOOL` ayarını geçersiz kılar.

### `--computer-use` / `--no-computer-use`

Bilgisayar Kullanımını etkinleştirir veya devre dışı bırakır. `UAGENT_COMPUTER_USE` ayarını geçersiz kılar.

### `--no-frontend`

HTML şablonları veya statik ön uç dosyaları olmadan yalnızca API'yi çalıştırır.

### `--embedded`

Oturum deposunu devre dışı bırakır ve araç yönetim araçlarını (`tool_catalog`, `tool_load`, `unload_tool`) gizler.

______________________________________________________________________

## A2A sunucu seçenekleri (`uaga`)

### `--host <address>`

A2A HTTP sunucusu için bağlanma adresi (varsayılan: `0.0.0.0`, `UAGENT_A2A_HOST` ile geçersiz kılınabilir).

### `--port <sayı>`

A2A HTTP sunucusu için bağlantı noktası numarası (varsayılan: `8765`, `UAGENT_A2A_PORT` ile değiştirilebilir).

### `--reload`

Kod değişikliklerinde anında yeniden yüklemeyi etkinleştirir (varsayılan: kapalı, `UAGENT_A2A_RELOAD` ile değiştirilebilir).

```
uaga --host 127.0.0.1 --port 8080 --reload
```

### `--tool-genre-mask <int>`

Yukarıda açıklanan bit maskesini kullanarak araç türlerini seçin. Belirtildiğinde, etkileşimli tür sorusu atlanır.

### `--use-tool` / `--no-use-tool`

LLM'e araç tanımlarının gönderilmesini etkinleştirir veya devre dışı bırakır. `UAGENT_USE_TOOL` değerini geçersiz kılar.

### `--computer-use` / `--no-computer-use`

Bilgisayar Kullanımını etkinleştirir veya devre dışı bırakır. `UAGENT_COMPUTER_USE` değişkenini geçersiz kılar.

### `--embedded`

Oturum deposunu devre dışı bırakır ve araç yönetim araçlarını (`tool_catalog`, `tool_load`, `unload_tool`) gizler.

______________________________________________________________________

## İlgili ortam değişkenleri

| Değişken | Açıklama |
|---|---|
| `UAGENT_PROVIDER` | LLM sağlayıcı adı (başlangıçta gereklidir) |
| `UAGENT_*_API_KEY` | Seçilen sağlayıcı için API anahtarı |
| `UAGENT_WORKDIR` | Varsayılan çalışma dizini |
| `UAGENT_WEB_HOST` | Web sunucusu bağlanma adresi (varsayılan: `127.0.0.1`) |
| `UAGENT_A2A_HOST` | A2A sunucu bağlanma adresi (varsayılan: `0.0.0.0`) |
| `UAGENT_A2A_PORT` | A2A sunucu bağlantı noktası (varsayılan: `8765`) |
| `UAGENT_A2A_RELOAD` | Varsayılan olarak A2A anında yeniden yüklemeyi etkinleştir |
| `UAGENT_USE_TOOL` | `0`, `false`, `no` veya `off` olarak ayarlandığında araçları devre dışı bırak |
| `UAGENT_COMPUTER_USE` | Bilgisayar Kullanımını varsayılan olarak etkinleştir veya devre dışı bırak |
| `UAGENT_SESSION_STORE` | Oturum deposunu etkinleştirin veya devre dışı bırakın; Gömülü modda `0` zorunludur |
| `UAGENT_PLUGIN_DIRS` | Ek eklenti arama dizinleri |
| `UAGENT_AUTO_SENTINEL` | `1` olarak ayarlandığında tekli LLM otomatik pilot sentinel modunu etkinleştir |
| `UAGENT_CONSECUTIVE_TOOL_CALL_LIMIT` | Maksimum ardışık yeni araç çağrısı sayısı (varsayılan: `100`) |
| `UAGENT_MAX_TOOL_ROUNDS` | Kullanıcı işlemi başına maksimum LLM/araç turu sayısı (varsayılan: `200`) |
| `UAGENT_SHRINK_CNT` | Mesajlarda isteğe bağlı otomatik küçültme eşiği (`0`/ayarlanmamış = devre dışı) |
| `UAGENT_SHRINK_KEEP_LAST` | Küçültme işleminden sonra saklanacak mesaj sayısı (varsayılan: `20`) |
| `UAGENT_LANG` | Arayüz dili (`ja`, `en`, vb.) |

Ortam değişkenlerinin tam listesi için bkz. [ENVIRONMENT.md](ENVIRONMENT.md).

______________________________________________________________________

## Örnekler

### OpenAI ile minimal başlangıç

```
set UAGENT_PROVIDER=openai
set UAGENT_OPENAI_API_KEY=sk-...
uag
```

### Yalnızca temel araçları içeren yerel Ollama

```
set UAGENT_PROVIDER=ollama
set UAGENT_OLLAMA_MODEL=qwen2.5:7b
uag --tool-genre-mask 1
```

### Tüm arayüzlerde web sunucusu

```
set UAGENT_WEB_HOST=0.0.0.0
uagw
```

veya

```
uagw --host 0.0.0.0
```

### Özel bağlantı noktasına sahip localhost üzerinde A2A sunucusu

```
uaga --host 127.0.0.1 --port 8080
```

### Küçük bir model için araçları devre dışı bırak

```
uag --no-use-tool --tool-genre-mask 1
```

### Etkileşimsiz dosya işleme

```
uag --non-interactive README.md
```
