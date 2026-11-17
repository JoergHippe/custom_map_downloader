# Teststrategie und Freigabekriterien

Stand: 2026-11-17. Dieses Dokument ist die Quelle für geplante QGIS-Kompatibilitätsprüfungen;
[VALIDATION_STATUS.md](VALIDATION_STATUS.md) enthält historische Messwerte.

## Status

- Metadata-Baseline: QGIS >= 3.34; **QGIS 4.x noch nicht freigegeben**.
- Der letzte belegte vollständige Windows/QGIS-Bericht stammt vom 2026-03-14 und
  deckt Änderungen aus April 2026 nicht ab.
- Linux-QGIS-3/4-Laufzeittests auf dem Entwicklungsbranch bestanden; der vollumfängliche Windows-/Webdienst-Freigabetest steht weiter aus.

## Prüfebenen

| Ebene | Umgebung | Gate |
| --- | --- | --- |
| Statisch | Python 3.12, Ruff, Black | Pflicht bei PR und Push |
| Unit | Python ohne QGIS, unittest mit Stubs | Pflicht bei PR und Push |
| Integration | QGIS 3 und 4, echte Python-Bindings, ohne Netz | Pflicht vor 4.x-Freigabe |
| Windows GUI | Lokale QGIS-Installation, Qt-Dialog/Canvas | Pflicht vor Release |
| Netzwerk | Reproduzierbare amtliche WMS-Szenarien | Pflicht vor Release, Befund prüfen |

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
6. Keine ungeklärte Abweichung in Pflicht-Reports; Webdienst-Hash-Drift
   anhand von Bildinhalt, Geometrie, CRS und externen Änderungen bewerten.
7. Validierte Versionen und Datum der erfolgreichen Laufzeitprüfung dokumentieren.

## CI-Strategie

GitHub-gehostete Linux-Runs für statische Checks, Unit-Tests und Package-Prüfung;
QGIS-Linux-Matrix mit offiziellen QGIS-Docker-Images für 3.x und 4.x. Die archivierte selbstgehostete Windows-CI bleibt vorerst inaktiv;
Windows-E2E werden vor Releases lokal ausgeführt. Kein automatischer Release.

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

## MBTiles-Dateisicherheit

MBTiles wird zunächst als temporäre SQLite-Datei **im Zielverzeichnis** geschrieben.
Erst nach erfolgreichem Commit und Schließen der Verbindung erfolgt
`os.replace` auf das endgültige Ziel. Bei Fehler/Abbruch bleibt eine bestehende
Datei unverändert; das temporäre Verzeichnis wird entfernt.

Automatisiert geprüft werden Datenbank-Schema, Dateierhaltung im Fehlerfall,
Dateiersetzung im Erfolgsfall sowie echte QGIS-3/4-End-to-End-Szenarien mit
lokaler Vektorebene (keine Netzabhängigkeit). Diese Garantie gilt für normale
Prozessfehler und Abbrüche; eine Aussage zur Stromausfall-Dauerhaftigkeit
(Filesystem-Sync) wird damit nicht getroffen.

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
