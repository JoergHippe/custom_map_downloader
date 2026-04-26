# Roadmap Notes

## Service Resolution Hints

Future improvement: show optional resolution guidance for service-backed layers.

- For WMS, parse `GetCapabilities` where possible and display `MinScaleDenominator`
  / `MaxScaleDenominator` as a service-provided visible scale range.
- Convert WMS scale denominators to approximate GSD using the OGC standard pixel size
  (`GSD = scale_denominator * 0.00028`), but label this as guidance, not as a hard
  native resolution.
- For WMTS/XYZ/tiled services, derive a more reliable zoom/resolution ladder when
  tile matrix or zoom metadata is available.
- For ArcGIS MapServer/TileServer sources, use `tileInfo.lods` when available.
- Add an optional action such as "Apply suggested resolution" only after showing
  the source and confidence of the suggestion.
- Do not silently overwrite the user's selected GSD or target scale.

