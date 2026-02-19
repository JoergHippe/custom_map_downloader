# QGIS-Integrationstests

Diese Tests benötigen eine echte QGIS-Python-Umgebung (qgis.core/qgis.gui). Unter Windows funktioniert das am einfachsten über die OSGeo4W-/QGIS-Shell.

## Vorbereitung (Windows)

1. QGIS installieren (z. B. OSGeo4W oder Standalone).  
2. OSGeo4W Shell / „QGIS Python“ öffnen.  
3. In das Projekt wechseln: `cd C:\Users\joerg\OneDrive\Documents\Coding\GitHubRepos\custom_map_downloader`  
4. Optional: `set QGIS_PREFIX_PATH=C:\OSGeo4W64\apps\qgis` (oder entsprechender QGIS-Pfad).

## Ausführen (lokal)

```
python -m unittest discover -s test/integration -v
```

Der Testsuite lädt ein kleines Raster (`test/tenbytenraster.asc`), setzt eine metrische CRS, startet den Exporter und schreibt ein GeoTIFF in ein temporäres Verzeichnis.

## Netzbasierte Szenarien (WMS/XYZ)

- Siehe `test/integration/config.json` für Quellen (`sources`) und Szenarien (`scenarios`).  
- Quellen definieren Provider/URI/Default-CRS; Szenarien referenzieren eine Quelle (`source`) und überschreiben Extent/GSD/VRT/Output.  
- Alle Szenarien laufen standardmäßig; optional filterbar über Env `SCENARIOS=name1,name2`.  
- Passe CRS/Extent/GSD/Output-Format nach Bedarf an (z. B. EPSG:25833, Dresden-Region).

### Aufbau der config.json

- `defaults`: zentrale Defaults (CRS, Extent, GSD, VRT/Output), die von Quellen/Szenarien geerbt werden.
- `sources`: Datenquellen mit `name`, `provider`, `uri`, optional `default_crs`, `extent`, `gsd`, `create_vrt`, `output_extension`.
- `scenarios`: konkrete Testläufe mit `name`, `source`-Verweis und optionalen Overrides (`crs`, `extent`, `gsd`, `vrt_preset_size`, `create_vrt`, `output_extension`).
- Umgebungsvariablen:
  - `ALLOW_INTEGRATION_NETWORK=1` aktiviert Netztests.
  - `CRS=EPSG:xxxx` überschreibt CRS global für alle Szenarien.
  - `EXTENT_W/E/S/N` überschreibt Extent global (z. B. `EXTENT_W=458000`).
  - `SCENARIOS=name1,name2` führt nur die genannten Szenarien aus.

### Batch-Helfer (Windows)

- Im Repo liegt `run_integration_tests.bat`. Aus der OSGeo4W-/QGIS-Shell im Repo-Root aufrufen:
  - `run_integration_tests.bat` → alle Integrationstests (`discover`)
  - `run_integration_tests.bat smoke` → nur lokaler Raster-Smoke-Test
  - `run_integration_tests.bat network` → nur Netz-Szenarien (setzt intern `ALLOW_INTEGRATION_NETWORK=1`)

Der Batch wechselt automatisch ins Repo, wählt nach Möglichkeit `python-qgis.bat`, prüft `qgis.core` vorab und gibt den Rückgabecode der Tests aus. Keine langen Pfade nötig.

## Hinweise

- Ohne QGIS-Umgebung werden die Tests automatisch übersprungen.  
- Pfade zum QGIS-Prefix können im Test über `QGIS_PREFIX_PATH` vorgegeben werden.  
- Testdaten liegen im Repo unter `test/` (10x10-Raster).  
- Integrationstests sind bewusst minimal gehalten; für umfangreiche Szenarien können zusätzliche Testdaten/Layer ergänzt werden.***
