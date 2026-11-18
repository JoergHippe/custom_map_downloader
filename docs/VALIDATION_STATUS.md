# Validierungsstand

**Aktuelle Einordnung (18.11.2026):** Die jüngsten erfolgreich
automatisiert geprüften Codeänderungen stehen auf
`7de08e43d119c88ad28cce91a1a739e12ec0e54a`
(QGIS-Dialog-/Profilkorrekturen).
Die untenstehenden früheren Befunde bleiben als datierte Nachweise
erhalten; neue Prüfungen ersetzen keine vollständige Freigabe
der offiziellen Windows-QGIS-/OSGeo4W-Desktop-Distribution.

Die aktuelle Änderung betrifft insbesondere lokale temporäre
Arbeitsverzeichnisse, sicheren Transfer ins Ziel-Staging,
MBTiles-Veröffentlichung und VRT-Rollback. Der breite amtliche
WMS-Katalog und echte SMB-Verbindungsausfälle bleiben separate
Release-Prüfpunkte. Änderungen von historischen öffentlichen
Bild-/Dateihashes sind nur Hinweise, solange die technische
Exportprüfung erfolgreich ist.

Freigabekriterien stehen in [TESTING.md](TESTING.md) und
[OGC_TEST_POLICY.md](OGC_TEST_POLICY.md).

## Dialog-/Profilzustand: Linux-QGIS-Regression (18.11.2026)

**Code-Commit:** `7de08e43d119c88ad28cce91a1a739e12ec0e54a`  
**Nachweis:** [Actions #44303291887](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44303291887)

- Python/Formatierung/Packaging: **PASS**
- QGIS 3: reale Dialog- und Exporttests **PASS**
- QGIS 4: reale Dialog- und Exporttests **PASS**
- Neue Regressionen: gespeicherte Layerauswahl beim Dialogstart,
  Wechsel/Refresh der Layerliste, Wiederherstellung eines
  VRT-Profils nach MBTiles und VRT-Dateiendung aus QSettings.
- Eine erste Testvariante mit temporär dem nativen QgsProject
  zugeordneten und anschließend entfernten Layern führte zu
  QGIS-C++-Abstürzen. Der Test verwendet jetzt isolierte
  Layer-Auswahldaten; die QGIS-Dialog- und Qt-Komponenten bleiben echt.
- **Noch nicht erneut geprüft:** native Windows-QGIS-3/4-Matrix
  speziell für diese Dialogkorrektur. Ebenso keine Freigabe mit dem
  offiziellen Windows-OSGeo4W-/Standalone-Installer.

Die dokumentierte Temp-/Staging-Architektur bleibt unverändert.
Details zu den historischen QGIS-Extent-Workarounds stehen in
[EXTENT_SELECTION.md](EXTENT_SELECTION.md).

## Aktueller geprüfter Stand: temporäre Exportoperationen (18.11.2026)

**Merge-Commit auf `main`:**
`ae7de62cf878913a9e8a72028efcd8d54f81389f`.
Die Änderung wurde in [PR #3](https://github.com/JoergHippe/custom_map_downloader/pull/3)
mit folgenden automatisierten Nachweisen geprüft:

| Prüfumgebung | GitHub Actions | Ergebnis |
| --- | --- | --- |
| Python/Ruff/Black/Unit/Packaging, Linux QGIS 3 und Linux QGIS 4 auf `main` | [#44296095045](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44296095045) | 3/3 PASS |
| Native Windows conda-forge QGIS 3.44.15 und 4.2.3 (PR-Head `726ffd601ef83ffed79eaee50d4dbe4c268ca6ad`) | [#44295236004](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44295236004) | 2/2 PASS |
| Linux-PR-Matrix für denselben PR-Head | [#44295236007](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44295236007) | 3/3 PASS |

Die Windows-Matrix umfasst nun auch
`tests.test_output_transaction`: lokales Arbeitsverzeichnis,
Veröffentlichungsreihenfolge der VRT-Kacheln, Sidecars, simulierten
Kopierabbruch, Platzmangel-Fallback, Dateisperren und
Recovery-Fehlersituationen. Die QGIS-3/4-Integration deckt weiterhin
reale Raster-, VRT-, MBTiles- und lokale WMS-/WMTS-Ausgaben ab.

**Nicht durch CI nachgewiesen:**

- Performancegewinn durch lokales Temp auf dem konkreten SMB-Netzwerk;
  der Vergleich muss die vollständige Laufzeit einschließlich Kopieren
  und Veröffentlichung berücksichtigen.
- Reale Netzwerkunterbrechung eines UNC-Pfades bzw. gemappten
  Firmenlaufwerks.
- Sichtbare Abnahme des gebauten Plugin-Pakets in einer offiziellen
  Windows-QGIS-/OSGeo4W-Installation mit deutscher Locale, Dateisperren
  und allen Ausgabeformaten.
- Vollständige aktuelle amtliche WMS-Katalog- und Release-Freigabe.

**Bewertung:** Automatische Regressionen erfolgreich;
**keine allgemeine Releasefreigabe**. Für das weitere Vorgehen siehe
[TESTING.md](TESTING.md) und [EXPORT_STAGING.md](EXPORT_STAGING.md).

## CI-Ergebnisse auf dem Entwicklungsbranch (2026-11-17)

### Amtliche WMS-Pflichtmaßstabsmatrix und WMTS-Live-Prüfung

**WMS:** [Actions #44196241970](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44196241970).
Alle drei in `scale_matrix` konfigurierten Pflichtfälle (GeoSN-Orthofoto
Grau, basemap.de Grau, basemap.de Farbe) mit jeweils zwei Maßstäben
unter **QGIS 3.44.15 und 4.2.3 erfolgreich**: 12 GeoTIFF-Exporte,
2/2 CI-Jobs PASS. Die Rasterabmessungen und Maßstabsdifferenzen stimmen.
Die aktuellen Dateihashes sind für jeden Fall zwischen QGIS 3/4 identisch.

| Dienst | Maßstäbe | Rastergröße (klein / groß) | Historische Referenz |
| --- | --- | --- | --- |
| GeoSN Orthofoto Grau | 1:1.500 / 1:6.000 | 2381×2381 / 595×595 | 2× übereinstimmend |
| basemap.de Grau | 1:5.000 / 1:25.000 | 1429×1429 / 286×286 | 2× abweichend |
| basemap.de Farbe | 1:4.000 / 1:20.000 | 1429×1429 / 286×286 | 2× abweichend |

Die alten Hashwerte bleiben unverändert; Abweichungen sind Hinweise
und keine technischen Exportfehler. Der zusätzliche, breite Katalog
`official_webmaps_catalog` wurde hierbei **noch nicht vollständig** geprüft.

**Echter amtlicher WMTS:** basemap.de Web Raster Grau mit
`GetCapabilities`, TileMatrixSet `DE_EPSG_25833_ADV`, Ausgabe
500×500 Pixel in EPSG:25833.
- [WMTS-Lauf #44196603830](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44196603830): QGIS 3/4 2/2 PASS.
- [WMTS-Wiederholung #44197047298](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44197047298): erneut 2/2 PASS.
  RGB-Kanalwerte 51–255, Alpha durchgehend 255; kein leeres oder
  transparentes Bild. Georeferenzierung zwischen QGIS-Versionen gleich.
- Die **Datei- und Pixel-Hashes wechseln zwischen Live-Läufen**.
  Ein QGIS-3-Dateihash aus dem ersten Lauf entspricht exakt dem
  QGIS-4-Dateihash aus dem zweiten. Eine systematische
  QGIS-versionsbedingte Abweichung ist nicht belegt; stabile
  Pixel-Reproduzierbarkeit ebenfalls nicht. Die Ursache ist offen.
- WMTS hat deshalb `technical_gate=pass`,
  `baseline_status=untracked`, `release_gate=not_assessed`.
  Die technische Funktionsfähigkeit ist nachgewiesen, **nicht**
  die pixelgenaue Wiederholbarkeit oder eine allgemeine Freigabe.



### Raster-Fingerprints: Pixel, Georeferenzierung und TIFF-Datei getrennt

**Neu geprüft am 17.11.2026** gegen die beiden WMS mit historischen
Dateihash-Abweichungen: QGIS 3.44.15 (GDAL 3.8.4) und
QGIS 4.2.3 (GDAL 3.12.2).

| Dienst | Aktueller Pixel-Hash | Aktueller Georeferenzierungs-Hash | QGIS 3 vs. 4 |
| --- | --- | --- | --- |
| basemap.de Grau | `1f377926b6b35baa…` | `ec3f87c5736669ba…` | Datei/Pixel/Geo identisch |
| NRW DTK Farbe | `2085515b2c19c855…` | `aabd167b31d8d8fa…` | Datei/Pixel/Geo identisch |

Belege:
[basemap.de #44187663983](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44187663983),
[NRW #44187943937](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44187943937).

Beide aktuellen Ausgaben sind je Dienst zwischen QGIS 3 und 4 auf
allen drei Ebenen identisch, **trotz unterschiedlicher GDAL-Versionen**.
Die früheren Referenzwerte bleiben abweichend, ihre Ursachen aber
**nicht abschließend erklärbar**: Es konnten weder frühere GeoTIFF-Dateien
im Repository noch nutzbare Rasterartefakte in ausgewählten historischen
Actions-Läufen gefunden werden. Aus einem historischen Datei-Hash lassen
sich frühere Pixel-/Georeferenzierungs-Hashes nicht ermitteln.

Die neue Diagnose wird künftig für Live-TIF-Szenarien im Bericht
`raster_diagnostics` gespeichert; sie bewahrt ursprüngliche Hash-Baselines
unverändert. Weitere Alt-Raster können mit
`python scripts/raster_diagnostics.py aktuell.tif --reference alt.tif`
unabhängig auf Pixel-, Georeferenzierungs- und Dateiänderungen
untersucht werden.

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
Sie beweist für sich genommen keinen Pluginfehler. Die Abweichung
bleibt als **historischer Referenzhinweis** dokumentiert, führt aber
bei technisch korrektem Export nicht mehr zum Scheitern des Tests.
Die vollständige Maßstabsmatrix und ein amtlicher WMTS-Live-Fall sind
durch diese drei WMS-Smokes weiterhin nicht abgedeckt.

Der Live-Runner unterscheidet `technical_gate=pass` von
`baseline_status=match|drift|untracked` und setzt
`release_gate=not_assessed`, da ein Live-Smoke keine Releasefreigabe ist.



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

## Historischer Stand vom 14. März 2026 (Version 0.4.0)

Die damaligen Tests umfassten lokale Python-Prüfungen, Windows/QGIS-Raster-
und VRT-Exporte, die Maßstabsmatrix und den amtlichen Webkartenkatalog.
Für den damaligen Stand wurden auch SHA-256-Dateiwerte als strikte
Freigabebedingung verwendet. Diese Regel ist **nicht mehr gültig**:
Seit November 2026 ist die technische Exportprüfung vom historischen
Daten-/Dateihashvergleich getrennt.

Die damaligen Detailtabellen, Aussagen zur Produktionsreife und Hashlisten
bleiben über die [Git-Historie des Dokuments](https://github.com/JoergHippe/custom_map_downloader/commits/3ded28ea50b66c556ce55dfbde4675528e06d043/docs/VALIDATION_STATUS.md)
nachvollziehbar. Referenzhashes in der Testkonfiguration werden nicht
automatisch geändert oder entfernt. Die damalige Freigabebewertung ist
**nicht** auf Version 0.5.0 übertragbar.
