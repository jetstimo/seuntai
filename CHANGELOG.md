# Changelog

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
