# Export-Staging: lokales Benutzer-Temp und sichere Veröffentlichung

Status: **geplant, nicht implementiert** (18.11.2026).
**Architekturentscheidung:** Temporäre Arbeitsoperationen werden grundsätzlich
im lokalen Benutzer-Temp-Verzeichnis bevorzugt, unabhängig davon, ob das
Ausgabeziel lokal oder im Netzwerk liegt. Die bisher nur für Netzlaufwerke
vorgesehene Sonderstrategie wird dadurch ersetzt.

## Aktueller Implementierungsstand

Raster- und VRT-Ausgaben werden derzeit im temporären Verzeichnis **auf dem
Zielmedium** vorbereitet. MBTiles besitzt eine separate Staging- und atomare
Veröffentlichungslogik. Diese vorhandenen Abläufe bleiben bis zur späteren,
testgesicherten Umstellung unverändert.

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

## QGIS-Konvention

QGIS Processing verwendet für Zwischenergebnisse typischerweise einen
temporären Arbeitsbereich; entsprechende API-Beispiele sind
`QgsProcessingUtils.tempFolder()` und `generateTempFilename()`.
Das Plugin ist **kein Processing-Algorithmus**, daher ist die Python-
Standardbibliothek `tempfile` für eigenständig kontrollierte
Arbeitsverzeichnisse vorzuziehen. QGIS-Processing-Temporärpfade müssen
nicht zwingend übernommen werden.

## Vor Umsetzung verpflichtend prüfen

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

## Abgrenzung und Entscheidungsvorbehalt

Die bestehende MBTiles-Transaktion bleibt bis zur gesonderten technischen
Bewertung unverändert. Ziel ist auch dort **grundsätzlich** lokales
Erzeugen der temporären SQLite-Datei, aber nur bei nachgewiesener
Korrektheit und sinnvoller Performance.

Vor der Implementierung Fallback-Policy, Platzreserve und mögliche
Schwellenwerte anhand der Testergebnisse konkretisieren. Keine große
Neustrukturierung und keine generelle zweite Kopie für lokale Kleinexporte,
wenn eine sichere direkte Veröffentlichung auf demselben Medium möglich ist.
