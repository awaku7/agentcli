# Kompresi konteks dan konteks model yang dibatasi

uag menggunakan beberapa lapisan untuk menjaga agar konteks model yang aktif tetap terbatas. Tujuannya adalah untuk mengurangi token masukan yang tidak perlu tanpa menghapus berkas, hasil alat, atau data sesi yang mungkin masih dibutuhkan pengguna.

Dokumen ini menjelaskan implementasi saat ini. Dokumen ini juga membedakan perilaku deterministik dari perilaku yang bergantung pada penyedia atau yang dibantu oleh LLM.

## 1. Permukaan alat dinamis

Tidak semua definisi alat perlu dikirim ke model pada setiap giliran.

- `tool_catalog` mencari kemampuan yang tersedia.
- `tool_load` hanya mengaktifkan alat yang diperlukan untuk tugas saat ini.
- `tool_catalog`, `tool_load`, dan `unload_tool` tetap tersedia sebagai alat manajemen.
- Alur kerja Responses API yang kompatibel dengan GPT-5.4 dapat menggunakan Tool Search asli di sisi server.
- Mode Tool Search lama mempersempit spesifikasi alat dengan `tool_catalog` di sisi klien.

Hal ini mengurangi token masukan yang digunakan oleh skema alat, terutama pada instalasi dengan banyak alat.

## 2. Hasil alat berbasis teks yang besar menjadi Artefak

Ketika hasil alat berbasis teks melebihi ambang batas Artifact, uag menyimpan hasil lengkap sebagai Artifact dan mengirimkan referensi terbatas serta pratinjau kepada model, bukan teks lengkap.

Batas defaultnya adalah:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Representasi yang terlihat oleh model berisi nama alat, panjang asli, referensi `artifact://`, jalur penyimpanan, dan pratinjau yang dibatasi. Hasil lengkap tetap tersedia melalui penyimpanan Artifact.

Ambang batas dapat diubah dengan `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Nilai `0` menonaktifkan promosi Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` mengontrol kebijakan hasil terbatas biasa; `0` menonaktifkan batas biasa tersebut.

## 3. Pengambilan Artifact yang dibatasi

Alat infrastruktur `artifact_read` hanya mengambil bagian yang diminta dari sebuah Artifact:

- `start_line` memilih baris pertama.
- `max_lines` dibatasi hingga 500.
- `max_chars` dibatasi hingga 50.000 karakter.
- Baik ID `Artifact` maupun URI `artifact://` dapat digunakan.

Hal ini memungkinkan untuk memeriksa rentang kecil yang relevan, alih-alih memasukkan kembali seluruh file atau hasil perintah ke dalam giliran model berikutnya.

Artefak baru disimpan di bawah ini:

```text
~/.uag/artifacts/
```

Jalur Artifact warisan yang sudah ada tetap dapat dibaca demi kompatibilitas.

## 4. Isolasi muatan biner

Data biner inline tidak dikirim sebagai hasil alat teks ke giliran model berikutnya. Bidang berbentuk Base64 diganti dengan penanda singkat seperti:

```text
[muatan biner dihilangkan dari konteks LLM]
```

UI dan klien jarak jauh masih dapat menerima lampiran dalam memori, dan file yang disimpan tetap tersedia melalui jalur atau referensi Artifact-nya. Hal ini mencegah gambar, audio, tangkapan layar, dan muatan biner lainnya membengkakkan konteks model teks.

Kelas muatan biner yang sama disterilkan sebelum penyimpanan ke SQLite dan JSONL, sehingga mencegahnya muncul kembali sebagai muatan besar setelah sesi dimuat ulang.

## 5. Kompresi riwayat otomatis

uag dapat mengompres riwayat percakapan yang lebih lama ketika jumlah pesan atau perkiraan jumlah token mencapai batas yang telah dikonfigurasi.

Kebijakan kompresi ini menggunakan:

- jumlah pesan non-sistem;
- jendela konteks model yang telah diselesaikan jika tersedia;
- `UAGENT_SHRINK_KEEP_LAST` (20 secara default);
- `UAGENT_SHRINK_MAX_TOKENS` atau penggantian yang spesifik untuk model;
- `UAGENT_SHRINK_CNT`; dan
- `UAGENT_SHRINK_RATIO` (0,5 secara default jika jendela konteks diketahui).

Batas khusus model dapat diberikan sebagai:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Ringkasan sebelumnya tidak dibuat ulang pada setiap giliran. Histeresis memerlukan akumulasi riwayat baru yang cukup, atau kelebihan anggaran token lainnya, sebelum kompresi dijalankan kembali.

## 6. Ringkasan riwayat yang didukung LLM

Saat kompresi otomatis menggunakan LLM, pesan pengguna, asisten, dan alat yang lebih lama diringkas menjadi pesan sistem bergulir sementara bagian ekor terbaru tetap dipertahankan.

Riwayat yang panjang dapat diringkas dalam potongan-potongan. Kontrol yang relevan adalah:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Ringkasan tersebut digabungkan ke depan alih-alih menciptakan urutan pesan ringkasan yang tak terbatas. Ini adalah operasi yang dibantu oleh LLM dan mungkin memerlukan permintaan tambahan kepada penyedia.

## 7. Kompresi cadangan deterministik

Jika ringkasan LLM tidak tersedia, uag dapat mempertahankan pesan sistem awal dan hanya pesan-pesan terbaru. Batas-batas panggilan alat diperbaiki sehingga riwayat yang dihasilkan tidak dimulai atau diakhiri dengan panggilan alat yang terputus.

Pemuatan dan penyaring juga menghapus entri yang tidak relevan dengan model atau tidak valid, termasuk pesan khusus antarmuka pengguna, pesan kontrol internal, baris log yang rusak, peran yang tidak didukung, hasil alat yang terputus, dan blok panggilan alat yang tidak lengkap.

Saat sesi dimuat ulang, prompt sistem saat ini dipulihkan dan hanya pesan sistem yang disisipkan yang relevan, seperti konteks keterampilan atau hook, yang dipertahankan.

## 8. Pemulihan kelebihan konteks

Jika penyedia melaporkan bahwa jendela konteks terlampaui, uag mengidentifikasi pesan riwayat terbaru yang berukuran besar dan membatalkan pesan tersebut beserta riwayat berikutnya sebelum mencoba kembali. Ini adalah solusi cadangan reaktif, bukan pengganti untuk pengalokasian sumber daya normal.

## 9. Kelanjutan dan pemadatan di sisi penyedia

Jika didukung, Responses API menggunakan `previous_response_id` untuk melanjutkan rantai respons tanpa mengirim ulang seluruh riwayat respons yang dikelola penyedia dari klien.

Alur Responses API juga mengirimkan konfigurasi pemadatan di sisi penyedia menggunakan ambang batas penyusutan lokal yang sama. Perilaku pastinya bergantung pada penyedia; Artifact lokal dan kebijakan riwayat tetap menjadi pengaman yang netral terhadap penyedia.

## 10. Efisiensi penghitungan token

Jumlah token yang digunakan untuk keputusan kompresi disimpan dalam cache dan diperbarui secara bertahap hanya saat pesan baru ditambahkan. Hal ini tidak secara langsung mengurangi konteks model, tetapi mengurangi beban CPU dan latensi dalam menentukan kapan kompresi diperlukan.

## Apa yang belum menjadi lapisan terpadu yang lengkap

Implementasi saat ini belum menyediakan semua hal berikut sebagai satu pengelola yang netral terhadap penyedia:

- `ContextManager` dan `ContextBudget` yang terpadu;
- `ToolResultRecord` dengan metadata kepentingan dan pengusiran;
- ringkasan semantik yang tidak memerlukan `LLM`;
- pengambilan dan penyisipan ulang Artefak yang relevan secara otomatis;
- Manajer Hasil terpusat yang menjamin konversi `Artifact` untuk setiap alat yang menghasilkan biner; atau
- pengusiran yang mempertimbangkan prioritas di seluruh kategori sistem, riwayat, skema alat, dan hasil.

Singkatnya, uag saat ini menggabungkan pemotongan deterministik, referensi Artifact, isolasi biner, pemilihan alat dinamis, ringkasan riwayat, kelanjutan penyedia, dan pemulihan kelebihan beban. Peta jalan desain untuk lapisan konteks terpadu didokumentasikan dalam [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
