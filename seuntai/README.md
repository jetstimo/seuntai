# Seuntai – Strand Consolidator

![Seuntai](icon.png)

**Seuntai** (Indonesian for *one strand*) is a QGIS plugin for line networks — cables, routes — that were digitised
more than once, so several lines run on top of or beside each other in one corridor. In every corridor only the
**line with the oldest creation date** is kept, unchanged and with all its original attributes, for the product/LOB
you choose. The result is one non-stacked layer, saved as a Shapefile.

Copyright © 2026 **Joseph Edward Timothy Siahaan** and **Sidah Fahira** · GNU GPL v2 or later · QGIS 3.22 LTR – 4.x

## Install
QGIS → **Plugins → Manage and Install Plugins → All** → search **Seuntai** → **Install**.
New versions appear under **Upgradeable**; no ZIP needed.

## Use
1. Click the **Seuntai** toolbar icon (**Consolidate Lines…**).
2. Pick a line layer (or **Open file…**). The product/LOB column and the creation-date column are detected
   automatically; the product values found in the data are listed with their line counts. Tick the ones to keep.
3. Choose the **Corridor width**: lines closer together than this along the same route become one line. Default
   15 m (right-of-way of a medium road); 5 m keeps cables on opposite sides of a road apart; 11 m and 25 m match a
   small and a main road.
4. Keep **Match lines to roads (OpenStreetMap)** ticked (default). Cables drawn on both sides of the same road are
   then reduced to one line, even when they are more than the corridor width apart (see below).
5. Press **Run**. The single-line Shapefile (`…_kabel_tunggal.shp`) is added to the map and the report opens.

The report (Indonesian, one offline HTML file) explains the result in plain language: a ready-to-use checklist,
Before / After / Compare map views, an animated explainer, the story of every line (why it was kept, trimmed or
removed and which older line won), a gap checklist saved in the browser, CSV export, FAQ and glossary pop-ups.

| Menu Vector → Seuntai | What it does |
|---|---|
| Consolidate Lines… | one layer, product/LOB picker, one line per corridor (oldest kept) |
| Consolidate a Folder… | every line dataset in a folder, same rules, one summary |
| Check Stacked Corridors… | report only: duplicates, partly parallel lines, gaps, junctions |
| Load Sample Data / About Seuntai | |

All expert settings (tolerance, mode, fields, filters) are in the Processing tools under **Advanced**.

## Road matching (one road = one line)
With road matching on, every cable point is matched to the nearest road of OpenStreetMap (distance limit by road
class: 22 m main roads, 16 m secondary, 13 m tertiary, 10 m local streets, 6 m service roads and alleys; direction
within 30 degrees). A newer line is treated as the same route when an older kept line already follows the same
road at the same position, on either side. Sidewalks drawn as separate ways are ignored, the two carriageways of a
divided road count as one road, and road pieces that continue straight through a junction are one road.

- **Automatic, light and fast:** only the road data around your lines is downloaded, once, and cached in the QGIS
  profile (`seuntai_cache/osm`, refreshed after 90 days). Source order:
  1. *Road pack* - OpenStreetMap roads cut into 0.1° tiles (about 0.1-1.4 MB each). A city such as Bandung needs
     about 4 MB; tested on a fresh cache: 33 s for 2,630 lines including the download.
  2. *OpenStreetMap live service (Overpass)* - small areas (up to 8 areas of 0.05°) when no road pack is
     reachable; 1-2 minutes the first time, seconds afterwards.
  3. Otherwise Seuntai warns and uses the corridor width only. A whole-island download (0.1-0.9 GB) is never
     started silently; it can be allowed with the setting `seuntai/allow_region_download = true`.
- **Privacy:** your cable data never leaves your computer. Only the road tiles around it are requested (the pack
  server sees which 11 km tiles; the live service sees the bounding box of small areas). Untick road matching
  for data whose location must not be revealed at all.
- **Same result from every source:** the three sources give byte-identical results (tested on three areas).
- **Offline or no roads found:** Seuntai warns and falls back to the corridor width only.
- **Own road layer:** Processing tool → Advanced → *Road layer* (OSM, RBI or any line layer).
- Road geometry is never written into the results; it only guides the choice. Road data © OpenStreetMap
  contributors, ODbL.
- Cables on both sides of a road can be real (two cables). The merged line IDs are kept in `su_dup_fid`; the
  source data is never changed.

Tested on West Java data (81,730 lines) and in QGIS 3.40 on Bandung and Bogor: two lines following the same road
dropped by 96% compared with the corridor alone, and 100% of the input routes stay represented within 45 m.

## No creation date?
If a layer has no creation-date column (or every date is unreadable), Seuntai shows a warning and still reduces
stacked lines to one per corridor, but keeps the **longest** line instead of the oldest. Every such result is marked:
field `su_dasar = PANJANG` and `_TANPA_TANGGAL` in the file names. With dates, `su_dasar = TANGGAL`.
Impossible dates (`#N/A`, 1899/1900 placeholders, future dates) are treated as missing and ranked last.

## How it works (short)
1. Filter by product/LOB value (and an optional QGIS expression).
2. Rank: oldest date → longest → geometry → attributes (independent of file order).
3. Compare each line with the lines already kept using buffer overlap (Goodchild & Hunter 1997, default corridor
   15 m = 7.5 m each side): duplicates are dropped, partly parallel parts are trimmed.
4. Node and merge kept pieces (JTS/GEOS LineMerger rule); small aligned gaps are bridged, others reported.
5. Lines in a geographic or Mercator CRS are processed in the UTM zone of each spatial cluster; lengths are ellipsoidal.

Every rule with its reason and source is listed in [DASAR_KEPUTUSAN.md](DASAR_KEPUTUSAN.md) and at the end of each
report. Reports are in Indonesian.

## Requirements
No extra Python packages and no account. Internet is used only to download road data for road matching (can be
switched off). Menus, forms and messages are in English; reports are in Indonesian.

## Development
See [CONTRIBUTING.md](https://github.com/jetstimo/seuntai/blob/main/CONTRIBUTING.md): tests, release by git tag,
automatic upload to the QGIS plugin repository, monthly road pack.

## License
Code: GPL-2.0-or-later – see [LICENSE](LICENSE). Fonts Inter and IBM Plex Mono: SIL Open Font License 1.1
(`assets/fonts/OFL.txt`).
Leaflet 1.9.4: BSD-2-Clause (`assets/map/LEAFLET_LICENSE.txt`).
