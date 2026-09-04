# Bağlam sıkıştırması ve sınırlı model bağlamı

uag, etkin model bağlamını sınırlı tutmak için birkaç katman kullanır. Amaç, kullanıcının hâlâ ihtiyaç duyabileceği dosyaları, takım sonuçlarını veya oturum verilerini kaldırmadan gereksiz girdi belirteçlerini azaltmaktır.

Bu belge, mevcut uygulamayı açıklamaktadır. Ayrıca, deterministik davranışı, sağlayıcıya özgü veya LLM destekli davranıştan ayırmaktadır.

## 1. Dinamik araç yüzeyi

Her turda her araç tanımının modele gönderilmesi gerekmez.

- `tool_catalog`, kullanılabilir yetenekleri arar.
- `tool_load`, yalnızca mevcut görev için gerekli araçları etkinleştirir.
- `tool_catalog`, `tool_load` ve `unload_tool`, yönetim araçları olarak kullanılmaya devam eder.
- GPT-5.4 uyumlu Responses API akışları, yerel sunucu tarafı Tool Search'i kullanabilir.
- Eski Tool Search modu, istemci tarafında `tool_catalog` ile araç özelliklerini daraltır.

Bu, özellikle çok sayıda araç içeren kurulumlarda araç şemaları tarafından kullanılan girdi belirteçlerini azaltır.

## 2. Büyük metin tabanlı araç sonuçları Artifact'lara dönüşür

Bir metin tabanlı araç sonucu Artifact eşiğini aştığında, uag tam sonucu bir Artifact olarak depolar ve modele tam metin yerine sınırlı bir referans ve önizleme gönderir.

Varsayılan sınırlar şunlardır:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Modelin görebileceği temsil, araç adını, orijinal uzunluğu, bir `artifact://` referansını, depolama yolunu ve sınırlandırılmış bir önizlemeyi içerir. Tam sonuç, Artifact deposu aracılığıyla erişilebilir durumda kalır.

Eşik değeri `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS` ile değiştirilebilir. `0` değeri, Artifact yükseltmesini devre dışı bırakır. `UAGENT_TOOL_RESULT_MAX_CHARS`, olağan sınırlı sonuç politikasını kontrol eder; `0` değeri bu olağan sınırı devre dışı bırakır.

## 3. Sınırlı Artifact alma

`artifact_read` altyapı aracı, bir Artifact'nin yalnızca istenen kısmını alır:

- `start_line`, ilk satırı seçer.
- `max_lines` değeri 500 ile sınırlıdır.
- `max_chars` değeri 50.000 karakter ile sınırlıdır.
- Hem bir Artifact kimliği hem de bir `artifact://` URI'si kullanılabilir.

Bu, bir dosyanın tamamını veya komut sonucunu bir sonraki model döngüsüne yeniden enjekte etmek yerine, ilgili küçük bir aralığı incelemek mümkün kılar.

Yeni Artefaktlar aşağıda depolanır:

```text
~/.uag/artifacts/
```

Mevcut eski Artifact yolları, uyumluluk amacıyla okunabilir kalır.

## 4. İkili yük izolasyonu

Satır içi ikili veriler, bir sonraki model turuna metin biçiminde bir araç sonucu olarak gönderilmez. Base64 biçimli alanlar, aşağıdaki gibi kısa bir işaretçiyle değiştirilir:

```text
[LLM bağlamından çıkarılan ikili yük]
```

Kullanıcı arayüzü ve uzak istemciler hâlâ bellek içi ekleri alabilir ve kaydedilmiş dosyalar, yollarından veya Artifact referanslarından erişilebilir durumda kalır. Bu, resimlerin, seslerin, ekran görüntülerinin ve diğer ikili yüklerin metin model bağlamını şişirmesini önler.

Aynı sınıftaki ikili yükler, SQLite ve JSONL kalıcılığı öncesinde temizlenir; böylece oturumun yeniden yüklenmesinden sonra büyük bir yük olarak geri dönmesi engellenir.

## 5. Otomatik geçmiş sıkıştırma

uag, mesaj sayısı veya tahmini token sayısı yapılandırılan sınıra ulaştığında eski konuşma geçmişini sıkıştırabilir.

Sıkıştırma politikası şunları kullanır:

- sistem dışı mesaj sayısı;
- varsa, modelin çözümlenmiş bağlam penceresi;
- `UAGENT_SHRINK_KEEP_LAST` (varsayılan olarak 20);
- `UAGENT_SHRINK_MAX_TOKENS` veya modele özgü bir geçersiz kılma;
- `UAGENT_SHRINK_CNT`; ve
- `UAGENT_SHRINK_RATIO` (bağlam penceresi bilindiğinde varsayılan olarak 0,5).

Modele özgü bir sınır şu şekilde sağlanabilir:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Önceki bir özet her turda yeniden oluşturulmaz. Sıkıştırma işleminin tekrar çalışabilmesi için, yeterli miktarda yeni geçmiş verisinin birikmesi veya başka bir token bütçesi taşması gerekir.

## 6. LLM destekli geçmiş özetleri

Otomatik sıkıştırma LLM’yi kullandığında, eski kullanıcı, asistan ve araç mesajları dönen bir sistem mesajında özetlenirken, en son kısım korunur.

Uzun geçmişler parçalar halinde özetlenebilir. İlgili denetimler şunlardır:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Özet, sınırsız bir özet mesaj dizisi oluşturmak yerine ileriye doğru katlanır. Bu, LLM destekli bir işlemdir ve ek sağlayıcı istekleri gerektirebilir.

## 7. Deterministik yedek sıkıştırma

Bir LLM özeti kullanılamıyorsa, uag baştaki sistem mesajlarını ve yalnızca en son mesajları tutabilir. Sonuçta ortaya çıkan geçmişin, yetim kalmış bir araç çağrısıyla başlamaması veya bitmemesi için araç çağrısı sınırları onarılır.

Yükleyici ve temizleyici ayrıca, yalnızca kullanıcı arayüzüne ait mesajlar, dahili kontrol mesajları, bozuk günlük satırları, desteklenmeyen roller, yetim kalmış araç sonuçları ve eksik araç çağrısı blokları dahil olmak üzere, modelle ilgisiz veya geçersiz girdileri de kaldırır.

Bir oturum yeniden yüklendiğinde, geçerli sistem istemini geri yükler ve yalnızca beceri veya kanca bağlamı gibi ilgili enjekte edilmiş sistem mesajları saklanır.

## 8. Bağlam taşması kurtarma

Bir sağlayıcı, bağlam penceresinin aşıldığını bildirirse, uag yakın zamandaki büyük bir geçmiş mesajını belirler ve yeniden denemeden önce o mesajı ve onu takip eden geçmişi geri alır. Bu, normal bütçelemenin yerine geçen bir çözüm değil, reaktif bir yedekleme yöntemidir.

## 9. Sağlayıcı tarafında devam ettirme ve sıkıştırma

Desteklendiği durumlarda, Responses API, `previous_response_id` kullanarak, istemciden sağlayıcı tarafından yönetilen yanıt geçmişinin tamamını yeniden göndermeden bir yanıt zincirini devam ettirir.

Responses API akışları ayrıca aynı yerel küçültme eşiğini kullanarak sağlayıcı tarafında sıkıştırma yapılandırması gönderir. Kesin davranış sağlayıcıya bağlıdır; yerel Artifact ve geçmiş politikaları, sağlayıcıdan bağımsız koruma önlemleri olarak kalır.

## 10. Jeton sayma verimliliği

Sıkıştırma kararları için kullanılan jeton sayıları önbelleğe alınır ve yalnızca yeni mesajlar eklendiğinde artımlı olarak güncellenir. Bu, model bağlamını doğrudan azaltmaz, ancak sıkıştırmanın ne zaman gerekli olduğuna karar vermenin CPU maliyetini ve gecikmesini azaltır.

## Henüz tam olarak birleştirilmiş bir katman olmayan unsurlar

Mevcut uygulama, aşağıdakilerin tümünü tek bir sağlayıcıdan bağımsız yönetici olarak henüz sunmamaktadır:

- birleştirilmiş `ContextManager` ve `ContextBudget`;
- önem ve tahliye meta verilerine sahip bir `ToolResultRecord`;
- `LLM` gerektirmeyen anlamsal özetler;
- ilgili Artefaktların otomatik olarak alınması ve yeniden enjeksiyonu;
- her ikili dosya üreten araç için `Artifact` dönüşümünü garanti eden merkezi bir Sonuç Yöneticisi; veya
- tüm sistem, geçmiş, araç şeması ve sonuç kategorileri genelinde önceliği dikkate alan kaldırma.

Kısacası, uag şu anda deterministik kesme, Artifact referansları, ikili izolasyon, dinamik araç seçimi, geçmiş özetleri, sağlayıcı devamlılığı ve taşma kurtarmayı bir araya getirmektedir. Birleşik bir bağlam katmanı için tasarım yol haritası [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md) belgesinde yer almaktadır.
