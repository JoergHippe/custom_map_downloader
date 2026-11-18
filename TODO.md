# Offene Aufgaben – Custom Map Downloader

Nur aktuell offene Aufgaben. Erledigte Arbeiten sind im
[Changelog](CHANGELOG.md) und den [Validierungsergebnissen](docs/VALIDATION_STATUS.md)
dokumentiert. Diese Liste begründet keine Release-Freigabe.

## Vor der nächsten Veröffentlichung

- [ ] Offizielle Windows-QGIS-/OSGeo4W-Desktop-Installation mit sichtbarer GUI
  prüfen: Ausdehnungswahl, manuelle Eingabe mit deutscher Locale,
  Zeichnen/Abbrechen, CRS-Änderungen und Profilwiederherstellung.
- [ ] Freizugebende QGIS-Versionen und Formatpfade (GeoTIFF, PNG, JPEG,
  VRT, MBTiles) am Release-Paket abnehmen.
- [ ] Breiten amtlichen WMS-Katalog erneut prüfen; technische Ausfälle strikt
  behandeln, historische Hashabweichungen gemäß
  [OGC-Teststrategie](docs/OGC_TEST_POLICY.md) nur als Hinweise.
- [ ] Version, Metadaten-Changelog und Freigabenachweise konsistent aktualisieren.

## Technische Prüfungen für spätere Codearbeiten

- [ ] QGIS-Extent-Fallbacks (insbesondere `currentExtent()` und privates
  Textparsing) sowie Polling-/Signalbedarf nach Desktop-/Locale-Tests kritisch
  prüfen; siehe [EXTENT_SELECTION.md](docs/EXTENT_SELECTION.md).
- [ ] Ursache der zwischen Live-Läufen schwankenden WMTS-Pixel- und
  Dateihashes untersuchen, soweit für technische Zuverlässigkeit relevant;
  gültige Bildinhalte und gleiche Georeferenzierung sind bereits belegt.
- [ ] Die großen Plugin-, Dialog- und Exporter-Klassen auf konkrete
  Wartbarkeitsprobleme prüfen; nur begründet und testgesichert modularisieren.
- [ ] Stärkere optionale Anzeige der Export-Diagnostik in der UI bewerten.

## Optionale Erweiterungen

- [ ] Weitere GDAL-Kompressionsoptionen und geringere Farbtiefe prüfen.
- [ ] Troubleshooting mit konkreten Fehlerbildern ergänzen.
- [ ] Nichtmodale Exporte bzw. Warteschlange hinsichtlich Aufwand und
  Nutzwert evaluieren.
- [ ] Zusätzliche Hinweise zu Seitenverhältnis, Tile- und Rastergröße evaluieren.
- [ ] Optional transparente Auflösungs-/Maßstabsempfehlungen für Webdienste
  anbieten, ohne die Benutzerauswahl automatisch zu ändern:
  - WMS: `MinScaleDenominator` / `MaxScaleDenominator` aus
    `GetCapabilities` als ungefähre Darstellungsgrenzen, nicht als native
    Rasterauflösung.
  - OGC-Näherung: `GSD = Maßstabsnenner × 0,00028 m` (Standardpixel),
    deutlich als Orientierung kennzeichnen.
  - WMTS/XYZ: Auflösungs-/Zoomstufen aus TileMatrixSet oder Metadaten.
  - ArcGIS MapServer/TileServer: `tileInfo.lods` berücksichtigen.
  - Eine Aktion „Empfohlene Auflösung übernehmen“ nur mit transparenter
    Herkunft und Unsicherheit vorsehen.
