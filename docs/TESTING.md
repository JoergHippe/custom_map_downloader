# Teststrategie und Freigabekriterien

Stand: 2026-11-18. Dieses Dokument ist die Quelle für geplante QGIS-Kompatibilitätsprüfungen;
[VALIDATION_STATUS.md](VALIDATION_STATUS.md) enthält historische Messwerte.

## Status

- Metadata-Baseline: QGIS >= 3.34; **QGIS 4.x noch nicht freigegeben**.
- Der letzte belegte vollständige Windows/QGIS-Bericht stammt vom 2026-03-14 und
  deckt Änderungen aus April 2026 nicht ab.
- QGIS 3.44.15 und 4.2.3: echte Linux- und Windows-CI mit Qt-Dialog und
  lokalen WMS-/WMTS-Exporten bestanden. Amtliche Live-Dienste und offizielle
  Windows-Desktop-Distribution bleiben separate Release-Freigabekriterien.

## Prüfebenen

| Ebene | Umgebung | Gate |
| --- | --- | --- |
| Statisch | Python 3.12, Ruff, Black | Pflicht bei PR und Push |
| Unit | Python ohne QGIS, unittest mit Stubs | Pflicht bei PR und Push |
| Integration | QGIS 3 und 4, echte Python-Bindings, ohne Netz | Pflicht vor 4.x-Freigabe |
| Windows CI | GitHub-gehostete QGIS-3/4-conda-Umgebungen mit echten Qt-/QGIS-Tests | Pflicht bei PR |
| Lokale OGC-Tests | Reproduzierbare WMS- und WMTS-HTTP-Server unter Windows/Linux | Pflicht bei PR |
| Windows Desktop | Offizielle QGIS-/OSGeo4W-Installation mit sichtbarer GUI | Release-Abnahme |
| Amtliche Netztests | Öffentliche WMS-/WMTS-Dienste und Maßstabs-/Hashmatrix | Release-Abnahme, Befund prüfen |

## Fail-closed für echte QGIS-Testläufe

Die Integrationstests überspringen QGIS-abhängige Fälle nur, wenn die Umgebung
explizit **keine QGIS-Laufzeit** erwartet. Bei echten QGIS-Läufen unbedingt
`CMD_REQUIRE_QGIS=1` setzen. Fehlgeschlagene Imports müssen dann den Testlauf
abbrechen statt als Skip gezählt zu werden. Zusätzlich wird ein ausdrücklicher
Import- und GUI-Smoke-Test benötigt (nicht allein QGIS-Stubs verwenden).

Beispiel in einer QGIS-Python-Umgebung:

```bash
CMD_REQUIRE_QGIS=1 QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests/integration -v
```

Unter Windows die Variablen zuvor im entsprechenden Terminal setzen und den
bestehenden `run_integration_tests.bat`-Runner benutzen.

## Freigabekriterien

1. Kein fehlgeschlagener statischer Test und keine unklar übersprungenen QGIS-Tests.
2. GeoTIFF, PNG, JPEG, VRT, MBTiles: mindestens ein kontrollierter Erfolgsfall;
   Fehler/Abbruch und vorhandene Ausgabedatei gesondert prüfen.
3. Ausdehnungswahl: Canvas, manuelle Koordinaten, Zeichnen und CRS-Wechsel.
4. Reprojektion und Maßstabstreue bei WMS, einschließlich Geo-Referenzierung.
5. Tatsächliche QGIS 3/4 GUI- und Exportprüfung, bevor metadata.txt 4.x zusagt.
6. Keine technischen Fehler oder fehlenden Ergebnisse in Pflicht-Reports; Webdienst-Hash-Drift
   anhand von Bildinhalt, Geometrie, CRS und externen Änderungen bewerten.
7. Validierte Versionen und Datum der erfolgreichen Laufzeitprüfung dokumentieren.

## CI-Strategie

GitHub-gehostete Linux-Runs für Python/Package-Prüfung und eine
QGIS-3/4-Docker-Matrix. Zusätzlich läuft
`.github/workflows/windows-qgis.yml` als native Windows-Matrix mit
QGIS 3.44.15 (`conda-forge/label/qgis_ltr`) und QGIS 4.2.3
(`conda-forge`) und Python 3.12.
Die frühere **self-hosted** Windows-CI bleibt archiviert;
die neue Windows-CI ist unabhängig davon nutzbar.
Keine automatische Release-Veröffentlichung.

## Automatische QGIS-Runtime-Matrix

Der GitHub-Workflow `.github/workflows/ci.yml` nutzt explizite Docker-Tags:

- QGIS 3.44.15 (Ubuntu Noble, Qt5)
- QGIS 4.2.3 (Ubuntu Resolute, Qt6)

Jeder Job setzt `CMD_REQUIRE_QGIS=1`, prüft QGIS- und Qt-Hauptversionen,
lädt das vollständige Plugin via `classFactory` und führt anschließend die
lokalen Raster-Smoke-Tests, QImage-Speichertests, MBTiles-Erfolgs-/Abbruchtests
und den echten Qt-/QGIS-Dialogtests aus. Details: [EXTENT_SELECTION.md](EXTENT_SELECTION.md). Importfehler müssen den Job abbrechen.
Ein roter QGIS-4-Job bedeutet bis zur vollständigen Migration eine echte
Kompatibilitätslücke, **keinen Grund, Tests zu überspringen**.
Die Docker-Tags sind versionsfest, aber nicht auf Image-Digests fixiert;
Digest-Pinning kann bei Bedarf ergänzend erfolgen; die verwendeten GitHub Actions
sind bereits auf vollständige Commit-SHAs fixiert.

## MBTiles-Dateisicherheit und temporäre Arbeitsdateien

MBTiles wird bevorzugt in einem geeigneten lokalen Benutzer-Temp-Verzeichnis
als SQLite-Datei aufgebaut. Die Auswahl nutzt die etablierte QGIS-Heuristik
`QgsFileUtils.pathIsSlowDevice()`. Falls das lokale Temp ungeeignet ist oder
die grob geschätzte Speicherreserve fehlt, erfolgt der Fallback **vor Beginn
des Exports** auf das bisherige Staging im Zielverzeichnis.

Nach erfolgreichem SQLite-Commit und dem **Schließen** der Datenbank werden
fertige Dateien gegebenenfalls in das Staging auf dem Ziellaufwerk kopiert
bzw. dort umbenannt. Erst danach wird die einzelne MBTiles-Datei mit
`os.replace()` auf demselben Dateisystem veröffentlicht. Bei Fehler/Abbruch
vor diesem Schritt bleibt die vorhandene Datei unverändert. Für Raster/VRT
gilt dasselbe Arbeitsverzeichnis-Prinzip mit bestehendem mehrdateibasiertem
Rollback; siehe [EXPORT_STAGING.md](EXPORT_STAGING.md).

Automatisiert geprüft sind Datenbank-Schema, lokale Temp-Erzeugung,
Transfer-Fehler, Dateierhaltung beim Abbruch, Dateiersetzung im Erfolgsfall
und reale QGIS-3/4-End-to-End-Exporte. Die Windows-Matrix enthält zusätzlich
Staging-/Recovery-Regressionstests. Dies ist **keine** Garantie für
Stromausfall-Dauerhaftigkeit (Filesystem-Sync) oder reale SMB-Ausfälle.

Nachweise:
[Windows-QGIS-3/4-CI #44295236004](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44295236004)
und
[CI auf main #44296095045](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44296095045).

## Extent-/Dialog-Regression

Die QGIS-Matrix enthält `test_extent_dialog.py` mit echtem
`QgsMapCanvas` und synthetischen Qt-Mausereignissen. Abgedeckt sind
Canvas-Reset, manuelle Ausdehnung über öffentliche API, Profil-Reimport,
CRS-Wechsel, wiederholtes Zeichnen und Abbruch durch Werkzeugwechsel.
Das ist kein Beleg für die vollständige Windows-Desktop-Interaktion oder
für lokalisierte manuelle Texteingabe; beides bleibt Release-Gate.
Siehe [Architektur und Historie der Ausdehnungsauswahl](EXTENT_SELECTION.md).

## Private Koordinatenfelder und Zahlenformate

Die Dialog-Matrix prüft zusätzlich die eindeutige Zuordnung der vier
QGIS-internen `QLineEdit`-Objekte, echte X-Koordinateneingabe,
fehlende/umbenannte Objektnamen, die selbständige Anzeigeaktualisierung
durch die öffentliche QGIS-API und beide gemischten Zahlformate
(`1.234,50` und `1,234.50`).
Die gesamte Feldanalyse ist in [EXTENT_SELECTION.md](EXTENT_SELECTION.md)
dokumentiert. Interaktive Tastatureingabe mit aktivierter deutscher
Windows-Locale bleibt Teil der noch offenen Desktop-Abnahme.

## Speicherarme MBTiles-Tileplanung

`build_mbtiles_plan()` ermittelt die Anzahl der Kacheln über
Integer-Arithmetik, ohne Kacheln vorab zu instanziieren. `MbtilesPlan.tiles`
liefert bei jedem Zugriff einen neuen Iterator, der `MbtilesTile` und
`QgsRectangle` nur für die aktuell verarbeitete Kachel erstellt.
Die frühere Tupel-/Index-Schnittstelle wird damit bewusst durch Iteration
ersetzt; der Exporter verarbeitet diese Daten bereits sequenziell.
Abbruchprüfungen erfolgen im Exportpfad vor jedem Rendervorgang.

Die Unit-Regression prüft einen weltumspannenden Plan bis Zoom 22
(trillionenfacher Kachelbestand), ohne die Iteration auszuschöpfen,
außerdem deterministische Wiederholung, Reihenfolge und Fortschritt.
Die QGIS-3/4-Matrix prüft weiterhin reale MBTiles-End-to-End-Exporte.

**Grenze:** Streaming begrenzt nur den Speicherbedarf des *Plans*.
Rechenzeit, Dateigröße und Renderaufwand sehr großer Exporte bleiben hoch;
eine harte Größen- oder Zeitbegrenzung ist derzeit nicht vorgesehen.

## MBTiles-Aufwandswarnung und Bestätigung

Vor dem Start der MBTiles-Ausgabe berechnet die GUI die tatsächlichen
WGS84-Grenzen mit demselben Transformationspfad wie der Exporter. Der
Kachelplan wird nur gezählt, nicht materialisiert. Für die komprimierte
PNG-Datenmenge wird ein **grober Referenzwert von 50 KiB je 256×256-Kachel** angesetzt.

| Stufe | Kachelzahl oder geschätzte Datenmenge | Verhalten |
| --- | --- | --- |
| Normal | unter 10.000 und unter 1 GiB | gewöhnliche Exportbestätigung |
| Groß | ab 10.000 oder ab 1 GiB | deutlicher Hinweis in der MBTiles-Vorschau |
| Extrem | ab 100.000 oder ab 10 GiB | zusätzliche ausdrückliche Ja/Nein-Bestätigung |

Die Schätzung skaliert den Referenzwert quadratisch mit der konfigurierten Kachelgröße.
Die Stufengrenzen sind als Konstanten in `core/mbtiles.py` definiert,
keine technischen Limits und keine Aussage zur tatsächlich benötigten
Dauer oder Dateigröße. Bei `extreme` ist **Nein** vorausgewählt.
Diese Bestätigung lässt sich auch dann nicht überspringen, wenn
`CustomMapDownloader/confirm_export` für normale Exportdialoge
deaktiviert ist. Der `Do not ask again`-Schalter wird in diesem Fall
nicht angeboten. Für normale Exporte bleibt das bisherige Verhalten
erhalten.

Der Regressionsumfang enthält Unit-Tests an beiden Schwellen und
QGIS-3/4-Integrationstests für die obligatorische Bestätigung und die
weiterhin gültige Deaktivierung normaler Bestätigungen.
Eine große Datenmenge allein verbietet den Export ausdrücklich nicht.

## Automatische Windows-QGIS- und lokale OGC-Tests

Die PR-gebundene Windows-Matrix verwendet QGIS 3.44.15 und 4.2.3
aus conda-forge. Sie prüft die reale Qt-/PyQGIS-Laufzeit einschließlich
Dialog, Raster-/VRT-/MBTiles-Export, Staging/Recovery und lokale
WMS-/WMTS-Dienste. Die Linux-Matrix prüft dieselben QGIS-Hauptversionen
in Containern. Importfehler dürfen nicht als Skips durchgehen.

Die reproduzierbaren lokalen Server für
`tests/integration/test_local_wms.py` und
`tests/integration/test_local_wmts.py` lauschen auf `127.0.0.1`:
WMS 1.3.0 mit GetCapabilities/GetMap und WMTS 1.0.0 mit
GetCapabilities/GetTile. Sie verwenden **keine amtlichen Internetdienste**.
Die öffentliche Live-Szenariomatrix ist bewusst getrennt.

Für die genauen Testkommandos und Konfigurationsfelder siehe
[Integrationstests](../tests/integration/README.md);
für datierte CI-Nachweise siehe
[VALIDATION_STATUS.md](VALIDATION_STATUS.md).
Die vorherige Self-hosted-Windows-CI wurde außer Betrieb genommen.
Die aktuelle Windows-Matrix ist nicht mit der offiziellen
OSGeo4W-/Standalone-Desktop-Abnahme gleichzusetzen.

## Amtliche Live-WMS-/WMTS-Prüfung (opt-in)

Die Workflows `.github/workflows/live-ogc.yml` und
`.github/workflows/live-scale-matrix.yml` werden ausschließlich
explizit bzw. durch freigegebene PR-Marker ausgeführt. Sie nutzen
amtliche WMS-/WMTS-Dienste; die reguläre CI bleibt davon unabhängig.

WMS-Szenarien können über `[run-live-wms:basemap_gray_tif]`,
der echte basemap.de-WMTS über `[run-live-wmts]` und die
Maßstabsmatrix über `[run-live-scale]` ausgelöst werden.
Die technischen Gates lehnen fehlende Daten, falsche Maße,
ungültige Exporte und Prozessfehler ab. Historische Datei-Hash-
Abweichungen bleiben dagegen **advisory**.

Verbindliche Interpretation: [OGC_TEST_POLICY.md](OGC_TEST_POLICY.md).
Konfiguration und manuelle Aufrufe:
[Integrationstests](../tests/integration/README.md).
Datierte Nachweise einschließlich wechselnder WMTS-Pixelhashes:
[VALIDATION_STATUS.md](VALIDATION_STATUS.md).

## Rasterpixel und GeoTIFF-Metadaten getrennt vergleichen

Für amtliche Live-WMS-Szenarien liefert `raster_diagnostics` ab sofort
drei unabhängige SHA-256-Fingerprints:

- `file_sha256`: vollständige GeoTIFF-Datei (abhängig von Encoder,
  Kompression, Tiff-Tags und eventuell Karteninhalt)
- `pixel_sha256`: tatsächlich durch GDAL dekodierte Rasterbandwerte,
  einschließlich Bandreihenfolge, Banddatentypen und Rasterdimensionen;
  blockweise eingelesen ohne vollständige Rasterkopie im Arbeitsspeicher
- `georef_sha256`: Projektion (WKT), GeoTransform, Dimensionen und GCP-Anzahl

Der Bericht enthält außerdem GDAL-Version, TIFF-Metadaten,
Bildstruktur und bandbezogene Eigenschaften. Pixel- und
Georeferenzierungs-Hashes sind **keine** Ersatzwerte für den
vollständigen Datei-Hash; sie erlauben eine genauere Ursachenanalyse.

Zur lokalen Untersuchung einer vorhandenen GeoTIFF-Datei:

```powershell
python scripts/raster_diagnostics.py .\export_aktuell.tif
```

Wenn die ursprünglich geprüfte Referenz-Datei noch vorhanden ist:

```powershell
python scripts/raster_diagnostics.py .\export_aktuell.tif --reference .\export_alt.tif
```

Ergebnis: `identical`, `file_encoding_or_metadata_only`,
`raster_samples_changed` oder `georeference_changed`.
Bei kombinierten Änderungen (z. B. andere Pixel **und** andere
Georeferenzierung) sind zusätzlich die einzelnen
`pixel_equal`-/`georef_equal`-Felder zu beachten.
Die alte Soll-GeoTIFF-Datei kann nicht aus ihrem bloßen SHA-256
rekonstruiert werden. Für die im März 2026 gespeicherten Referenzen
liegen bisher nur **Dateihashes**, keine Pixel-/Georeferenzierungsdaten vor.
Ohne ein solches Alt-Raster ist eine eindeutige historische
Ursachenzuordnung nicht möglich.

