# Mengembangkan dan merilis Seuntai

## Struktur
```
seuntai/                     plugin QGIS (isi ZIP rilis)
  core.py                    pemilihan koridor, pencocokan ke jalan, noding/merge (Python murni, bisa diuji tanpa QGIS)
  roads.py                   data jalan OpenStreetMap: paket petak, layanan langsung, cache
  alg_strand.py batch.py     alat Processing (satu layer / satu folder)
  dialog.py                  jendela Consolidate Lines
  report.py sumber.py        laporan HTML dan dasar setiap keputusan (DASAR_KEPUTUSAN.md)
  tests/                     uji otomatis (tidak ikut ZIP)
tools/build_road_pack.py     pembuat paket petak jalan dari ekstrak Geofabrik
scripts/release.py           validasi aturan plugins.qgis.org + buat ZIP
scripts/upload_plugin.py     unggah ZIP ke plugins.qgis.org (XML-RPC)
scripts/check_neutral.py     cegah nama merek/perusahaan masuk ke rilis publik
.github/workflows/           CI (setiap push), rilis (setiap tag v*), paket jalan (tiap bulan)
```

## Mengubah aturan
1. Setiap angka batas dan aturan baru dicatat di `sumber.py` (`KEPUTUSAN`: nilai, alasan, sumber, jenis) dan
   `DASAR_KEPUTUSAN.md`, sehingga laporan selalu bisa menjelaskan dasarnya.
2. Tambahkan uji di `seuntai/tests/` (Python murni). Hasil harus tetap sama bila urutan fitur atau urutan data jalan
   dibalik.

## Paket jalan (OpenStreetMap)
Workflow **road-pack** mengunduh ekstrak Geofabrik per pulau, membangun petak 0,1° dengan `tools/build_road_pack.py`,
dan menerbitkannya di GitHub Pages (`https://jetstimo.github.io/seuntai/pack/`) tiap tanggal 2. Aktifkan sekali:
Settings → Pages → Source: **GitHub Actions**, lalu Actions → road-pack → **Run workflow**. Data © OpenStreetMap
contributors, ODbL 1.0; halaman Pages memuat atribusinya.

## Merilis versi baru (otomatis)
1. Naikkan `version=` di `seuntai/metadata.txt` dan `__version__` di `seuntai/alg_strand.py`, tulis baris
   `changelog=` untuk versi itu, dan perbarui `CHANGELOG.md`.
2. Commit, lalu buat tag yang sama dengan versi:
   ```
   git tag v2.0.1
   git push origin main v2.0.1
   ```
3. Workflow **Release** menguji, membuat `seuntai.2.0.1.zip`, melampirkannya ke GitHub Release, dan mengunggahnya ke
   plugins.qgis.org. Pengguna QGIS melihat pembaruan di tab **Upgradeable** Plugin Manager.

## Secrets repositori (GitHub: Settings → Secrets and variables → Actions)
| Nama | Isi |
|---|---|
| `OSGEO_USER`, `OSGEO_PASSWORD` | akun OSGeo pemilik plugin (untuk unggah otomatis) |
| `BRAND_DENYLIST` | daftar nama merek/perusahaan yang tidak boleh muncul, dipisah koma (tidak disimpan di repo publik) |

## Rilis pertama (sekali, manual)
plugins.qgis.org mewajibkan unggahan pertama lewat web: login dengan akun OSGeo di https://plugins.qgis.org/plugins/add/,
unggah ZIP dari GitHub Release, lalu tunggu persetujuan tim QGIS. Setelah itu rilis berikutnya berjalan otomatis.
