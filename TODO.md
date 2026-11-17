# TODO – Custom Map Downloader

Aktueller, bereinigter Backlog. Nur noch tatsächlich offene Themen.

## Hohe Priorität

- [ ] QGIS-Importfehler in Integrationstests bei aktivem Strict-Modus als Fehler behandeln (erste Absicherung implementiert; Runtime-Verifikation offen).
- [ ] QGIS 3/4-Kompatibilitätsmatrix auf realen Laufzeiten validieren, Qt6-Fundstellen beheben.
- [ ] QGIS-Integrationstests nach April-Änderungen erneut durchführen (einschließlich MBTiles und Dialog).
- [ ] MBTiles-Ausgabe gegen Verlust einer bestehenden Datei bei Fehler/Abbruch absichern.
- [ ] Speicherkonvertierung von QImage nach NumPy in Qt5/Qt6 robust machen.
- [ ] Komplexe QGIS-Extent-Widget-Heuristik durch öffentliche APIs ersetzen, wo möglich.
- [ ] CI mit begrenztem Scope reaktivieren und tatsächliche Testausführung nachweisen.

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
