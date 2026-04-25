# Validierungsstand

Dieses Dokument beschreibt den aktuell verifizierten Qualitäts- und Laufzeitstand des Plugins auf Basis von:

- lokalen Repository-Checks
- echten Windows/QGIS-Läufen
- hashbasierten Reports für Maßstabsfälle und den breiten amtlichen WMS-Katalog

Stand dieses Dokuments:

- Datum der letzten Abschlussvalidierung: `2026-03-14`

## Kurzurteil

Aktueller Stand:

- releasefähig
- technisch professionell umgesetzt
- auf echter Windows/QGIS-Runtime wiederholt validiert
- mit verbleibenden Restrisiken vor allem auf Seiten externer Webdienste, nicht im grundlegenden Engineering-Kern

Praktische Einordnung:

- Das Plugin ist aktuell in einem seriösen Sinn produktionsreif.
- Das bedeutet nicht, dass nie wieder ein Problem auftreten kann.
- Die wichtigsten verbleibenden Risiken liegen bei öffentlichen WMS-Diensten, deren Darstellung, Verfügbarkeit oder Backend sich ändern kann.

## Lokal verifizierte Checks

Lokal geprüft:

- `ruff` auf `custom_map_downloader`, `scripts`, `tests`
- `black --check` auf `custom_map_downloader`, `scripts`, `tests`
- `python3 -m unittest discover -s tests -v`

Letztes Ergebnis der lokalen Suite:

- `67 Tests`
- `OK`
- `8 skipped`

Die übersprungenen Tests sind die erwarteten QGIS-gebundenen Integrationstests in einer Nicht-QGIS-Umgebung.

## Echte Windows/QGIS-Abschlussvalidierung

Die Abschlussvalidierung auf echter Windows/QGIS-Runtime umfasste diese Blöcke:

1. Smoke-Pfad
2. Deploy-/Profil-E2E-Pfad
3. verpflichtende `scale_matrix`
4. breiten amtlichen WMS-Katalog `official_webmaps_catalog`

### 1. Smoke-Pfad

Direkt gegen echte QGIS-Runtime validiert:

- `test_export_small_raster`
- `test_export_small_raster_as_vrt`
- `test_export_small_raster_with_reprojection`
- `test_export_small_raster_with_target_scale`

Ergebnis:

- `4 Tests`
- `OK`

Damit sind auf echter Runtime ausdrücklich geprüft:

- normaler GeoTIFF-Export
- Tiling/VRT
- Reprojektion zwischen Render-CRS und Ausgabe-CRS
- Zielmaßstab / scale-dependent Rendering

### 2. Deployter Plugin-Stand im QGIS-Profil

Direkt gegen den deployten Plugin-Stand im Profil validiert:

- `test_class_factory_is_available`
- `test_plugin_import_source_matches_requested_mode`
- `test_export_small_raster`
- `test_export_small_raster_as_vrt`
- `test_export_small_raster_with_reprojection`
- `test_export_small_raster_with_target_scale`

Ergebnis:

- `6 Tests`
- `OK`

Wichtiger Befund:

- Der E2E-/Profilpfad wurde im Zuge der Abschlussvalidierung noch einmal gehärtet.
- Dabei wurden zwei echte Workflow-Themen korrigiert:
  - Profil-Importtests mussten Link-/Junction-Semantik auf Windows korrekt berücksichtigen
  - `scripts/install_dev_plugin.py` musste vorhandene Windows-Junctions robuster entfernen

## Verpflichtende Scale-Matrix

Die folgende `scale_matrix` ist verpflichtend und hash-gated:

| Fall | Diensttyp | Quelle | Status |
| --- | --- | --- | --- |
| `geosn_ortho_gray_scale_matrix` | Orthofoto | Sachsen | verifiziert |
| `basemap_gray_scale_matrix` | topographische Basemap | BKG | verifiziert |
| `basemap_color_scale_matrix` | topographische Basemap | BKG | verifiziert |

Validierungsmodell:

- zwei Zielmaßstäbe pro Fall
- echter Windows/QGIS-Lauf
- Hashvergleich für `small` und `large`
- striktes Gate über `scripts/check_scale_matrix_report.py`

Letztes Abschlussresultat:

- alle `6` Matrix-Zeilen `status = ok`

Verifizierte Größen und Hashes:

| Fall | Label | Größe | SHA256 |
| --- | --- | --- | --- |
| `basemap_color_scale_matrix` | `small` | `1429x1429` | `508b4a8163e8094c60fdc32fc21fc1e11933398dad610123a10f1968fef2ef12` |
| `basemap_color_scale_matrix` | `large` | `286x286` | `ed7c811cd41d135dd348fd9f93001acc195a0ae95a1dea1a93cee35c7cd1e976` |
| `basemap_gray_scale_matrix` | `small` | `1429x1429` | `b47deeef2d0af358cafcf017e24ca7b1dd14f43a30cad73fcc43252198d3c114` |
| `basemap_gray_scale_matrix` | `large` | `286x286` | `b4a15f30f4af2ff7266ec992ca9523b221d0396c1ceabaac7fb620a34a27c92d` |
| `geosn_ortho_gray_scale_matrix` | `small` | `2381x2381` | `c6367a4faf1757d70981236c77cccb8b299a66e6b8216837829825ba7e64c074` |
| `geosn_ortho_gray_scale_matrix` | `large` | `595x595` | `4e6154de72b7c0f0f0fa1906afed21d567f285f2fe2d5e702151311378eb8e07` |

## Breiter amtlicher WMS-Katalog

Der breite amtliche Katalog wird als `scenario_groups.official_webmaps_catalog` gepflegt und ist inzwischen ebenfalls hash-gated.

Abgedeckte amtliche Diensttypen:

- topographische Basemap
- topographische Karte
- Orthofoto
- reliefartige DGM-Ableitung

Abgedeckte Anbieter:

- BKG
- Sachsen
- Bayern
- Nordrhein-Westfalen

### Verifizierte Fälle

| Szenario | Kategorie | Anbieter | Region | Ergebnis |
| --- | --- | --- | --- | --- |
| `basemap_gray_tif` | topographische Basemap | BKG | Deutschland | verifiziert |
| `bkg_dgm200_relief_tif` | Relief aus DGM | BKG | Deutschland | verifiziert |
| `geosn_ortho_color` | Orthofoto | GeoSN | Sachsen | verifiziert |
| `bayern_dop40_tif` | Orthofoto | Bayern | Bayern | verifiziert |
| `nrw_dtk_color_tif` | topographische Karte | NRW | Nordrhein-Westfalen | verifiziert |
| `bayern_relief_tif` | Relief aus DGM | Bayern | Bayern | verifiziert |

### Verifizierte Baseline-Hashes

| Szenario | Größe | SHA256 |
| --- | --- | --- |
| `basemap_gray_tif` | `1000x1000` | `60f9f19c8757aad1b0d9f354f81033fd740822b2d44c39b243a31bbe7bf9f4f4` |
| `bkg_dgm200_relief_tif` | `200x200` | `a03d06bd4c2c55bb7ff5e908eb742198ed9371ea3e7293976bac0e7850655a7a` |
| `geosn_ortho_color` | `5000x5000` | `a5d18b3a2732435af9ee5bc2a418affcf30e2b47b071a39b0ecde8df8752bfde` |
| `bayern_dop40_tif` | `1250x1250` | `f38c8a896f03412f43143059aea349508e6191621438ed3d894b47c65e5afece` |
| `nrw_dtk_color_tif` | `1000x1000` | `aac68ebef8537087edf05251b617732af96bd582e814b32254debb7ee8d0c1d0` |
| `bayern_relief_tif` | `500x500` | `0299bb2651063ca34a7d01bc7ae0b967475a820f29798a4be4e67791bf7122a9` |

Validierungsmodell:

- isolierter Windows/QGIS-Kindprozess pro Szenario
- pro Szenario:
  - `stdout.log`
  - `stderr.log`
  - `network_scenarios.json`
- zusammenfassende Reports:
  - `scenario_catalog_report.json`
  - `scenario_catalog_report.md`
- striktes Gate über `scripts/check_network_catalog_report.py`

Letztes Abschlussresultat:

- alle `6` Katalog-Zeilen `status = ok`

## Wichtiger historischer Befund

Vor der jüngsten Exporter-Anpassung gab es bei mehreren echten Webkartenfällen native Windows/QGIS-Abstürze im kleinen Direktrender-Pfad mit `3221225477`.

Betroffen waren vor dem Fix:

- `basemap_gray_tif`
- `bayern_dop40_tif`
- `nrw_dtk_color_tif`
- `bayern_relief_tif`

Technische Konsequenz:

- Web-Layer werden jetzt grundsätzlich über den Tilepfad exportiert

Re-Validierung nach dem Fix:

- derselbe breite amtliche Katalog lief vollständig erfolgreich
- die hashbasierte Verifikation lief anschließend ebenfalls vollständig erfolgreich

## Gibt es aktuell noch Probleme?

Stand heute: keine bekannten offenen Kernprobleme, die gegen einen produktiven Release sprechen.

Es gibt aber weiterhin normale Restrisiken:

1. Drift öffentlicher Dienste
   - Styles, Caches, Backend-Versionen oder Datenstände können sich upstream ändern
   - Das kann Hash-Drift auslösen, obwohl der Plugin-Code korrekt bleibt

2. Umgebungsunterschiede
   - andere QGIS-/GDAL-Builds können sich anders verhalten
   - die stärkste aktuelle Absicherung ist die gepflegte Windows/QGIS-Host-Runtime

3. Nicht vollständig abgedeckte Dienstlandschaft
   - der aktuelle Katalog deckt wichtige amtliche WMS-Typen ab
   - er beweist nicht automatisch Korrektheit für jeden beliebigen Drittanbieter-WMS/WMTS

## Ist der Stand jetzt produktionsreif?

Ehrliche Antwort:

- Ja, der Stand ist aktuell professionell umgesetzt und produktionsreif.
- Nein, das ist kein Versprechen, dass externe Webdienste sich nie ändern oder nie ausfallen.

Präziser:

- Architektur, Tests, Release-Governance, CI-Gates, Diagnostik und echte Runtime-Validierung sind auf einem klar professionellen Niveau.
- Die verbleibenden Risiken sind überwiegend betriebliche und externe Risiken, nicht fehlende Basistechnik im Plugin.

## Empfehlung für Releases

Vor einem Release:

1. lokalen Release-Gate laufen lassen
2. aktuellen `scale_matrix`-Report prüfen
3. aktuellen `official_webmaps_catalog`-Report prüfen
4. bei `drift`, `missing`, `error` oder ungeklärten Runtime-Abweichungen nicht veröffentlichen
