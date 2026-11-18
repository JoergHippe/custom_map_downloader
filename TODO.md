# TODO – Custom Map Downloader

Aktueller, bereinigter Backlog. Nur noch tatsächlich offene Themen.

## Hohe Priorität

- [x] Fail-closed-Integrationstests mit echter QGIS-3/4-Runtime nachgewiesen.
- [x] QGIS 3.44/4.2 unter Linux und Windows mit echten Bindings und automatisierten Qt-Tests geprüft.
- [ ] Weitere offiziell unterstützte Versionen und die finale OSGeo4W-/Desktop-Distribution vor Freigabe prüfen.
- [x] QGIS-Integration für MBTiles, Qt-Canvas, Raster, lokales WMS und WMTS unter Windows/Linux automatisiert bestanden.
- [ ] Den breiten amtlichen WMS-Katalog vollständig erneut prüfen; Windows-Desktop-Bedienung der offiziellen Distribution gesondert bewerten.
- [x] MBTiles-Ausgabe atomar im Zielverzeichnis bereitstellen; Abbruch- und Ersetzungstests unter QGIS 3/4.
- [x] QImage-Speicherkonvertierung mit eigenen NumPy-Puffern unter Qt5/Qt6 testen.
- [x] MBTiles-Tileplanung speicherschonend iterieren und sehr große Pläne ohne Vorbelegung testen.
- [x] MBTiles-Aufwandswarnung und ausdrückliche Bestätigung bei extremen Kachelzahlen oder Dateigrößenschätzungen implementiert und QGIS-3/4-getestet.
- [x] QGIS-3/4-Dialogtests für Canvas-Reset, Profil, CRS-Wechsel und wiederholtes Zeichnen/Abbruch ergänzt; Profil-Ausdehnungsfehler behoben.
- [x] Mehrdeutige QGIS-Extent-Feldheuristik durch exakte, fehlertolerante Zuordnung ersetzt; direkte QLineEdit-Schreibzugriffe entfernt.
- [ ] Verbleibende QGIS-Extent-Fallbacks (`currentExtent()` und Textparsing) sowie Signal-/Polling-Bedarf nach Windows-/Locale-GUI-Tests bewerten; siehe docs/EXTENT_SELECTION.md.
- [x] CI mit begrenztem Scope reaktiviert und grüne QGIS-3/4-Läufe nachgewiesen.

- [x] Reproduzierbare WMS-/WMTS-End-to-End-Tests mit lokalen HTTP-OGC-Diensten unter Windows/Linux ergänzt.
- [x] Drei verschiedene amtliche WMS-Live-Szenarien unter QGIS 3/4 ausgeführt (BKG, basemap.de, NRW).
- [x] Live-TIF-Diagnose für Rasterpixel, Georeferenzierung und TIFF-Metadaten unter QGIS 3/4 eingeführt; basemap.de und NRW aktuell jeweils identisch.
- [x] Historische Hashabweichungen als Referenzhinweise statt automatischer Exportfehler behandeln; alte SHA-256-Baselines bleiben erhalten.
- [ ] Falls originale März-2026-GeoTIFF-Dateien wieder verfügbar sind, deren Pixel/Georeferenzierung/Metadaten optional vergleichen; kein Release-Blocker allein aufgrund alter Dateihashes.
- [x] Konfigurierte amtliche WMS-Pflichtmaßstabsmatrix (3 Fälle × 2 Maßstäbe) unter QGIS 3/4: alle zwölf Exporte erfolgreich.
- [x] Echter amtlicher basemap.de-WMTS-Live-Test mit GeoTIFF unter QGIS 3/4 ausgeführt.
- [ ] WMTS: Ursache wechselnder Pixel-/Dateihashes zwischen Live-Läufen prüfen; die Georeferenzierung ist identisch und die Ausgaben enthalten gültige Bilddaten.
- Export-Diagnostik optional noch stärker in der UI auswertbar machen.
- Release-Version und Changelog vor der nächsten Veröffentlichung sauber pflegen.

## Mittlere Priorität

- `core/exporter.py` weiter modularisieren, bis nur noch schmale Orchestrierung übrig bleibt.
- Zusätzliche Exportoptionen prüfen:
  - alternative GDAL-Kompressionen
  - optional reduzierte Farbtiefe / kleinere Dateien
- Troubleshooting-Doku mit konkreten Beispiel-Fehlerbildern erweitern.

## Niedrige Priorität

- Optionales Hintergrund-/Queue-Modell für nicht-modale Exporte evaluieren.
- Optional weitere UX-Hilfen im Dialog ergänzen:
  - expliziter Aspect-Ratio-Hinweis
  - zusätzliche Experteninfos für Raster-/Tile-Größen

## Geplante Erweiterung: Hinweise zur Dienstauflösung

Optionale, nachvollziehbare Auflösungs- und Maßstabsempfehlungen für Webkarten:

- WMS: Angaben `MinScaleDenominator`/`MaxScaleDenominator` aus
  `GetCapabilities` berücksichtigen, sofern verfügbar; als Darstellungsgrenzen,
  nicht als native Rasterauflösung kennzeichnen.
- Näherungsweise GSD bei WMS: `Maßstabsnenner × 0,00028 m`
  (OGC-Standardpixel), ausdrücklich nur als Orientierung.
- WMTS/XYZ: Stufen aus TileMatrixSet oder Zoom-Metadaten berücksichtigen.
- ArcGIS MapServer/TileServer: bei Verfügbarkeit `tileInfo.lods` verwenden.
- Empfehlungen transparent mit Quelle und Unsicherheit anzeigen; keine
  stillschweigende Änderung der gewählten GSD oder des Zielmaßstabs.
- Eine Aktion „Empfohlene Auflösung übernehmen“ erst nach Prüfung
  der Datenverfügbarkeit und des Benutzerablaufs erwägen.
