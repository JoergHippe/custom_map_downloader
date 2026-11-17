# Ausdehnungsauswahl und Zeichnen auf der Karte

Stand: 2026-11-17. Verbindliche Einordnung der Integration von
`QgsExtentGroupBox` im Plugin. Die Testmatrix und Freigabekriterien sind
zentral in [TESTING.md](TESTING.md) gepflegt.

## Architekturentscheidung

**Variante B:** QGIS-Widget für CRS-Transformation, manuelle Koordinaten und
Kartenwerkzeug weiterverwenden, dabei die Dialogsteuerung und die Auswahl
des tatsächlich exportierten Rechtecks kontrolliert im Plugin halten.
Kein vollständiger Eigenbau; vorhandene Workarounds nicht ohne nachgewiesene
Regressionstests löschen.

Das exportierte Rechteck wird über die öffentliche
`QgsExtentGroupBox.outputExtent()` in `outputCrs()` bezogen.
`setCurrentExtent()` aktualisiert dagegen die *angebotene aktuelle*
Karten-/Layerausdehnung und ist **kein** Ersatz für das Auswählen
eines Exportrechtecks. Zum Wiederherstellen einer explizit ausgewählten
Profil-Ausdehnung wird `setOutputExtentFromUser(rect, crs)` verwendet.

Dokumentierte QGIS-APIs:
- [QGIS 3.44: QgsExtentWidget](https://api.qgis.org/api/3.44/classQgsExtentWidget.html)
- [QGIS 4.2: QgsExtentGroupBox](https://api.qgis.org/api/4.2/classQgsExtentGroupBox.html)

## Hintergrund und bisherige Fehler

- [Commit vom 26.04.2026](https://github.com/JoergHippe/custom_map_downloader/commit/32eeacf3284a29815c5cffea1ae7190b8a52f0b2):
  Statt `QDialog.exec_()` wird ein nichtmodal sichtbarer Dialog mit
  eigenem `QEventLoop` verwendet. Das Kartenwerkzeug muss den Dialog
  während des Zeichnens verbergen und danach wieder anzeigen können.
- Die bestehende Dialogimplementierung enthält einen 300-ms-Poller und
  Fallbacks auf `currentExtent()` sowie interne `QLineEdit`-Felder, weil
  bei früheren Abläufen sichtbare Koordinaten und `outputExtent()`
  auseinanderlaufen konnten.
- **Nachgewiesene Regression im November 2026:** Profile wurden nur über
  `setCurrentExtent()` wiederhergestellt; der Export hätte weiterhin die
  alte `outputExtent()` verwendet. Der Fehler war in QGIS 3.44.15 und
  4.2.3 reproduzierbar und wurde mit `setOutputExtentFromUser()` behoben.

## Automatisierte Abdeckung

`tests/integration/test_extent_dialog.py` instanziiert den echten
Qt-Dialog, `QgsExtentGroupBox` und `QgsMapCanvas` in einer QGIS-Laufzeit.
Es prüft Canvas-Reset, explizite Benutzerausdehnung, Profilwiederherstellung,
CRS-Wechsel und wiederholtes Zeichnen per synthetischen Qt-Mausereignissen.
Das Deaktivieren des Zeichenwerkzeugs ohne Auswahl wird als Abbruch geprüft.

Die Tests laufen ohne Webdienste mit `QT_QPA_PLATFORM=offscreen` unter
QGIS 3.44.15 (Qt5) und QGIS 4.2.3 (Qt6).

## Nachgewiesene Korrekturen der internen Koordinatenfelder

Die gezielte QGIS-3/4-Regression zeigte, dass der alte Keyword-Resolver
`xmax` und `ymax` **auf dasselbe interne Feld** `mYMaxLineEdit` abbildete.
Ursache waren einbuchstabige, nicht eindeutige Teilstring-Treffer.
Damit konnte die letzte Fallback-Stufe falsche Koordinaten liefern.

Die bisherige Heuristik mit übersetzten Labels, Tooltips und
positionsbasiertem Raten wurde entfernt. Die vier internen Felder werden
nur noch über ihre **exakten** Qt-Objektnamen aufgelöst:
`mXMinLineEdit`, `mXMaxLineEdit`, `mYMinLineEdit`, `mYMaxLineEdit`.
Sind diese unbekannt, bleibt das betreffende Feld ausdrücklich
unaufgelöst. Die primäre Datenquelle bleibt die öffentliche QGIS-API
`outputExtent()`.

Ein separater Test zeigt, dass die Eingabe in `xmax` die X-Grenze
ändert, ohne `ymax` zu überschreiben. Ein weiterer Test simuliert
umbenannte interne Felder und verhindert stilles Zurückfallen auf
Widget-Reihenfolgen.

Außerdem wurde das direkte Schreiben in die internen `QLineEdit`-Felder
per `setText()` beim Canvas-Reset entfernt. Die QGIS-3/4-Tests zeigen,
dass `setOutputExtentFromUser()` die vier sichtbaren Werte bereits
korrekt aktualisiert.

Der localeabhängige Fallback-Parser wurde für gemischte Dezimal- und
Gruppierungszeichen korrigiert (z. B. `1.234,50` bzw. `1,234.50`).
Bei Zahlen mit **nur einem** Komma oder Punkt bleibt eine grundsätzlich
mögliche Mehrdeutigkeit (z. B. `1,234`) bestehen. Der öffentliche
QGIS-Zustand hat daher weiterhin Vorrang vor Textparsing.

**Nachweis:** [GitHub Actions #44172109704](https://github.com/JoergHippe/custom_map_downloader/actions/runs/44172109704)
unter QGIS 3.44.15 und QGIS 4.2.3.

## Bewusst noch nicht entfernt

- Polling von Änderungen nach `Draw on canvas`.
- Zugriff auf `QgsExtentWidget` für die Steuerung der Dialogsichtbarkeit.
- Optionaler, auf exakte Objektnamen begrenzter Fallback auf interne `QLineEdit`-Felder und `currentExtent()`.
- Eigene Behandlung des Signals `toggleDialogVisibility`.

**Verbleibende Risiken:** Die exakten Feldnamen sind weiterhin private
Implementierungsdetails der QGIS-Oberfläche und können sich ändern.
`currentExtent()` repräsentiert nicht zwingend die ausgewählte
Exportausdehnung. Der Fallback auf Feldtexte und die Unterstützung
mehrdeutiger Einzel-Trennzeichen dürfen deshalb nicht als stabile
öffentliche Schnittstellen betrachtet werden.

Vor weiteren Änderungen an Polling, `currentExtent()`-Fallback
oder Sichtbarkeitssteuerung sind gesonderte Windows-QGIS-GUI-Tests
für manuelle Eingabe (einschließlich deutscher Systemeinstellung)
und Zeichnen/Abbrechen notwendig. Ein bestandener Linux-Offscreen-
Test ersetzt nicht die Bedienprüfung im vollständigen Windows-QGIS.

**Keine** Änderung der QGIS-4-Kompatibilitätsmetadaten durch diese Entscheidung.
