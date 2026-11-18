# Temporäre Arbeitsdateien und sichere Veröffentlichung

**Stand:** 18.11.2026 – implementiert. Dieses Dokument beschreibt die
**Architektur und ihre Grenzen**. Testverfahren und Freigabekriterien:
[TESTING.md](TESTING.md); aktuelle Ergebnisse:
[VALIDATION_STATUS.md](VALIDATION_STATUS.md); noch offene Arbeiten:
[TODO.md](../TODO.md).

## Grundprinzip

- **Arbeitsphase:** Raster (GeoTIFF/PNG/JPEG), VRT samt Kacheln sowie
  MBTiles/SQLite werden bevorzugt im Benutzer-Temp-Verzeichnis erstellt.
  `QgsFileUtils.pathIsSlowDevice()` liefert eine *Heuristik* für langsame
  Zielmedien; die Lösung berücksichtigt außerdem das Dateisystem von
  Benutzer-Temp und Ziel. `tempfile` verwaltet die Arbeitsordner.
- **Fallback:** Ist das Temp-Medium als langsam erkannt, nicht zugänglich
  oder gemäß grober Schätzung nicht ausreichend frei, wird **vor**
  Renderbeginn im Ziel-Staging gearbeitet. Das ist kein dynamischer
  Wechsel während des Exports.
- **Transfer:** Liegen Arbeitsdateien und Ziel-Staging auf demselben
  Dateisystem, werden die fertigen Dateien umbenannt, ansonsten
  blockweise und abbrechbar kopiert. Teilkopien bleiben im
  Ziel-Staging, niemals unter dem veröffentlichten Zieldateinamen.
- **Veröffentlichung:** Erst vollständige Dateien auf dem Zielmedium
  werden veröffentlicht. MBTiles ersetzt die geschlossene SQLite-Datei
  mit einem einzigen `os.replace()`; für Raster und insbesondere
  VRT-Dateisätze gilt die vorhandene Backup-/Rollback-Strategie.
- **Keine globale Umstellung:** Das Plugin verändert weder `TEMP`,
  `TMP`, `CPL_TMPDIR` noch QGIS-Processing-Einstellungen.

Die generischen Dateisystemfunktionen befinden sich in
`custom_map_downloader/core/output_transaction.py`.
GDAL-Rendering, VRT-Erzeugung und MBTiles-Schreiben bleiben in
ihren bestehenden Modulen. **Keine separate Storage-Klassenhierarchie.**

## Vorhandene QGIS-/Python-Technologien

| Technologie | Einsatz und Abgrenzung |
| --- | --- |
| `QgsFileUtils.pathIsSlowDevice()` | QGIS-eigene Erkennung vermutlich langsamer Medien; kein zuverlässiger Nachweis für SSD, Netzlaufwerk oder unterschiedliche Dateisysteme |
| Python `tempfile` und `shutil` | Eigene, auf den Export begrenzte Temp-Verzeichnisse, Kapazitätsprüfung und Transfer |
| `os.replace()` | Sichere Einzeldateiersetzung **innerhalb** des Zielfilesystems; nicht über Dateisystemgrenzen |
| `QgsProcessingUtils.tempFolder()` | Für QGIS Processing sinnvoll, hier kein Bedarf für eine Processing-Abhängigkeit; auch dieser Ordner ist nicht zwingend lokal |
| `QgsFileUtils.renameDataset()` / `sidecarFilesForPath()` | Kandidaten für GIS-Dateisätze; ersetzen kein mehrdateibasiertes VRT-Backup/Rollback |
| Qt `QTemporaryDir` / `QSaveFile` | Keine zusätzliche Parallel-Implementierung nötig; `QSaveFile` ist kein generischer GDAL-Rasterwriter |
| GDAL `/vsimem/` | Allenfalls für kleine, begrenzte Zwischendaten – nicht pauschal für umfangreiche Exporte |

API-Referenzen:
[QGIS 3.44 QgsFileUtils](https://qgis.org/pyqgis/3.44/core/QgsFileUtils.html),
[QGIS 4.2 QgsFileUtils](https://qgis.org/pyqgis/4.2/core/QgsFileUtils.html),
[Python tempfile](https://docs.python.org/3/library/tempfile.html),
[Python shutil](https://docs.python.org/3/library/shutil.html),
[GDAL Virtual File Systems](https://gdal.org/en/stable/user/virtual_file_systems.html).

## Grenzen und Fehlerverhalten

- **Leistung:** Das lokale Temp kann selbst umgeleitet oder langsam sein.
  Rendern vor Ort spart potenziell viele SMB-Schreiboperationen, benötigt
  bei verschiedenen Dateisystemen aber einen vollständigen Transfer.
  Ein Geschwindigkeitsgewinn wurde **nicht** durch SMB-Messungen belegt.
- **Speicher:** Freier Platz wird konservativ aus einer groben
  Exportgrößenschätzung plus Reserve beurteilt, nicht garantiert.
  Kompression, temporäre GDAL-Dateien und große VRT-Sätze können
  davon abweichen.
- **VRT:** Kacheln/Sidecars werden zuerst, die VRT-Datei zuletzt
  veröffentlicht. Diese Dateigruppe ist **nicht insgesamt atomar**.
  Ein fehlgeschlagener Rollback kann einen manuell zu prüfenden
  Recovery-Ordner hinterlassen.
- **Abbruch/Fehler:** Vor der Veröffentlichung bleiben bestehende
  Zieldateien unberührt. Die Übertragung ist abbrechbar;
  fehlgeschlagene Kopien dürfen nicht als fertig veröffentlicht gelten.
  Windows-Dateisperren und SMB-Verbindungsabbrüche bedürfen eines
  separaten Praxistests.
- **Verwaiste Temp-Dateien:** Eigene Ordner werden im normalen
  Fehler-/Abbruchpfad aufgeräumt; nach Prozessabsturz können Reste
  verbleiben. Recovery-Daten dürfen nicht unkontrolliert gelöscht werden.

## Validierung und Releasegrenzen

Automatisch geprüft: Python-Regressionen, Linux QGIS 3/4 sowie
native Windows-conda-forge-QGIS-3/4-Läufe. Siehe
[VALIDATION_STATUS.md](VALIDATION_STATUS.md) für exakte Commits und
Workflow-IDs.

**Noch offen:** Abnahme mit offizieller Windows-QGIS-/OSGeo4W-
Installation und repräsentative SSD-/SMB-Vergleichsmessungen
einschließlich Kopierdauer, Dateisperren und echter
Netzwerkunterbrechungen. Verbindliche Prüfschritte stehen in
[TESTING.md](TESTING.md#manuelle-abnahme-windows-desktop-und-netzlaufwerk).
