# Pemampatan konteks dan konteks model terhad

uag menggunakan beberapa lapisan untuk memastikan konteks model aktif kekal terhad. Matlamatnya adalah untuk mengurangkan token input yang tidak perlu tanpa membuang fail, keputusan alat, atau data sesi yang mungkin masih diperlukan oleh pengguna.

Dokumen ini menerangkan pelaksanaan semasa. Ia juga membezakan tingkah laku deterministik daripada tingkah laku khusus penyedia atau dibantu LLM.

## 1. Permukaan alat dinamik

Tidak semua definisi alat perlu dihantar ke model pada setiap giliran.

- `tool_catalog` mencari kebolehan yang tersedia.
- `tool_load` hanya mengaktifkan alat yang diperlukan untuk tugas semasa.
- `tool_catalog`, `tool_load`, dan `unload_tool` kekal tersedia sebagai alat pengurusan.
- Aliran Responses API yang serasi GPT-5.4 boleh menggunakan Tool Search asli di sisi pelayan.
- Mod Tool Search warisan menyempitkan spesifikasi alat dengan `tool_catalog` di pihak klien.

Ini mengurangkan token input yang digunakan oleh skema alat, terutamanya dalam pemasangan dengan banyak alat.

## 2. Keputusan alat tekstual yang besar menjadi Artifacts

Apabila keputusan alat tekstual melebihi ambang Artifact, uag menyimpan keputusan lengkap sebagai Artifact dan menghantar rujukan terhad serta pratonton kepada model, bukannya teks penuh.

Had lalai adalah:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Wakil yang boleh dilihat oleh model mengandungi nama alat, panjang asal, rujukan `artifact://`, laluan penyimpanan, dan pratonton terhad. Keputusan penuh kekal tersedia melalui storan Artifact. Ambang boleh diubah dengan `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Nilai `0` menyahaktifkan promosi Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` mengawal dasar keputusan terhad biasa; `0` menyahaktifkan had biasa itu.

## 3. Pengambilan Artifact Terhad

Alat infrastruktur `artifact_read` hanya mengambil bahagian yang diminta daripada Artifact:

- `start_line` memilih baris pertama.
- `max_lines` dihadkan kepada 500.
- `max_chars` dihadkan kepada 50,000 aksara.
- Kedua-dua ID Artifact dan URI `artifact://` boleh digunakan.

Ini membolehkan pemeriksaan julat kecil yang relevan, bukannya menyuntik semula keseluruhan fail atau hasil arahan ke dalam giliran model seterusnya.

Artifak baru disimpan di bawah:

```text
~/.uag/artifacts/
```

Jejak Artifact sedia ada kekal boleh dibaca untuk keserasian.

## 4. Pengasingan muatan binari

Data binari dalam baris tidak dihantar sebagai hasil alat teks kepada pusingan model seterusnya. Medan berbentuk Base64 digantikan dengan penanda ringkas seperti:

```text
[muatan binari diabaikan daripada konteks LLM]
```

Antaramuka pengguna dan klien jauh masih boleh menerima lampiran dalam memori, dan fail yang disimpan kekal tersedia melalui laluan atau rujukan Artifact mereka. Ini menghalang imej, audio, tangkapan skrin, dan muatan binari lain daripada membengkakkan konteks model teks.

Kelas muatan binari yang sama disanitasi sebelum pengekalan SQLite dan JSONL, menghalangnya daripada muncul semula sebagai muatan besar selepas sesi dimuat semula.

## 5. Pemampatan sejarah automatik

uag boleh memampatkan sejarah perbualan lama apabila bilangan mesej atau anggaran bilangan token mencapai had yang telah ditetapkan.

Dasar pemampatan menggunakan:

- bilangan mesej bukan sistem;
- tetingkap konteks terurai model apabila tersedia;
- `UAGENT_SHRINK_KEEP_LAST` (20 secara lalai);
- `UAGENT_SHRINK_MAX_TOKENS` atau keutamaan khusus model;
- `UAGENT_SHRINK_CNT`; dan
- `UAGENT_SHRINK_RATIO` (0.5 secara lalai apabila tetingkap konteks diketahui).

Had khusus model boleh disertakan sebagai:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Ringkasan sebelumnya tidak dihasil semula pada setiap giliran. Histeresis memerlukan sejarah baru yang mencukupi untuk terkumpul, atau lebihan bajet token lain, sebelum pemampatan dijalankan semula.

## 6. Ringkasan sejarah dibantu LLM

Apabila pemampatan automatik menggunakan LLM, mesej pengguna, pembantu, dan alat yang lebih lama diringkaskan ke dalam mesej sistem bergolek manakala hujung terkini dikekalkan.

Sejarah panjang boleh diringkaskan dalam ketulan. Kawalan berkaitan adalah:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Ringkasan dilipat ke hadapan dan bukannya mencipta urutan mesej ringkasan tanpa had. Ini adalah operasi yang dibantu oleh LLM dan mungkin memerlukan permintaan penyedia tambahan.

## 7. Pemampatan fallback deterministik

Jika ringkasan LLM tidak tersedia, uag boleh mengekalkan mesej sistem terkemuka dan hanya mesej terkini. Batas panggilan alat dibaiki supaya sejarah yang terhasil tidak bermula atau berakhir dengan panggilan alat yang terasing.

Pemuat dan penyahcemar juga membuang entri yang tidak relevan dengan model atau tidak sah, termasuk mesej hanya UI, mesej kawalan dalaman, baris log yang rosak, peranan yang tidak disokong, keputusan alat terasing, dan blok panggilan alat yang tidak lengkap.

Apabila sesi dimuat semula, prompt sistem semasa dipulihkan dan hanya mesej sistem yang disuntik dan relevan, seperti konteks kemahiran atau hook, dikekalkan.

## 8. Pemulihan tumpahan konteks

Jika penyedia melaporkan bahawa tetingkap konteks telah melebihi, uag mengenal pasti mesej sejarah terkini yang besar dan menggulung balik mesej tersebut serta sejarah berikutnya sebelum mencuba semula. Ini adalah langkah fallback reaktif, bukan pengganti untuk perancangan biasa.

## 9. Sambungan dan pemampatan pihak penyedia

Di mana disokong, Responses API menggunakan `previous_response_id` untuk meneruskan rantaian respons tanpa menghantar semula keseluruhan sejarah respons yang diuruskan oleh penyedia dari klien.Aliran Responses API juga menghantar konfigurasi pemampatan pihak penyedia menggunakan ambang pengecutan tempatan yang sama. Perilaku sebenar bergantung pada penyedia; dasar Artifact tempatan dan sejarah kekal sebagai langkah keselamatan neutral penyedia. Kecekapan pengiraan token

Pengiraan token yang digunakan untuk keputusan pemampatan disimpan dalam cache dan dikemas kini secara berperingkat apabila hanya mesej baru yang ditambah. Ini tidak secara langsung mengurangkan konteks model, tetapi ia mengurangkan kos CPU dan latensi dalam membuat keputusan bila pemampatan diperlukan.

## Apa yang belum menjadi lapisan bersepadu sepenuhnya

Pelaksanaan semasa belum menyediakan semua perkara berikut sebagai satu pengurus neutral penyedia:

- satu `ContextManager` dan `ContextBudget` bersepadu;
- satu `ToolResultRecord` dengan metadata kepentingan dan pengusiran;
- ringkasan semantik yang tidak memerlukan LLM;
- pemulihan dan suntikan semula automatik Artifacts yang relevan;
- Pengurus Keputusan pusat yang menjamin penukaran Artifact untuk setiap alat penghasil binari; atau
- pengusiran yang sedar keutamaan merentasi semua kategori sistem, sejarah, skema alat, dan keputusan.

Ringkasnya, uag pada masa ini menggabungkan pemotongan deterministik, rujukan Artifact, pengasingan binari, pemilihan alat dinamik, ringkasan sejarah, sambungan penyedia, dan pemulihan limpahan. Peta jalan reka bentuk untuk lapisan konteks bersatu didokumenkan dalam [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
