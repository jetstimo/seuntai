# Seuntai™ – Strand Consolidator · Pemberitahuan kepengarangan / Authorship notice

**Pencipta dan pemegang hak cipta / Authors and copyright holders:** Joseph Edward Timothy Siahaan dan Sidah Fahira (2026).
Lisensi / Licence: GNU GPL v3 atau lebih baru, **dengan syarat tambahan pasal 7** (lihat [LICENSE](LICENSE)), sejak
versi 2.1.0 atas persetujuan kedua pencipta. Versi sampai 2.0.1: GPL-2.0-or-later.

## Rilis resmi / Official releases
- QGIS Plugin Repository: *Seuntai - Strand Consolidator* (plugins.qgis.org), diunggah oleh pencipta.
- Kode sumber: https://github.com/jetstimo/seuntai
- Setiap rilis resmi memuat `RILIS.json` yang **ditandatangani secara digital** (Ed25519) dengan kunci rilis pencipta,
  dipegang Joseph Edward Timothy Siahaan. Plugin memeriksa tanda tangan itu sendiri; hasilnya tercetak di kaki setiap
  laporan (`Integritas: ASLI - rilis resmi ...`), di ringkasan folder dan di dialog *About*.
- **Sidik kunci rilis resmi / official release key fingerprint: `92C4-D078-D1FC-1C5B`** (sama dengan Seranta). Rilis yang tampil
  dengan sidik kunci lain BUKAN rilis resmi Seuntai, apa pun nama pembuat yang tertulis.

| Status | Arti |
|---|---|
| ASLI – rilis resmi … (kunci 92C4-D078-D1FC-1C5B) | Paket resmi, tidak ada berkas yang diubah |
| DIMODIFIKASI dari rilis resmi … | Ada berkas yang diubah/ditambah setelah rilis – bukan rilis resmi |
| TIDAK RESMI … kunci resmi 92C4-D078-D1FC-1C5B | Tanda tangan dibuat ulang atau kunci diganti |
| salinan pengembangan | Tidak ada tanda tangan rilis |

## Memeriksa keaslian / Verifying a copy
1. **About** di QGIS: status harus `ASLI … (kunci 92C4-D078-D1FC-1C5B)`.
2. **Verify online** di About: mencocokkan isi salinan dengan daftar rilis resmi `RILIS_RESMI.json` di GitHub.
3. Pemeriksa independen: `python rilis_resmi.py cek seuntai.<versi>.zip` (membawa kunci resmi sendiri, tidak menjalankan
   kode dari paket yang diperiksa). Hasil: ASLI / DIMODIFIKASI / PALSU (kunci diganti) / TIDAK RESMI.

## Memodifikasi / Modifying
Boleh, sesuai GPL v3. Syaratnya (LICENSE, pasal 7): pertahankan nama dan hak cipta kedua pencipta (di kode, metadata,
dialog About dan laporan), beri nama dan logo lain, tandai sebagai modifikasi ("Berbasis Seuntai oleh Joseph Edward
Timothy Siahaan dan Sidah Fahira, dimodifikasi oleh …, tanggal …"), dan jangan mengaku sebagai pembuat atau pemilik.

## Bukti kepengarangan / Evidence of authorship
Riwayat commit di GitHub, unggahan di QGIS Plugin Repository atas nama pencipta, kunci tanda tangan rilis, daftar rilis
resmi bertanggal (`RILIS_RESMI.json`) dan arsip rilis (`seuntai.<versi>.zip` + SHA-256).
