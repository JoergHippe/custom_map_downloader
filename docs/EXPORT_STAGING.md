# Export-Staging: lokales Benutzer-Temp und sichere Veröffentlichung

Status: **implementiert auf Feature-Branch, Validierung ausstehend**
(18.11.2026). Die Strategie bevorzugt das lokale Benutzer-Temp für
rechenintensive Arbeitsdateien, ohne bei jedem lokalen Export eine
vollständige Zusatzkopie zu erzwingen.

## Implementierter Ablauf

- `QgsFileUtils.pathIsSlowDevice()` prüft, ob das Ziel vermutlich langsam
  ist und ob das Benutzer-Temp als Arbeitsmedium geeignet erscheint.
  Bei gleichem Dateisystem wird lokales Arbeiten ebenfalls bevorzugt,
  da die fertigen Dateien ins Ziel-Staging **umbenannt** werden können.
- Bei geeigneten Bedingungen wird mit `tempfile.mkdtemp()` ein
  an den Export gebundenes Arbeitsverzeichnis im Benutzer-Temp angelegt.
  Andernfalls wird das bisherige **Ziel-Staging** verwendet.
- Die verfügbare lokale Kapazität wird vor Beginn anhand einer
  konservativen Größenabschätzung plus Reserve überprüft. Nicht
  verfügbare Temp-Verzeichnisse führen vor dem Rendern zum Fallback.
- Bei unterschiedlichen Dateisystemen werden fertige Dateien in
  abbrechbaren Blöcken ins **Ziel-Staging** kopiert und auf vollständige
  Dateigröße geprüft; niemals direkt über ein Netzlaufwerk in die
  bestehenden Zieldateien hineinkopiert.
- Die bisherige VRT-Backup-/Rollback-Logik veröffentlicht Kacheln und
  Sidecars zuerst, dann die VRT. Eine VRT-Gruppe ist weiterhin
  **nicht vollständig atomar**.
- MBTiles verwendet denselben Temp-/Transfer-Baustein; die
  geschlossene SQLite-Datenbank wird danach weiterhin mit
  **einem** `os.replace()` auf dem Ziellaufwerk veröffentlicht.

**Einschränkung:** `pathIsSlowDevice()` ist eine QGIS-Heuristik und
garantiert weder ein lokales Temp-Laufwerk noch einen Performancegewinn.
Bei unbekannten Geräten wird vorsichtig auf das bisherige Ziel-Staging
zurückgegriffen. Große Raster können trotz Vorabschätzung lokale
Speicherengpässe erzeugen. Windows-SMB-Messwerte und Dateisperren müssen
an einer echten Umgebung gesondert geprüft werden.

## Zielarchitektur

1. **Arbeitsbereich:** Rechenintensive und vorläufige Vorgänge (Rasterrendering,
   GDAL-Reprojektion, gekachelte PNG/JPEG-Ausgabe, VRT-Zusammenstellung,
   temporäre GeoTIFFs sowie perspektivisch SQLite/MBTiles-Erzeugung)
   bevorzugt in einem eindeutigen, kontrolliert verwalteten Verzeichnis
   im **lokalen Benutzer-Temp** durchführen, etwa mit
   `tempfile.TemporaryDirectory()`.
2. **Temp-Pfad verifizieren:** `tempfile.gettempdir()` liefert nicht garantiert
   einen lokalen Datenträger. Umgeleitete TEMP-/TMP-Verzeichnisse und
   Laufwerkskonfigurationen berücksichtigen; keine unnötige Abhängigkeit
   von QGIS Processing einführen.
3. **Ziel-Staging:** Fertige Dateien ausschließlich auf dem endgültigen
   Zieldateisystem zur Veröffentlichung bereitstellen. Wenn Arbeits- und
   Zielbereich nachweislich auf **demselben Dateisystem** liegen, direkt
   verschieben statt vollständig zu kopieren, soweit sicher und sinnvoll.
   Andernfalls kopieren und erst nach erfolgreichem Transfer veröffentlichen.
4. **Veröffentlichung:** Vorhandene Ergebnisse möglichst erhalten, solange
   die neuen nicht vollständig erzeugt und übertragen sind. Bestehende
   Backup-/Rollback-Strategie in `core/output_transaction.py` weiterverwenden;
   keine zweite konkurrierende Implementierung einführen.
5. **Automatik:** Keine zusätzliche Benutzereinstellung vorsehen.
   Kleinere lokale Exporte dürfen aus nachgewiesenen Effizienzgründen einen
   direkten, sicheren Ziel-Staging-Pfad wählen; das ist eine Optimierung,
   keine separate Architektur für Netzlaufwerke.

## Daten- und Fehlersicherheit

- `os.replace()` ist **nicht** als atomare Operation über Dateisystemgrenzen
  verfügbar. Sichere Umbenennungen/Ersetzungen deshalb ausschließlich
  auf dem Zieldateisystem vornehmen.
- Lokale und Ziel-Speicherkapazitäten vorab konservativ prüfen; Reserve
  und Schwellenwerte erst anhand realer Messungen festlegen. Große Raster
  und viele VRT-Kacheln können erhebliche Temp-Belegung verursachen.
- Bei ungeeignetem lokalen Temp, zu wenig Speicher oder fehlendem Zugriff
  kontrolliert auf Ziel-Staging zurückfallen **oder** verständlich abbrechen.
  Kein unbemerkter Fallback nach bereits teilweise erfolgtem Export.
- Kopieren abbrechbar und fehlertolerant gestalten; Teilkopien niemals
  veröffentlichen. Datei- und Sidecar-Vollständigkeit vor dem Ersetzen
  prüfen, bei Bedarf Integritätschecks ergänzen.
- VRT-Kachelpfade müssen auch nach Umzug relativ und gültig sein.
  **VRT-Dateisätze bleiben als Gruppe nicht atomar:** Kacheln und Sidecars
  zuerst, VRT zuletzt; bei Fehlern Rückrollversuch. Parallel lesende QGIS-
  Instanzen und Windows-Dateisperren gesondert berücksichtigen.
- Eigene temporäre Arbeitsverzeichnisse aufräumen, auch nach Abbruch
  und Fehlern. Prozessabstürze, gesperrte Dateien und gegebenenfalls
  verbleibende Recovery-Verzeichnisse behandeln; niemals fremde
  Benutzer-Temp-Dateien global bereinigen.
- Bestehende Benennungen, QGIS-Layer-Konfliktprüfung, Koordinatensysteme,
  Formatsemantik und Exportausdehnungen nicht verändern.

## Abgleich mit etablierten QGIS-/GDAL-Technologien (18.11.2026)

Die folgenden dokumentierten APIs wurden gezielt für QGIS 3.44 und 4.2
verglichen. Keine eigene QGIS-Processing- oder Dateisystem-Bibliothek bauen.

| Vorhandene Technologie | Verwendung / Entscheidung |
| --- | --- |
| `QgsProcessingUtils.tempFolder()` / `generateTempFilename()` | QGIS-Processing-konforme, sitzungsbezogene Temp-Dateien; für Processing-Algorithmen passend, aber kein automatischer Vorteil für unser eigenständiges Plugin. Processing-Temp kann von Benutzereinstellungen beeinflusst sein und ist nicht garantiert lokal. |
| `tempfile.TemporaryDirectory()` / `tempfile.gettempdir()` | **Bevorzugt** für eindeutig besessene, zeitlich begrenzte Arbeitsverzeichnisse. Benutzer-Temp tatsächlich prüfen, da umgeleitete Profile und TEMP/TMP möglich sind. |
| Qt `QTemporaryDir` | Alternative mit ähnlicher Lebensdauerverwaltung; aktuell kein Grund, parallel zur Python-Standardbibliothek einen zweiten Mechanismus einzuführen. |
| `QgsFileUtils.pathIsSlowDevice(path)` | **Verwenden** als QGIS-eigene Heuristik für langsame/netzgebundene Speichermedien (seit QGIS 3.20; QGIS 3.44/4.2). Kein Beweis für ein anderes Dateisystem oder eine bestimmte Datenrate. |
| `QgsFileUtils.driveType(path)` | Optional zur Diagnose; kann auf nicht unterstützten Plattformen eine QGIS-Ausnahme auslösen. Keine eigene Windows-Laufwerkserkennung, solange die QGIS-API genügt. |
| `QgsFileUtils.sidecarFilesForPath()` | Für Datensatz-Nebenprodukte gezielt prüfen. Vorhandene Staging-Dateiliste bleibt für tatsächlich erzeugte Artefakte maßgeblich. |
| `QgsFileUtils.renameDataset()` | Kann GIS-Datensätze samt Sidecars umbenennen; ersetzt **keine** transaktionale Veröffentlichung von VRT + Kacheln und kein Backup/Rollback. Nicht pauschal einsetzen. |
| `QSaveFile` | Geeignet für einzelne Qt-seitig geschriebene Dateien, **nicht** als allgemeiner Ersatz für GDAL-Driver-Ausgaben und mehrteilige VRTs. Direktes Schreib-Fallback würde Atomarität aufgeben. |
| GDAL `/vsimem/` | Nur für kleine, begrenzte Zwischenraster; bei großen Exporten droht unnötiger RAM-Druck. Bestehende GDAL-Writer weiterverwenden. |
| `shutil.copyfile()` / `copy2()`, `os.replace()` | Bewährte Standardwerkzeuge für Transfers bzw. Umbenennung **innerhalb** des Zielfilesystems; keine Eigenentwicklung eines Kopierprogramms. Abbruch und Fehlerstatus prüfen. |

Referenzen:
[PyQGIS QgsProcessingUtils 3.44](https://qgis.org/pyqgis/3.44/core/QgsProcessingUtils.html),
[PyQGIS QgsFileUtils 3.44](https://qgis.org/pyqgis/3.44/core/QgsFileUtils.html),
[PyQGIS QgsFileUtils 4.2](https://qgis.org/pyqgis/4.2/core/QgsFileUtils.html),
[Qt QTemporaryDir](https://doc.qt.io/qt-6/qtemporarydir.html),
[Qt QSaveFile](https://doc.qt.io/qt-6/qsavefile.html),
[GDAL Virtual File Systems](https://gdal.org/en/stable/user/virtual_file_systems.html),
[Python 3.12 shutil](https://docs.python.org/3.12/library/shutil.html).

### Schlanke, generische Zielstruktur

**Nur zwei Verantwortlichkeiten**, bevorzugt in/bei der bestehenden
`core/output_transaction.py`, keine universelle Storage-Abstraktion:

1. **Arbeitsverzeichnis** verwalten: lokale Temp-Eignung prüfen,
   erzeugen, Dateinamen bereitstellen, beenden/aufräumen. Die
   eigentlichen GDAL-/QGIS-Exportfunktionen erhalten lediglich Pfade.
2. **Ergebnisse veröffentlichen**: tatsächlich erzeugte Datei-
   und Sidecar-Menge erfassen; ggf. von lokal nach Ziel-Staging kopieren;
   erst dann bestehende Zieldateien mit Backup/Rollback ersetzen.
   Fehlercodes, Recovery-Verhalten und Protokollierung wiederverwenden.

Die Unterscheidung **Scratch-Artefakt vs. veröffentlichungsreifer Dateisatz**
ist wichtiger als eine generische Laufwerk-/Netzwerk-Klassenhierarchie.
Für große Mehrdatei-Exporte (VRT) bleibt die Veröffentlichung als Ganzes
nicht atomar; es ist keine vollständige Transaktion wie bei einer Datenbank.

Die QGIS-Heuristik `pathIsSlowDevice()` kann zwischen direktem
Ziel-Staging (insbesondere schnelle lokale Ziellaufwerke) und
lokalem Arbeits-Staging mit späterem Transfer entscheiden. Die
prinzipielle Bevorzugung lokaler Temp-Arbeiten bleibt erhalten,
**ohne zwingend jeden lokalen Kleinexport doppelt zu schreiben**.
Eine pauschale Optimierung nach Dateiendung oder eine harte
Größenschwelle ist ohne Messungen nicht gerechtfertigt.

**Nicht verwenden:** pauschale globale Änderung von `TEMP`, `TMP`,
`CPL_TMPDIR` oder QGIS-Processing-Einstellungen für das Plugin.
Das könnte andere QGIS-Plugins, GDAL-Operationen und parallele
Exporte beeinflussen. Eigene explizite Arbeitsverzeichnisse vorziehen.

### Bereits festgestellte Testlücke unter Windows

`.github/workflows/windows-qgis.yml` prüft QGIS 3/4 aus
conda-forge und wird über Pull Requests bzw. manuelles
`workflow_dispatch` gestartet; **kein automatischer Push-Lauf
auf `main`**. Bereits geprüft werden Raster-/VRT-/MBTiles-
Exporte. **Zusätzlich benötigt** die spätere Umstellung
gezielte Windows-Dateisperr-, Recovery- und SMB-Tests.
Die conda-basierte CI ersetzt keinen sichtbaren Test mit einer
offiziellen Windows-QGIS-/OSGeo4W-Installation.

## Verbleibende Betriebs- und Performanceprüfung

- **Leistung:** lokale SSD, SMB-UNC und gemappte Netzlaufwerke;
  kleine und große GeoTIFFs, PNG/JPEG, VRT mit vielen Kacheln,
  MBTiles gesondert. Gesamtdauer einschließlich Rendern, Kopieren und
  Veröffentlichen gegen das bisherige Ziel-Staging messen.
- **Speicher:** freier Platz auf Arbeits- und Zielmedium,
  konservative Größenschätzung, Peak-Belegung und Fallback.
- **Dateisystem:** Prüfung, ob beide Verzeichnisse wirklich auf demselben
  Dateisystem liegen; keine Annahmen allein aus Laufwerksbuchstaben
  oder Pfadstrings.
- **Fehler:** Abbruch während Rendering/Kopie/Veröffentlichung,
  SMB-Unterbrechung, volles Laufwerk, vorhandene Dateien,
  Windows-Dateisperren, VRT-Referenzen und Rollback-Ausfälle.
- **Regression:** QGIS 3/4 unter Linux und Windows sowie sichtbarer
  Desktop-Test mit offizieller Windows-QGIS-/OSGeo4W-Installation.

## Grenzen der Implementierung

Die ursprüngliche MBTiles-Ein-Datei-Atomarität bleibt erhalten; die
Arbeitsdatei kann nun lokal erzeugt und ins Ziel-Staging übertragen
werden. Für Raster/VRT bleibt die vorhandene Rollback-Strategie erhalten.

Der Transfer ist über die bestehende `core/output_transaction.py`
implementiert: keine neue Storage-Schicht und keine Änderungen an globalen
TEMP-/GDAL-Umgebungsvariablen. Für die späteren Messungen bleiben
Gesamtdauer, realer Windows-Dateizugriff, SMB-Ausfälle und unzureichender
Speicher relevante offene Prüfpunkte; insbesondere wurde keine
Performancesteigerung ohne Messdaten behauptet.
