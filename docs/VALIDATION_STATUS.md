# Validierungsstand

> **Historischer Validierungsbericht (2026-03-14).** Die nachstehenden Ergebnisse
> beziehen sich auf den damals getesteten Stand. Der aktuelle Repository-Stand
> `0.5.0` enthält spätere Änderungen vom April (u. a. MBTiles und Dialogablauf),
> die durch diesen Bericht nicht abgedeckt sind. Die früheren GitHub Actions wurden im
> Oktober 2026 deaktiviert; die neue CI läuft seit November auf dem Entwicklungsbranch. Aussagen wie „produktionsreif“ und „releasefähig“
> sind daher **keine aktuelle Freigabe** für `main` oder QGIS 4.x.
> Für aktuelle Freigabekriterien siehe [TESTING.md](TESTING.md).

## CI-Ergebnisse auf dem Entwicklungsbranch (2026-11-17)

### Amtliche Live-WMS-Tests, 17.11.2026

Alle drei amtlichen WMS-Szenarien exportierten unter QGIS 3.44.15 und
QGIS 4.2.3 erfolgreich. Je Dienst stimmen die **neuen** Dateihashes
zwischen beiden Versionen exakt überein.

| Dienst | Ausgabepixel | Alter Hash (Präfix) | Neuer Hash (Präfix) | Status |
| --- | ---: | --- | --- | --- |
| BKG DGM200 Relief | 200 × 200 | `a03d06bd` | `a03d06bd` | Referenz bestätigt |
| basemap.de Grau | 1000 × 1000 | `60f9f19c` | `6b6214a5` | Review erforderlich |
| NRW DTK Farbe | 1000 × 1000 | `aac68ebe` | `8cfe2e93` | Review erforderlich |

Nachweise: [BKG #44183991013](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44183991013),
[basemap.de #44184326655](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44184326655),
[NRW #44184619733](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44184619733).

**Keine Baselines aktualisiert.** Eine Hash-Differenz kann durch
GeoTIFF-/GDAL-Metadaten oder geänderte Karteninhalte entstehen.
Sie beweist für sich genommen keinen Pluginfehler, ist aber ein offenes
Release-Gate. Die komplette amtliche Maßstabsmatrix und amtliche WMTS
sind durch diese drei WMS-Smokes nicht abgedeckt.

Der neue Runner trennt technischen Exportstatus von Referenzstatus
und dokumentiert `release_gate=review_required` bei Abweichungen.



### Native Windows-QGIS 3/4 und lokale WMS-/WMTS-Server

**Geprüfter Commit:** `711b72a390f4b8086a63bba3517f80f757b6dd84`  
**Windows Actions:** [Lauf 44181305999](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44181305999)  
**Linux Actions:** [Lauf 44179443697](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44179443697)

- **Windows: 2/2 Jobs PASS**: QGIS 3.44.15 und QGIS 4.2.3
  aus conda-forge, jeweils 24 reale Qt-/QGIS-Integrationstests.
- **Linux: 3/3 Jobs PASS** für den geprüften WMS-/WMTS-Code.
- WMS 1.3.0: QGIS lädt GetCapabilities und GetMap vom lokalen
  HTTP-Dienst und exportiert ein geprüftes GeoTIFF.
- WMTS 1.0.0: QGIS interpretiert den lokalen TileMatrixSet-Katalog,
  lädt GetTile-Kacheln und exportiert ein geprüftes GeoTIFF.
- Windows-spezifischer Testfehler behoben: Explizites Schließen
  von SQLite-Leseverbindungen, damit MBTiles-Dateien ohne
  Dateisperre gelöscht werden können.
- Die Tests sind **netzunabhängig** und ersetzen ausdrücklich
  nicht die amtliche WMS-/WMTS-Hash-/Maßstabsmatrix.
- Die offizielle Windows-OSGeo4W-/Standalone-Distribution wurde
  mit diesem neuen CI-Lauf noch nicht gesondert abgenommen.



### MBTiles-Aufwandswarnung und ausdrückliche Bestätigung

**Geprüfter Code-Commit:** `985e7dc0be79761ec8790afee1748321c5c9825b`  
**GitHub Actions:** [Lauf 44176616387](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44176616387)

- **3/3 Jobs PASS**: Python-Qualität/Paketprüfung sowie QGIS 3.44.15
  und QGIS 4.2.3.
- Neue Unit-Tests zu den Größenstufen und zum Dateivolumen. Die Schätzung berücksichtigt jetzt die
  Kachelgröße relativ zur Referenz von 256 px (quadratische Skalierung).
- Python-Job: 103 Tests (26 erwartete Skips ohne QGIS), Ruff, Black,
  Governance und Packaging bestanden.
- Neue echte QGIS-Integrationstests: Eine extreme, aber mathematisch
  gültige Exportplanung erfordert ausdrücklich `Yes` auch bei
  deaktivierten normalen Bestätigungen; `No` verwirft den Vorgang.
- Bestätigungsdialog ist standardmäßig auf `No` gesetzt. Die normale
  Bestätigungsoption bleibt für kleine Exporte abschaltbar.
- **Keine automatische Größenbeschränkung**: Die Schätzung ist bewusst
  als Warnwert und nicht als Speicherplatz- oder Zeitgarantie zu verstehen.



### Speicherarme MBTiles-Tileplanung

**Geprüfter Commit:** `1dca7393cbe52d98e8f4f369044b3d92e1456a41`  
**GitHub Actions:** [Lauf 44173639820](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44173639820)

- **3/3 CI-Jobs erfolgreich:** Python-Unit-/Formatierungs-/Packaging-Checks,
  QGIS 3.44.15 und QGIS 4.2.3.
- Der Kachelplan enthält keine vorab erzeugten `QgsRectangle`-/Tile-Objekte
  mehr. Ein Generator liefert sie unmittelbar vor der Verarbeitung.
- Neue Unit-Tests erzeugen eine weltumspannende Planung bis Zoom 22,
  ohne die Kacheln zu materialisieren. Geprüft: Anzahl, wiederholbare
  Iteration, Kachelreihenfolge und Abschluss der Fortschrittsanzeige.
- Bestehende reale QGIS-3/4-MBTiles-End-to-End-Tests auf beiden
  Laufzeiten bestanden.
- Keine Aussage über *praktikable* Dateigrößen oder Laufzeiten gigantischer
  Exporte: Nutzerwarnung/Begrenzung bleibt offen.


### Korrektur der Koordinatenfeld-Zuordnung und lokalisierter Zahlenwerte

**Commit:** `35628339511b1934af104e6a62c1cdd3c88d79f3`  
**Nachweis:** [Actions #44172109704](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44172109704)

Unter QGIS 3.44.15 und 4.2.3 wurden doppelte Feldreferenzen im
internen QGIS-Widget nachgewiesen: `xmax` verwies fälschlich auf
`mYMaxLineEdit`. Die Zuordnung erfolgt nun ausschließlich über exakte
Objektnamen ohne positionsabhängiges Raten. Tests für manuelle
X-Koordinateneingabe, API-seitige Aktualisierung sichtbarer Werte,
unbekannte Feldnamen und Deutsch-/Englisch-Gruppierungsformate
bestehen unter beiden QGIS-Versionen.

Die QGIS-interne Komponente bleibt bewusst integriert.
Vollständige Windows-/Locale-Freigabe weiterhin offen.

### Ausdehnungsdialog und Profilwiederherstellung

- In QGIS 3.44.15 und QGIS 4.2.3 wurde durch neue echte Dialogtests
  nachgewiesen, dass `setCurrentExtent()` beim Profil-Reimport das
  ausgewählte Exportrechteck **nicht** aktualisierte.
- Der Pfad wurde auf `setOutputExtentFromUser()` umgestellt.
- Erfolgreich getestet: Canvas-Reset, Benutzer-Ausdehnung,
  Profilwiederherstellung, CRS-Wechsel, wiederholtes Zeichnen mit
  Qt-Mausereignissen und Abbruch durch Werkzeugwechsel.
- Nachweis: [CI-Lauf 44169404947](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44169404947),
  Commit `e233a1bd1ca96b93ad5ae882e1bf8d4c456e49c4`, alle 3 Jobs bestanden.
- Der vollständige Windows-GUI- und Locale-Test bleibt ausdrücklich offen;
  Details und Risiken in [EXTENT_SELECTION.md](EXTENT_SELECTION.md).


### MBTiles-Dateisicherheit und reale Exporttests

**Geprüfter Commit:** `e7604ac3cc88b3ecc8cb1b47d82112b2496037f6`  
**GitHub Actions:** [Workflow-Lauf 44164135334](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44164135334)

| Job | Umfang | Ergebnis |
| --- | --- | --- |
| Python quality | Ruff, Black, 85 Tests (12 erwartete Skips ohne QGIS), Packaging | PASS |
| QGIS 3 | Plugin-Import, 2 QImage-, 4 Raster- und 2 MBTiles-End-to-End-Tests | PASS |
| QGIS 4 | Plugin-Import, 2 QImage-, 4 Raster- und 2 MBTiles-End-to-End-Tests | PASS |

Die MBTiles-Szenarien prüfen eine vorhandene Zieldatei bei erfolgreichem
Ersatz und beim Abbruch nach Erstellung der temporären SQLite-Datenbank.
Sie ersetzen keine vollständige Windows-/Webdienst-Validierung.

### Erste QGIS-3/4-Baseline

**Branch:** `chore/restart-quality-baseline-20261117`  
**Geprüfter Commit:** `3ccd4e3600d014b896771d29e9edf4eaa3c67688`  
**GitHub Actions:** [Workflow-Lauf 44160918990](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44160918990)

| CI-Job | Laufzeit/Prüfumfang | Ergebnis |
| --- | --- | --- |
| Python quality | Ruff, Black, 79 Tests (10 Skip ohne QGIS), Übersetzungen, Release-Governance, Paketprüfung | PASS |
| QGIS 3 | QGIS 3.44.15, Qt 5.15.13; Plugin-Import, 2 QImage- und 4 Export-Smoke-Tests | PASS |
| QGIS 4 | QGIS 4.2.3, Qt 6.10.2; Plugin-Import, 2 QImage- und 4 Export-Smoke-Tests | PASS |

**Geltungsbereich:** Diese Ergebnisse belegen ausschließlich die genannten CI-Prüfungen
für den aufgeführten Branch-Commit. Sie ersetzen **nicht** die vollständige
Windows-GUI-, Netz-WMS/WMTS- und vollständige Release-Validierung. Der Stand wurde
noch nicht nach `main` übernommen und QGIS 4.x ist noch nicht offiziell freigegeben.

## Historischer Validierungsbericht vom 14. März 2026

Dieses Dokument beschreibt den im März 2026 verifizierten Qualitäts- und Laufzeitstand des Plugins auf Basis von:

- lokalen Repository-Checks
- echten Windows/QGIS-Läufen
- hashbasierten Reports für Maßstabsfälle und den breiten amtlichen WMS-Katalog

Stand dieses Dokuments:

- Datum der letzten Abschlussvalidierung: `2026-03-14`

## Kurzurteil (Stand 2026-03-14, nicht auf 0.5.0 übertragbar)

Damals dokumentierter Stand:

- releasefähig
- technisch professionell umgesetzt
- auf echter Windows/QGIS-Runtime wiederholt validiert
- mit verbleibenden Restrisiken vor allem auf Seiten externer Webdienste, nicht im grundlegenden Engineering-Kern

Praktische Einordnung:

- Das Plugin wurde damals als produktionsreif bewertet; diese Aussage ist keine aktuelle Freigabe.
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
