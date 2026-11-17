# TODO – Custom Map Downloader

Aktueller, bereinigter Backlog. Nur noch tatsächlich offene Themen.

## Hohe Priorität

- [x] Fail-closed-Integrationstests mit echter QGIS-3/4-Runtime nachgewiesen.
- [ ] QGIS 3/4-Kompatibilitätsmatrix auf realen Laufzeiten validieren, Qt6-Fundstellen beheben.
- [ ] QGIS-Integrationstests nach April-Änderungen erneut durchführen (einschließlich MBTiles und Dialog).
- [x] MBTiles-Ausgabe atomar im Zielverzeichnis bereitstellen; Abbruch- und Ersetzungstests unter QGIS 3/4.
- [x] QImage-Speicherkonvertierung mit eigenen NumPy-Puffern unter Qt5/Qt6 testen.
- [ ] MBTiles-Tileplanung für sehr große Ausschnitte ohne hohe Speichervorbelegung begrenzen/streamen.
- [ ] Komplexe QGIS-Extent-Widget-Heuristik durch öffentliche APIs ersetzen, wo möglich.
- [x] CI mit begrenztem Scope reaktiviert und grüne QGIS-3/4-Läufe nachgewiesen.

- Weitere echte QGIS-End-to-End-Netztests für reproduzierbare WMS-/XYZ-Szenarien ergänzen.
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
