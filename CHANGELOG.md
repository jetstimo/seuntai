# Changelog

## 2.3.0 – pengenalan kolom yang lebih pintar

- Kolom tanggal pembuatan dan kolom produk/LOB dikenali walau namanya salah ketik satu huruf (CRETEDATE, PRODCUT) atau
  ditulis lain (CREATE_DT, TGL_DIBUAT, LOB_TYPE); isi kolom tanggal tetap harus >= 80 % terbaca tanggal.
- Bila nama kolom produk tidak dikenal sama sekali, dipakai kolom teks yang isinya memuat nilai produk yang dicari (mis.
  FTTT) - dari ISI, bukan nama.
- Nilai produk dicocokkan tanpa peduli huruf besar/kecil, spasi dan tanda baca (fttt, FTT-T = FTTT).
- Kolom tanggal ubah/hapus tetap tidak pernah dipakai. Layer dengan nama kolom biasa dan nilai produk yang ditulis seragam: hasil tidak berubah.

## 2.2.1 – rilis stabil (bukan experimental lagi)

- `experimental=False`: Seuntai tampil di Plugin Manager QGIS tanpa harus mencentang "Show also experimental plugins".
- Tidak ada perubahan algoritma maupun hasil; rilis tetap ditandatangani kunci resmi 92C4-D078-D1FC-1C5B.

## 2.2.0 – peta dasar citra satelit yang tajam dan cepat
- Saat hasil Seuntai dimuat, satu layer citra satelit Esri World Imagery dipasang di dasar daftar layer (dipakai bersama
  Seranta, tidak pernah dobel). Pilihan Satelit / Peta jalan / Tanpa: Vector → Seuntai → **Base Map...**
- Tajam & tanpa tulisan "Map data not yet available": zoom asli citra ditanyakan ke layanan `tilemap` Esri sekali per
  wilayah (di latar belakang, QGIS tidak menunggu); di atas zoom asli ubin diperbesar dengan interpolasi kubik.
- Cepat: hanya ubin yang tampil yang diunduh; cache jaringan QGIS minimal 1 GB.
- Laporan HTML: pilihan peta dasar (citra satelit bawaan bila online, peta jalan, tanpa) dengan deteksi zoom asli yang sama.
- Tidak ada perubahan aturan atau hasil.

## 2.1.0 – lisensi GPL v3 + pasal 7, rilis bertanda tangan
- Atas persetujuan kedua pencipta (Joseph Edward Timothy Siahaan dan Sidah Fahira), lisensi menjadi GPL-3.0-or-later
  dengan syarat tambahan pasal 7: nama kedua pencipta wajib dipertahankan, versi modifikasi wajib berganti nama dan
  ditandai, tidak boleh mengaku sebagai pembuat; merek Seuntai tidak dilisensikan. Versi s.d. 2.0.1 tetap GPL-2.0-or-later.
- Rilis resmi ditandatangani digital (Ed25519, `RILIS.json`) dengan kunci rilis yang sama dengan Seranta (sidik
  `92C4-D078-D1FC-1C5B`). Kaki laporan, ringkasan folder dan dialog About mencetak ASLI / DIMODIFIKASI / TIDAK RESMI beserta sidik kunci.
- Pengaman berlapis: cek silang sidik kunci di metadata.txt, NOTICE.md dan README.md; About → *Verify online* mencocokkan
  salinan dengan `RILIS_RESMI.json` di GitHub; pemeriksa independen `scripts/rilis_resmi.py`.
- Tidak ada perubahan aturan atau hasil.

## 2.0.1 – lulus pemeriksaan plugins.qgis.org
- Kesalahan yang sengaja diabaikan (fitur QGIS opsional, berkas terkunci) kini dicatat ke panel Log Messages QGIS
  (tab Seuntai) melalui `_log.py`, bukan diam-diam; pindaian keamanan Bandit lulus.
- Enum Qt6 `QNetworkRequest.KnownHeaders`; izin berkas 644; gaya kode (flake8 E731).
- Tidak ada perubahan aturan atau hasil (uji inti tetap identik).

## 2.0.0 – satu klik, satu jalan satu garis
- Menu, form dan pesan berbahasa Inggris; laporan tetap berbahasa Indonesia. Jendela baru **Consolidate Lines**: pilih
  layer garis, centang nilai produk/LOB yang ada di data, tekan Run. Setiap alat cukup satu isian; pengaturan lain di
  Advanced.
- Lebar koridor bawaan 15 m (toleransi 7,5 m = separuh RUMIJA minimum jalan sedang, PP 34/2006 Pasal 40); pilihan
  5 / 11 / 15 / 25 m di jendela Consolidate Lines.
- **Cocok ke jalan (OpenStreetMap)**, aktif bawaan: kabel yang digambar di kiri dan kanan jalan yang sama menjadi satu
  garis. Setiap titik kabel dicocokkan ke ruas jalan terdekat (batas per kelas jalan 5–22 m, beda arah ≤ 30°);
  trotoar terpisah diabaikan, dua lajur jalan berpemisah dihitung satu jalan, ruas yang bersambung lurus di
  persimpangan dihitung satu jalan; tidak ada penyambung melintang jalan (kecuali cabang yang memang menyeberang).
- Data jalan ringan dan otomatis: hanya petak jalan 0,1° di sekitar garis yang diunduh (satu kota beberapa MB),
  disimpan 90 hari; area kecil bisa memakai layanan langsung OpenStreetMap; unduhan satu pulau tidak pernah dijalankan
  diam-diam; tanpa internet hanya koridor yang dipakai dengan peringatan. Semua sumber data jalan memberi hasil
  identik (seri jarak diputus menurut geometri ruas). Geometri jalan tidak ditulis ke hasil; atribusi
  © OpenStreetMap contributors (ODbL).
- Layer tanpa kolom tanggal pembuatan tetap diproses dengan peringatan: garis terpanjang dipakai per koridor, hasil
  ditandai `su_dasar = PANJANG` dan `_TANPA_TANGGAL`; tanggal mustahil (#N/A, 1899/1900, masa depan) dianggap kosong.
- Laporan HTML interaktif baru: kesimpulan bahasa sederhana dan daftar "siap dipakai?", peta Sebelum / Sesudah /
  Bandingkan, animasi cara kerja, cerita setiap garis, grafik umur jaringan, daftar celah tersimpan di browser, ekspor
  CSV, FAQ dan glosarium.
- Diuji: Jawa Barat 81.730 garis; QGIS 3.40.14 potongan Bandung (2.630 garis, cache kosong 33 detik termasuk unduhan
  4 MB) dan Bogor: garis ganda di jalan yang sama turun 96%, 100% jalur masukan tetap terwakili dalam 45 m.
- Handbook bawaan dihapus; deskripsi plugin dipersingkat; changelog di metadata hanya versi terbaru.

## 1.4.0 – satu folder, semua data
- Alat **Seuntai Otomatis**: pilih folder (atau folder pengguna / semua drive), Run. Setiap data garis (Shapefile,
  GeoPackage, GeoJSON, KML, GML, FlatGeobuf) ditemukan, kolom tanggal, produk/LOB dan nama kabel dikenali otomatis,
  lalu diproses dengan aturan yang sama.
- Data yang tidak cocok dilewati dengan alasan dan cara memperbaikinya; satu data gagal tidak menghentikan yang lain.
  Hasil: satu folder per data + `Ringkasan_Seuntai.html`, CSV untuk Excel dan `BACA_SAYA.txt`.
- Diuji di QGIS 3.40: 15 data, 10 diproses, 5 dilewati dengan alasan tepat, 0 gagal; hasil identik dengan proses satu
  per satu.

## 1.3.0 – stabil di wilayah mana pun
- Garis dikelompokkan menjadi kelompok ruang yang saling lepas; tiap kelompok dihitung di zona UTM pusatnya sendiri,
  sehingga hasil sama apa pun luas wilayah dan CRS layer.
- Pemutus seri tidak bergantung urutan fitur atau FID; indeks ruang lebih hemat (memori Bangka Belitung 590 → 270 MB).
- Diuji: CRS 4326/3395/32748, urutan acak, pulau dipisah, salinan di zona UTM 46 dan 54 → 0 perbedaan.

## 1.2.0 – kabel tunggal
- Keluaran utama **Kabel tunggal**: satu fitur per garis terpilih dengan geometri dan seluruh atribut aslinya + kolom
  status `su_`; ekspor Shapefile opsional.
- Potongan yang dipangkas tidak lagi digeser ke garis tertua; garis 2,5–5 m di samping garis terpilih (pita drift)
  dibuang sebagai koridor yang sama. Bangka Belitung: tumpukan sejajar 52 km → 0.

## 1.1.0 – uji lapangan pertama
- Jalur unik selalu dipertahankan (kelengkapan 99,46% → 99,99%); ekor pendek dan penyambung tidak dibuang.
- Penyambungan celah segaris dan berkabel sama sampai 10 m (Kruskal); untai < 25 m ditandai FRAGMEN; UTM otomatis
  untuk CRS berdistorsi besar; profil jarak antar-garis dengan titik lutut (Kneedle) di laporan.

## 1.0.0 – rilis pertama
- Alat Konsolidasi Strand dan Periksa Koridor Ganda; pemilihan koridor dengan buffer dan prioritas tanggal tertua;
  noding dan line merge; deteksi celah; layer keputusan, gaya otomatis ramah buta warna; laporan HTML luring.
