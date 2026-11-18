# Export-Staging: lokales Benutzer-Temp und sichere Veröffentlichung

Status: **geplant, nicht implementiert** (18.11.2026).
Die aktuell implementierte Strategie steht unter
[Raster and VRT file safety](RELEASING.md#raster-and-vrt-file-safety):
Raster-/VRT-Ausgaben werden derzeit in einem temporären Verzeichnis
**auf dem Zielmedium** vorbereitet. MBTiles besitzt eine separate
Staging-/Veröffentlichungslogik und bleibt zunächst unverändert.

## Ziel und Motivation

Bei einem SMB-/Netzlaufwerk können wiederholte GDAL-Schreibzugriffe,
Kachelanlage und Metadatenoperationen merkliche Netzwerklatenz verursachen.
Für solche Ziele ist zu prüfen, ob **lokales Rendern in das Temp-Verzeichnis
des angemeldeten Benutzers** und anschließendes Übertragen der fertigen
Dateien die Gesamtlaufzeit reduziert.

**Nicht voraussetzen**, dass die lokale Variante grundsätzlich schneller
ist: Die vollständige zusätzliche Übertragung, das Ziellaufwerk, der
Dateiumfang und die Anzahl der VRT-Kacheln beeinflussen das Ergebnis.

## Vorgesehene Strategie

- **Lokales Ziel:** Weiterhin Staging auf dem Zielmedium; keine zusätzliche
  vollständige Dateikopie.
- **Erkanntes Netz-/UNC-Ziel:** Zunächst lokal in einem eigenen,
  eindeutig benannten Verzeichnis unter dem Benutzer-Temp erzeugen
  (`tempfile.gettempdir()` als möglicher Ausgangspunkt; tatsächliches
  Dateisystem und verfügbare Kapazität prüfen).
- **Danach für Netz-Ziele:** Fertige Raster, Sidecars oder VRT samt Kacheln
  kontrolliert in ein separates Staging-Verzeichnis **auf dem Zielmedium**
  kopieren; erst nach vollständigem Kopieren dort veröffentlichen.
- **Unbekannter Laufwerkstyp:** Konservativ das bisherige Ziel-Staging
  verwenden; nicht aus Laufwerksbuchstaben oder Pfadnamen auf SMB schließen.
  Erkennung unter Windows gegebenenfalls über systemeigene Laufwerks-APIs
  (UNC und verbundene Netzlaufwerke) gesondert prüfen.
- **MBTiles:** Vorhandenes atomisches Ersetzen zunächst nicht ändern.
  Eine lokale Render-Optimierung nur bei nachgewiesenem Performancegewinn.

Die Auswahl soll automatisch erfolgen, ohne zusätzliche UI-Option.
Keine Veränderung der bestehenden Render-, Georeferenzierungs-,
VRT- und GDAL-Ausgabeformate allein wegen des Staging-Orts.

## Sicherheits- und Fehleranforderungen

1. `os.replace` ist **nicht** als atomarer Transfer über verschiedene
   Dateisysteme verwendbar. Zwischen lokalem Temp und Ziel-Staging
   müssen die Daten **kopiert** werden. Ersetzen/Backup/Rollback findet
   ausschließlich auf dem Zielmedium statt.
2. Lokaler freier Speicher und Zielkapazität sollen vorab konservativ
   geprüft werden; Größenabschätzungen bei komprimierten Formaten und
   MBTiles sind unsicher. Kein stilles Risiko vollständiger
   Benutzer-Temp- oder Systemlaufwerke.
3. Wenn lokaler Speicher nicht reicht: konfigurationsfreie,
   nachvollziehbare Rückfallstrategie auf Ziel-Staging **oder**
   verständlicher Abbruch. Kein stiller Wechsel nach begonnenem
   unvollständigem Export; diese Policy vor Implementierung präzisieren.
4. Abbruch und Ausnahmen während Rendering, Kopieren und Veröffentlichen
   müssen behandelte Fehler sein. Existierende Zieldateien bleiben bis
   zur Veröffentlichung unberührt; partielle Kopien im Ziel-Staging
   dürfen nicht als Erfolg gelten.
5. Nach erfolgreichem Kopieren Existenz, erwartete Dateianzahl und
   Dateigrößen prüfen; falls erforderlich zusätzliche Integritätsprüfung
   (z. B. Prüfsummen) begründet einsetzen. VRT-Referenzen auf lokale
   Temp-Pfade sind unzulässig; Kacheln müssen nach der Veröffentlichung
   relativ erreichbar bleiben.
6. **VRT-Dateisätze sind nicht als Gesamtheit atomar.** Kacheln und
   Sidecars zuerst, VRT zuletzt; bei Fehlern Rückrollversuch und
   Wiederherstellungsdateien erhalten. Bereits geöffnete VRTs und
   Windows-Dateisperren gesondert beachten.
7. Temp-Verzeichnisse kontrolliert aufräumen; Umgang mit Resten nach
   Prozessabsturz und gesperrten Dateien untersuchen. Keine globale
   Bereinigung fremder Benutzer-Temp-Dateien.
8. Bestehende Dateien auf dem Ziel nur nach erfolgreichem Transfer
   ersetzen; `overwrite`-Semantik, Ausgabenamen und QGIS-Layer-Konflikte
   unverändert berücksichtigen.

## Vor der Implementierung: Mess- und Testmatrix

- **Ziele:** lokale SSD, SMB-UNC-Pfad, gemapptes Netzlaufwerk;
  nach Möglichkeit verschieden schnelle Netz-/Serverkombinationen.
- **Formate:** kleine und große GeoTIFFs, gekacheltes PNG/JPEG,
  VRT mit vielen Kacheln und Sidecars. MBTiles als separater Vergleich.
- **Messwerte:** gesamte Exportdauer einschließlich Netzwerktransfer
  und Veröffentlichung, Renderdauer, Kopierdauer, Datentransfermenge,
  Anzahl Dateien, Peak-Belegung lokal/auf Ziel.
- **Fehlerfälle:** zu wenig Platz im lokalen Temp und Ziel, SMB-Verlust
  während Kopieren/Veröffentlichen, Abbruch, gesperrte Zieldatei,
  bestehende Ausgabe, VRT-Referenzen und Rollbackfehler.
- **Regression:** QGIS 3/4 unter Linux und Windows; abschließender
  sichtbarer Test mit der offiziellen Windows-QGIS-/OSGeo4W-Distribution.

## Entscheidungsvorbehalt

Erst nach Vergleichsmessungen Schwellenwerte, Fallback-Policy und
Speicherreserve festlegen. Keine feste Dateigrößengrenze ohne Datenbasis.
Eine weitere Abstraktionsschicht ist nur gerechtfertigt, wenn sie
die bestehende `core/output_transaction.py` sinnvoll ergänzt und
nicht eine zweite konkurrierende Veröffentlichungslogik erzeugt.
