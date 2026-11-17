# Prüfstrategie für dynamische amtliche OGC-Kartendienste

Stand: 17.11.2026. Gilt für die WMS-/WMTS-Live-Szenarien und die
amtlichen Szenariokatalog- und Maßstabsberichte.

## Grundsatz

Amtliche Karteninhalte sind **dynamische Fremddaten**. Änderungen können
durch Aktualisierung von Geodaten, Symbolisierung oder Dienstsoftware
entstehen. Ein SHA-256-Dateihash ist deshalb ein **historischer
Vergleichswert**, keine zeitlich unbegrenzt gültige fachliche Sollvorgabe.

Ein Export kann technisch korrekt sein, obwohl sein Dateihash gegenüber
März 2026 abweicht. Der Prüflauf muss diesen Sachverhalt transparent
melden, darf ihn aber nicht stillschweigend als Plugin-Regression
interpretieren. Keine automatische Aktualisierung historischer Werte.

## Zwei unabhängige Prüfungen

| Prüfebene | Nachweise | Bewertung |
| --- | --- | --- |
| Technische Exportfunktion | gültige Quelle, tatsächlich ausgeführter Export, Ergebnisdatei, QGIS-Prozess-Erfolg, valider Bericht und Rasterdimensionen | Fehler/Missing = Testfehler |
| Historischer Dateivergleich | `expected_sha256` gegenüber aktuellem Datei-SHA-256 | `match` / `drift` / `untracked` = Vergleichshinweis |

Für die Maßstabsmatrix gelten zusätzlich ihre **technischen
Maßstabs-/Dimensionsprüfungen**. Fehlende Fälle, fehlende Ergebnisse,
Prozessfehler und ungültige Raster dürfen niemals als Erfolg gewertet
werden.

Die Auswertungen `summarize_network_catalog.py`,
`check_network_catalog_report.py`,
`summarize_scale_matrix.py` und `check_scale_matrix_report.py`
lassen `drift` und `untracked` nur als **Hinweis** durch. Bei
`missing`, `error`, ungültigen Reports, fehlender Fallabdeckung
oder einem Prozess-Exitcode ungleich null scheitert der technische Test.

Die optionale Live-WMS-Stufe bewertet `technical_gate=pass` nur nach
erfolgreicher GDAL-Diagnose und gültigem Exportreport. Das Feld
`release_gate=not_assessed` macht ausdrücklich klar, dass dieser
einzelne Smoke-Test **keine Releasefreigabe** darstellt.
`baseline_status` zeigt weiterhin den historischen Vergleich an.

## Bewertung historischer Abweichungen

- Die Referenzdateihashes für basemap.de Grau und NRW DTK wurden am
  **14.03.2026** im Repository hinterlegt.
- Im November 2026 waren aktuelle Ausgaben unter QGIS 3.44.15 und
  QGIS 4.2.3 jeweils auf Datei-, Pixel- und Georeferenzierungsebene
  identisch; die alten Dateihashes weichen dennoch ab.
- Da frühere GeoTIFF-Dateien fehlen, lässt sich die Ursache rückwirkend
  nicht eindeutig feststellen. Regelmäßige Aktualisierungen amtlicher
  Geodaten sind eine plausible, aber nicht bewiesene Erklärung.
- Diese Abweichungen werden weiterhin als **historische
  Referenzhinweise** geführt; sie allein verhindern nicht die technische
  Testfreigabe.

Eine neue Referenz kann bei Bedarf **bewusst und datiert** angelegt
werden. Dabei nach Möglichkeit Datei-, Pixel- und Georeferenzierungs-
Fingerprint, Dienstkennung, CRS, Extent, Auflösung sowie QGIS-/GDAL-
Version dokumentieren. Historische Vergleichswerte nicht ersetzen,
wenn ihre Entwicklung nachvollziehbar bleiben soll.

## Was trotzdem vor einer Veröffentlichung offen bleibt

Die konfigurierte WMS-Pflichtmaßstabsmatrix und ein echter
WMTS-Live-Fall sind unter QGIS 3/4 inzwischen technisch
erfolgreich geprüft. Offen bleiben die pixelgenaue
WMTS-Reproduzierbarkeit, der breite amtliche WMS-Katalog
und die Abnahme der offiziellen Windows-QGIS-Distribution. Ein grüner Live-Smoke allein genügt
nicht. Für reproduzierbare Code-Regressionen bleiben die lokalen
WMS-/WMTS-HTTP-Testserver in der regulären CI maßgeblich.

Aktuelle Resultate: [VALIDATION_STATUS.md](VALIDATION_STATUS.md).
Testaufrufe: [TESTING.md](TESTING.md).
