# -*- coding: utf-8 -*-
"""Seuntai - daftar sumber dan dasar setiap keputusan (dipakai laporan HTML dan DASAR_KEPUTUSAN.md).
Status: STANDAR = mengikuti standar/aturan resmi; LITERATUR = metode dari publikasi ilmiah/dokumentasi rujukan;
DESAIN = keputusan rekayasa yang diturunkan dari sumber dan diuji, dapat diubah pengguna.
Copyright (C) 2026 Joseph Edward Timothy Siahaan and Sidah Fahira. GPL-3.0-or-later with section 7 terms (see LICENSE)."""

SUMBER = [
    ("S1", "Goodchild, M. F. & Hunter, G. J. (1997). A simple positional accuracy measure for linear features. "
           "International Journal of Geographical Information Science 11(3), 299-306.",
     "https://doi.org/10.1080/136588197242419"),
    ("S2", "Lei, T. L. (2019). Geospatial Data Conflation. The Geographic Information Science & Technology Body of "
           "Knowledge (3rd Quarter 2019 Edition), J. P. Wilson (ed.). DOI 10.22224/gistbok/2019.3.5.",
     "https://gistbok.ucgis.org/node/100004813"),
    ("S3", "LocationTech JTS Topology Suite - kelas LineMerger (dipakai juga oleh GEOS/QGIS/PostGIS ST_LineMerge).",
     "https://locationtech.github.io/jts/javadoc/org/locationtech/jts/operation/linemerge/LineMerger.html"),
    ("S4", "QGIS Documentation - A Gentle Introduction to GIS, bab 7 Topology (snapping distance, undershoot, "
           "overshoot, dangles).", "https://docs.qgis.org/3.28/en/docs/gentle_gis_introduction/topology.html"),
    ("S5", "U.S. Government, GPS.gov - GPS Accuracy (ponsel ber-GPS umumnya akurat dalam radius 4,9 m di langit "
           "terbuka; memburuk dekat bangunan, jembatan, dan pohon).",
     "https://webarchive.library.unt.edu/web/20201218011422/https://www.gps.gov/systems/gps/performance/accuracy"),
    ("S6", "Peraturan Menteri PU No. 19/PRT/M/2011, Lampiran: Persyaratan Teknis Jalan - lebar jalur jalan kecil "
           "2 x 2,75 m, jalan sedang 2 x 3,50 m. Telah dicabut dan digantikan Permen PUPR No. 5 Tahun 2023; nilai "
           "dipakai sebagai acuan orde besaran, periksa tabel terbaru untuk keperluan formal.",
     "https://peraturan.bpk.go.id/Download/152623/PermenPU19-2011%20-%20Lamp.pdf"),
    ("S7", "Esri ArcGIS Pro - Remove Overlapping Centerlines (Location Referencing): bagian yang tumpang-tindih "
           "dihapus sehingga rute berbagi satu centerline; daftar garis yang dibuang ditulis ke berkas rincian.",
     "https://pro.arcgis.com/en/pro-app/2.9/tool-reference/location-referencing/remove-overlapping-centerlines.htm"),
    ("S8", "ISO 19157:2013 Geographic information - Data quality: elemen konsistensi logis (konsistensi topologis) "
           "dan kelengkapan (commission/kelebihan data). Rujukan antarmuka: GeoAPI TopologicalConsistency.",
     "https://www.geoapi.org/snapshot/javadoc/org.opengis.geoapi/org/opengis/metadata/quality/"
     "TopologicalConsistency.html"),
    ("S9", "ISO 8601 - Date and time format (tanggal ditulis YYYY-MM-DD).",
     "https://www.iso.org/iso-8601-date-and-time-format.html"),
    ("S10", "Ichihara, Y. G., Okabe, M., Iga, K., Tanaka, Y., Musha, K., Ito, K. (2008). Color universal design: "
            "the selection of four easily distinguishable colors for all color vision types. Proc. SPIE 6807.",
     "https://jfly.uni-koeln.de/color/ichihara_etal_2008.pdf"),
    ("S11", "W3C - Web Content Accessibility Guidelines (WCAG) 2.1, kriteria 1.4.3 Contrast (Minimum) 4,5:1.",
     "https://www.w3.org/TR/WCAG21/#contrast-minimum"),
    ("S12", "QGIS PyQGIS Developer Cookbook - Releasing your plugin (nama unik, metadata, ikon, Processing provider, "
            "dokumentasi dan data contoh, struktur ZIP).",
     "https://docs.qgis.org/3.34/en/docs/pyqgis_developer_cookbook/plugins/releasing.html"),
    ("S13", "Snyder, J. P. (1987). Map Projections - A Working Manual. USGS Professional Paper 1395 (proyeksi UTM, "
            "zona 6 derajat).", "https://pubs.usgs.gov/pp/1395/report.pdf"),
    ("S14", "Panduan Modul & Plugin QGIS: Attribute-Based Strand Consolidator - kebutuhan: "
            "filter PRODUCT = 'FTTT', prioritas CREATEDATE tertua, Dissolve + Line Merge menjadi 1 strand.", ""),
    ("S16", "Satopaa, V., Albrecht, J., Irwin, D., Raghavan, B. (2011). Finding a 'Kneedle' in a Haystack: "
            "Detecting Knee Points in System Behavior. IEEE ICDCS Workshops 2011.",
     "https://dblp.org/rec/conf/icdcsw/SatopaaAIR11.html"),
    ("S17", "Kruskal, J. B. (1956). On the shortest spanning subtree of a graph and the traveling salesman problem. "
            "Proceedings of the American Mathematical Society 7(1), 48-50.",
     "https://doi.org/10.1090/S0002-9939-1956-0078686-7"),
    ("S18", "Jarak antar tiang <= 50 m: Perwal Tangerang Selatan 3/2019 jo. 47/2019 Ps. 5J; Rancangan Permenkominfo "
            "2018 Pedoman Teknis Infrastruktur Bersama (acuan); tiang sudut > 30 derajat wajib tambat: Buku pedoman "
            "konstruksi jaringan distribusi TR (2010). Dirangkum di DASAR_ATURAN Seranta.", ""),
    ("S19", "Uji empiris Seuntai pada data FTTT Kepulauan Bangka Belitung (3.050 garis, 3.295 km, 52.357 ruas, "
            "EPSG:3395), 29 Oktober 2026 (v1.0-v1.2): distribusi jarak antar-garis, celah ujung bebas, kelengkapan, "
            "dan tumpukan tersisa di hasil. Rincian di DASAR_KEPUTUSAN.md.", ""),
    ("S20", "Haunert, J.-H. & Sester, M. (2008). Area collapse and road centerlines based on straight skeletons. "
            "GeoInformatica 12, 169-191. DOI 10.1007/s10707-007-0028-x.",
     "https://www1.pub.informatik.uni-wuerzburg.de/pub/haunert/pdf/HaunertSester2008.pdf"),
    ("S21", "Quach, T. BecaGIS (plugin QGIS, GPL): alat Skeleton/Medial Axis untuk POLIGON (titik rapat di tepi -> "
            "diagram Voronoi -> tepi di dalam poligon -> garis tengah) dan 'Merge lines in direction' (gabung garis "
            "yang ujungnya bertemu persis dan searah). Kode sumber ditinjau 29 Oktober 2026.",
     "https://github.com/opengeoshub/becagis"),
    ("S22", "Esri ArcGIS Pro - Collapse Dual Lines To Centerline: garis tengah dibuat baru; atribut garis asal tidak "
            "dibawa (hanya FID kiri/kanan).",
     "https://pro.arcgis.com/en/pro-app/3.3/tool-reference/cartography/collapse-dual-lines-to-centerline.htm"),
    ("S23", "GDAL - ESRI Shapefile driver: nama atribut maksimal 10 karakter; lebar kolom DBF maksimal 255 byte.",
     "https://gdal.org/en/stable/drivers/vector/shapefile.html"),
    ("S24", "Uji kestabilan Seuntai 1.3 dengan algoritma lengkap pada data Bangka Belitung (proyeksi uji: deret "
     "Kruger orde 6, Karney 2011): CRS layer EPSG:4326/3395/32748, urutan fitur diacak, Pulau Bangka dan Belitung "
     "diproses terpisah, serta data digabung dengan dua salinan di bujur -12 dan +36 derajat (zona 46 dan 54) -> "
     "0 perbedaan status dan panjang (> 1 cm) dari 2.496 kabel. Versi 1.2 pada uji gabungan yang sama: 10 kabel "
     "muncul/hilang dan 321 panjang berubah.", ""),
    ("S25", "Nielsen, J. (1994). 10 Usability Heuristics for User Interface Design (dirintis bersama R. Molich, "
     "CHI 1990): antara lain visibilitas status sistem, mencegah kesalahan, mengenali alih-alih mengingat, desain "
     "minimalis, serta membantu pengguna mengenali dan memulihkan kesalahan.",
     "https://www.nngroup.com/articles/ten-usability-heuristics/"),
    ("S26", "QGIS Documentation 3.40, 23.6 The batch processing interface: setiap algoritma Processing dapat dijalankan "
     "untuk banyak masukan; tiap baris tabel = satu eksekusi dengan parameter per kolom.",
     "https://docs.qgis.org/3.40/en/docs/user_manual/processing/batch.html"),
    ("S27", "Uji Seuntai Otomatis 1.4 di QGIS 3.40.14 (Windows) pada folder berisi 15 data garis: 7 Shapefile per "
     "kabupaten, GeoPackage dua layer (garis + titik), GeoJSON WGS84 berkolom Tgl_Dibuat/LOB, KML, serta data "
     "tanpa tanggal, hanya FTTH, kosong, rusak, tanpa .prj, dan salinan hasil Seuntai -> 10 diproses, 5 dilewati "
     "dengan alasan, 0 gagal, 87 detik. Hasil GeoPackage = hasil satu layer v1.3 (0 perbedaan dari 2.496 kabel); "
     "GeoJSON/KML WGS84 = Shapefile EPSG:3395 untuk wilayah yang sama.", ""),
    ("S28", "Peraturan Pemerintah No. 34 Tahun 2006 tentang Jalan, Pasal 39-40: ruang milik jalan (rumija) terdiri "
     "dari ruang manfaat jalan dan sejalur tanah tertentu di luarnya; lebar paling sedikit jalan bebas hambatan 30 m, "
     "jalan raya 25 m, jalan sedang 15 m, jalan kecil 11 m.", "https://pasal.id/peraturan/pp/pp-no-34-tahun-2006"),
    ("S29", "Walter, V. & Fritsch, D. (1999). Matching spatial data sets: a statistical approach. International "
     "Journal of Geographical Information Science 13(5), 445-473 (pencocokan ruas berbasis jarak, arah, dan panjang; "
     "sebagian besar pasangan cocok berbeda arah < 10-30 derajat).", "https://doi.org/10.1080/136588199241157"),
    ("S30", "Esri ArcGIS - How Merge Divided Roads works / Collapse Dual Lines To Centerline: pasangan garis sejajar "
     "di dua sisi satu jalan dijadikan satu, dengan jarak penggabungan sedikit di atas lebar pemisah.",
     "https://desktop.arcgis.com/en/arcmap/latest/tools/cartography-toolbox/how-merge-divided-roads-works.htm"),
    ("S31", "OpenStreetMap - Copyright and License / Legal FAQ: data (c) OpenStreetMap contributors, Open Database "
     "License (ODbL); wajib atribusi.", "https://www.openstreetmap.org/copyright"),
    ("S32", "Peraturan Menteri PU No. 20/PRT/M/2010 tentang Pedoman Pemanfaatan dan Penggunaan Bagian-Bagian Jalan, "
     "Pasal 12: utilitas di kawasan perkotaan ditempatkan di luar bahu jalan/trotoar atau di sisi terluar ruang milik "
     "jalan (tidak dibatasi satu sisi).", "https://pelayanan.jakarta.go.id/download/regulasi/peraturan-menteri-"
     "pekerjaan-umum-nomor-20-prt-m-2010-tentang-pedoman-pemanfaatan-dan-penggunaan-bagian-bagian-jalan.pdf"),
    ("S33", "Geofabrik Download Server (ekstrak OSM per wilayah Indonesia: Java, Sumatra, Kalimantan, Sulawesi, Nusa "
     "Tenggara, Maluku, Papua) dan Overpass API (pedoman pemakaian wajar +-10.000 permintaan dan 1 GB per hari).",
     "https://download.geofabrik.de/asia/indonesia.html"),
    ("S34", "Thomson, R. C. & Richardson, D. E. (1999). The 'good continuation' principle of perceptual organization "
     "applied to the generalization of road networks. Proceedings of the 19th International Cartographic "
     "Conference, Ottawa; dirangkum di Thomson (2003), 4th Space Syntax Symposium (stroke: ruas yang bersambung paling lurus dianggap satu jalan).",
     "https://www.spacesyntax.net/symposia-archive/SSS4/fullpapers/50Thomsonfpaper.pdf"),
    ("S15", "QGIS Python Plugins Repository - daftar plugin paling banyak diunduh (QuickMapServices, QuickOSM, "
            "Semi-Automatic Classification, mmqgis, Profile tool, dsb.) sebagai acuan nama dan ikon.",
     "https://plugins.qgis.org/plugins/most_downloaded/"),
]

# (keputusan, nilai/perilaku, alasan, sumber, status)
KEPUTUSAN = [
    ("Kesamaan koridor diukur dengan jarak, bukan WKT identik",
     "Garis dianggap satu koridor bila berada dalam toleransi jarak dari garis lain",
     "Garis hasil digitasi/ekspor ulang hampir tidak pernah identik verteks demi verteks. Pada data Bangka Belitung "
     "hanya 2 fitur yang identik, tetapi 69% panjang kabel berjarak <= 2,5 m dari kabel lain. Skrip panduan (kunci "
     "asWkt) hanya membuang yang identik; metode buffer mengukur persen panjang garis di dalam toleransi.",
     "S1, S2, S14, S19", "LITERATUR"),
    ("Lebar koridor bawaan 15 m (toleransi 7,5 m), dapat dipilih 5 / 11 / 15 / 25 m",
     "15 m = RUMIJA minimum jalan sedang; pilihan di jendela Consolidate Lines mengikuti RUMIJA jalan kecil, sedang, "
     "dan raya; laporan menampilkan kurva jarak dan lutut (Kneedle)",
     "Kebutuhan pengguna: satu garis per jalur, tidak tampak berdampingan. Versi 2.0 awal memakai 2,5 m (koridor 5 m, "
     "di bawah separuh badan jalan kecil agar kabel di dua sisi jalan terpisah); uji Bangka Belitung menunjukkan masih "
     "tersisa 95,7 km garis sejajar berjarak <= 10 m (122,5 km <= 15 m), umumnya kabel baru yang digambar 5-10 m di "
     "samping kabel lama di jalan yang sama. Kabel ditempatkan di dalam ruang milik jalan (RUMIJA), yang lebar "
     "minimumnya 11 / 15 / 25 / 30 m. Koridor 15 m menurunkan sisa sejajar <= 10 m menjadi 4,6 km (Bangka) dan "
     "0,5 km (Bali FTTT); 25 m menghilangkannya tetapi berisiko menggabungkan jalan sejajar yang berdekatan. Pilihan "
     "5 m tetap tersedia bila kabel di dua sisi jalan harus dipisah.",
     "S6, S16, S19, S28", "STANDAR"),
    ("Mode pangkas: setiap jalur unik dipertahankan",
     "Bagian di luar koridor selalu dipakai berapa pun persen cakupan garisnya",
     "Uji Bangka Belitung: versi 1.0 (ambang 80% + buang ekor pendek) kehilangan 17,9 km jalur unik (kelengkapan "
     "99,46%). Sejak 1.1 garis hanya berstatus DUPLIKAT bila tidak ada sisa di luar koridor dan pita drift. Ambang "
     "persen hanya dipakai mode 'utuh'.", "S1, S8, S19", "DESAIN"),
    ("Ekor pendek dan penyambung tidak dibuang",
     "Sisa yang menyentuh ujung garis tetap dipakai; garis duplikat yang menjadi satu-satunya penghubung dua garis "
     "terpilih menyumbang penyambung",
     "Uji Bangka Belitung: membuang ekor < 5 m dan duplikat penghubung menciptakan celah buatan 5-7,5 m. Kelengkapan "
     "topologi (ISO 19157) lebih penting daripada membuang beberapa meter garis rangkap.", "S8, S19", "DESAIN"),
    ("Pita drift: garis sejajar sampai 2 x toleransi dari garis terpilih = koridor yang sama",
     "Sisa yang seluruh titiknya <= 2 x toleransi dari garis terpilih dan berjalan di sampingnya (kaki tegak lurus "
     "di badan garis) dibuang; ekor yang memanjang melewati ujung garis tetap dipakai; celah yang mengarah ke untai "
     "lain dalam pita ini disambung",
     "Uji Bangka Belitung v1.1: masih ada 52 km (2,7%) garis sejajar <= 2,5 m sepanjang >= 10 m di keluaran, "
     "karena garis 2,5-5 m dari garis tertua dipertahankan dan ujung potongannya digeser ke garis tertua. Kabel di "
     "seberang jalan berjarak >= lebar badan jalan tersempit 5,5 m, di atas pita 2 x 2,5 = 5 m. Hasil v1.2: "
     "tumpukan 0 m dan setiap jalur masukan terwakili dalam 5,5 m (100,000%).", "S6, S19", "DESAIN"),
    ("Keluaran utama: kabel tunggal berisi garis asli tertua, bukan garis tengah baru",
     "Satu fitur per garis terpilih, geometri asli (dipangkas bila perlu), seluruh atribut asli + kolom su_*",
     "Kebutuhan pengguna: tampilkan garis dengan CREATEDATE paling lama sehingga tidak bertumpuk, tetap sebagai "
     "data kabel (NAME, MODEL, dst.). Garis tengah dari skeleton/medial axis (BecaGIS, ArcGIS Collapse Dual Lines) "
     "membuat geometri baru yang tidak pernah disurvei, butuh poligon, menghasilkan cabang palsu di persimpangan, "
     "dan tidak membawa atribut kabel; karena itu tidak dipakai sebagai hasil utama.", "S14, S20, S21, S22", "LITERATUR"),
    ("Sambungan potongan ditambahkan sebagai verteks, ujung asli tidak digeser",
     "Ujung potongan yang dipangkas disambung ke titik terdekat garis tertua dengan ruas pendek <= toleransi",
     "Menggeser ujung potongan dua-verteks memindahkan seluruh ruas (sampai 103 m pada data uji) ke atas garis "
     "tertua - geometri survei asli harus dipertahankan.", "S19", "DESAIN"),
    ("Semua hasil bisa disimpan langsung sebagai Shapefile",
     "Folder keluaran opsional; nama kolom keluaran <= 10 karakter",
     "Data operator dipertukarkan sebagai .shp; format DBF membatasi nama kolom 10 karakter (kolom tgl_terbaru "
     "diganti tgl_baru).", "S23", "STANDAR"),
    ("Prioritas tanggal tertua, tanggal tak terbaca di urutan terakhir",
     "Urut: tanggal (tertua dulu) -> panjang (terpanjang dulu) -> FID",
     "Sesuai kebutuhan panduan (CREATEDATE tertua). Skrip panduan memberi datetime.min pada tanggal gagal dibaca "
     "sehingga dianggap tertua; data Bangka Belitung memuat 13 tanggal '#N/A' yang kini ditaruh paling akhir. Format: "
     "ISO 8601, 2021/07/19 15:35:31.000, D/M/Y (Indonesia), YYYYMMDD, nama bulan, serial Excel.",
     "S9, S14, S19", "STANDAR"),
    ("Bagian paralel dipangkas lalu disambung (mode bawaan)",
     "Bagian di dalam koridor dibuang; sisa disambung ke titik terdekat garis pemilik koridor",
     "Praktik alat centerline industri: bagian tumpang-tindih dihapus sehingga rute berbagi satu garis tengah dan "
     "daftar yang dibuang dicatat.", "S7", "LITERATUR"),
    ("Noding sebelum Line Merge",
     "Sambung ujung <= toleransi sambung, tempel ujung ke badan garis (T), pecah di persilangan",
     "LineMerger hanya menggabungkan garis yang bertemu di ujung dan berhenti di simpul berderajat 1 atau >= 3. "
     "Undershoot/overshoot harus disambung dulu dengan snapping distance.", "S3, S4", "LITERATUR"),
    ("Celah segaris dan berkabel sama disambung otomatis sampai 10 m",
     "Jembatan bila (dua ujung saling menghadap dengan belokan <= 30 derajat) atau (nama kabel sama dan ujung "
     "mengarah ke sasaran <= 60 derajat); dipilih dengan hutan perentang minimum",
     "Data Bangka Belitung: 1.178 ujung bebas adalah celah segaris berkabel sama, memuncak di 5-7,5 m (pola "
     "penggambaran berhenti sebelum tiang). 91% ujung bebas berjarak <= 10 m dari garis lain. Belokan > 30 derajat "
     "adalah titik sudut (tiang sudut wajib tambat), bukan kelanjutan lurus. Kruskal memastikan satu jembatan "
     "terpendek per pasangan untai tanpa lingkar. Celah lain hanya dilaporkan.", "S4, S17, S18, S19", "DESAIN"),
    ("Satu untai = satu komponen tersambung; untai < 25 m ditandai FRAGMEN",
     "Kolom kelas UTAMA/FRAGMEN; untai bercabang tetap satu fitur (utuh = YA hanya bila tanpa cabang)",
     "Jaringan bercabang tidak bisa menjadi satu LineString. 25 m = separuh bentang tiang maksimum 50 m (median "
     "ruas data Bangka Belitung 55,9 m): potongan lebih pendek tidak mungkin satu bentang utuh, sehingga dipisah "
     "agar tidak mengaburkan jumlah untai (data uji: 57 fragmen, total 552 m).", "S3, S8, S18, S19", "DESAIN"),
    ("Perhitungan dalam meter: zona UTM per kelompok ruang; panjang dilaporkan elipsoidal",
     "Garis dikelompokkan menurut kedekatan (sel grid 0,01 derajat berjangkar absolut, jangkauan interaksi + 5 m); "
     "tiap kelompok dihitung di zona UTM pusat kelompoknya, apa pun CRS layer",
     "UTM bersifat konformal: di sekitar satu titik distorsinya berupa faktor skala seragam yang membesar menjauhi "
     "meridian tengah (0,9996 di meridian tengah; sekitar 1,08 pada 22 derajat, mis. Aceh bila Indonesia dihitung "
     "di satu zona tengah). Uji v1.2 pada data Bangka Belitung: faktor skala 1,0004 saja sudah menggeser 36 panjang "
     "potongan, 1,02 mengubah 12 status, 1,09 mengubah 40 status. Dengan zona per kelompok, kelompok yang sama "
     "selalu dihitung di zona yang sama, sehingga hasilnya tidak bergantung pada luas wilayah, CRS layer, maupun "
     "urutan fitur; juga hemat memori karena kelompok diproses satu per satu. EPSG:3395 di pusat data Bangka "
     "Belitung: faktor skala 1,0018; panjang keluaran diukur elipsoidal (QgsDistanceArea).",
     "S13, S19, S24", "STANDAR"),
    ("Pemutus seri tidak bergantung urutan berkas",
     "Tanggal sama -> terpanjang -> geometri (titik ujung, 1 mm) -> atribut -> FID; jarak sama -> segmen terdaftar "
     "lebih dulu",
     "FID berubah bila data dipotong atau digabung per wilayah. Data Bangka Belitung: 2.359 dari 3.050 garis berbagi "
     "CREATEDATE persis dengan garis lain, sehingga pemutus seri harus stabil.", "S19, S24", "DESAIN"),
    ("Satu alat otomatis untuk banyak data: pilih folder, Run",
     "Alat 'Seuntai Otomatis' mencari sendiri data garis di folder (atau folder pengguna / seluruh komputer), "
     "mengenali kolom tanggal, produk/LOB, dan nama kabel, lalu memproses tiap data dengan aturan yang sama; "
     "parameter ahli disembunyikan di bagian lanjutan",
     "Pengguna cukup mengenali folder, bukan mengingat nama kolom (recognition rather than recall), isian sedikit "
     "(desain minimalis), dan daftar data dapat dilihat dulu sebelum diproses (mencegah kesalahan). Antarmuka batch "
     "bawaan QGIS meminta satu baris per berkas dan pemetaan kolom manual; Seuntai mengisinya otomatis. Kolom "
     "tanggal dipilih dari nama yang dikenal (CREATEDATE, TGL_DIBUAT, ...), tipe Date/DateTime, atau isi >= 90% "
     "terbaca tanggal; kolom tanggal ubah/hapus dan angka murni (ID) tidak dipilih.", "S25, S26, S27", "DESAIN"),
    ("Banyak data sekali jalan tetap stabil",
     "Tiap data diproses terpisah; data yang gagal dicatat lalu dilanjutkan; layer sementara dilepas setelah tiap "
     "data; hasil sebelumnya (Hasil_Seuntai*, *_kabel_tunggal) tidak diproses ulang; data tidak cocok dilewati "
     "dengan alasan dan cara memperbaikinya",
     "Kesalahan satu berkas (rusak, tanpa CRS, tanpa tanggal) tidak boleh menghentikan ratusan berkas lain, dan "
     "pengguna harus tahu sebabnya (heuristik 1 dan 9). Uji 15 data: 10 berhasil, 5 dilewati dengan alasan tepat, "
     "0 gagal; hasil identik dengan pemrosesan satu per satu.", "S25, S27", "DESAIN"),
    ("Satu jalan = satu garis: garis dicocokkan ke jalan OpenStreetMap (bawaan aktif)",
     "Titik kabel dicocokkan ke ruas jalan terdekat dalam batas per kelas (22 m arteri, 16 m kolektor, 13 m tersier, "
     "10 m lokal, 8 m ramp, 6 m jalan servis/gang, 5 m jalan setapak) dan beda arah <= 30 derajat; garis baru "
     "dianggap jalur yang sama bila garis lama yang sudah dipilih mengikuti jalan yang sama di posisi yang sama "
     "(<= 8 m sepanjang jalan, 45 m untuk jalan satu arah/berpemisah), di sisi mana pun. Trotoar terpisah diabaikan, "
     "dua lajur jalan berpemisah dihitung satu jalan, ruas yang bersambung lurus (<= 20 derajat) dihitung satu jalan, "
     "celah <= 40 m di persimpangan ditutup, dan tidak dibuat penyambung melintang jalan (kecuali cabang yang memang menyeberang). Data jalan diunduh otomatis hanya di sekitar garis: paket petak 0,1 derajat "
     "(kota = beberapa MB) atau layanan langsung OSM untuk area kecil; unduhan satu pulau tidak pernah dijalankan diam-diam; "
     "semua sumber memberi hasil identik (seri jarak diputus menurut geometri ruas); tanpa internet hanya koridor yang dipakai",
     "Temuan pengguna di citra satelit: satu jalan tampil sebagai dua garis kabel di kiri-kanan jalan (Jl. Soekarno-"
     "Hatta dan Jl. Sumber Asih Bandung, Jl. Raya Cibadak Bogor). Kabel di dua sisi jalan berjarak 10-40 m, di atas "
     "koridor 15 m, sehingga koridor jarak saja tidak cukup. Pencocokan peta berbasis jarak dan arah (Walter & "
     "Fritsch 1999) dengan referensi linear ke garis tengah jalan memisahkan 'sisi lain jalan yang sama' dari 'jalan "
     "sejajar lain' yang sama jauhnya. Uji Jawa Barat (81.730 garis, semua produk): panjang garis ganda yang "
     "mengikuti jalan yang sama turun dari 1.569 km (8,6%) menjadi 334 km (-79%); panjang hasil 18.250 -> 17.664 "
     "km; 417 s. Uji QGIS 3.40 (2 November 2026): potongan Bandung (2.630 garis) 44 s dan Bogor (743 garis) 13 s dengan data jalan Jawa di cache; garis ganda di jalan yang sama 50,2 -> 2,0 km (Bandung) dan 7,5 -> 0,3 km (Bogor), 100% jalur masukan tetap terwakili dalam 45 m. Uji 'laptop baru' (cache kosong): Bandung 33 s termasuk unduhan paket 4 MB; hasil dari paket petak, GeoPackage, dan layanan langsung OSM identik byte demi byte (Bandung, Bogor, Curug Mekar). Regulasi membolehkan utilitas di kedua sisi jalan, jadi dua kabel nyata tetap mungkin: ID garis "
     "yang digabung dicatat di su_dup_fid dan data sumber tidak diubah. Geometri OSM tidak ditulis ke hasil; "
     "atribusi ODbL dicantumkan di laporan.",
     "S2, S28, S29, S30, S31, S32, S33, S34", "LITERATUR"),
    ("Warna status ramah buta warna + pola garis",
     "Palet Okabe-Ito; dipakai = utuh, dipangkas = putus-putus, duplikat = titik-titik",
     "Status tidak boleh dibedakan dengan warna saja. Teks laporan memenuhi kontras minimum 4,5:1.",
     "S10, S11", "STANDAR"),
    ("Nama, ikon, struktur plugin",
     "Nama unik tanpa kata 'plugin', ikon sendiri, Processing provider, menu Vector, data contoh",
     "Mengikuti pedoman rilis repositori plugin resmi QGIS dan pola plugin paling banyak diunduh.", "S12, S15",
     "STANDAR"),
]


def ref_html(ids):
    """'S1, S2' -> tautan ke daftar sumber di halaman."""
    return ", ".join("<a href='#%s'>%s</a>" % (i.strip(), i.strip()) for i in ids.split(","))
