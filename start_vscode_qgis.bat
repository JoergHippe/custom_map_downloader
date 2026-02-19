@echo off
:: Pfad zur OSGeo4W Installation
SET OSGEO4W_ROOT=C:\OSGeo4W

:: Initialisiere Standard OSGeo4W Umgebung
call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

:: QGIS-spezifische Pfade ergänzen
SET QGIS_PATH=%OSGEO4W_ROOT%\apps\qgis
SET PATH=%QGIS_PATH%\bin;%PATH%

:: PYTHONPATH erweitern für Autovervollständigung und Shell-Zugriff
SET PYTHONPATH=%QGIS_PATH%\python;%QGIS_PATH%\python\plugins;%PYTHONPATH%

:: Qt-Plugins für korrekte UI-Darstellung
SET QT_QPA_PLATFORM_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\Qt5\plugins\platforms
SET QGIS_PREFIX_PATH=%QGIS_PATH%

:: --- Robuste VS Code Suche ---
SET VSCODE_EXE=C:\Users\joerg\AppData\Local\Programs\Microsoft VS Code Insiders\Code - Insiders.exe
if not exist "%VSCODE_EXE%" SET VSCODE_EXE=%ProgramFiles%\Microsoft VS Code\Code.exe
if not exist "%VSCODE_EXE%" SET VSCODE_EXE=%ProgramFiles(x86)%\Microsoft VS Code\Code.exe

:: Falls Pfade oben fehlschlagen, wird der globale Pfad-Aufruf versucht
if not exist "%VSCODE_EXE%" SET VSCODE_EXE=code

:: Start von VS Code
start "" "%VSCODE_EXE%" .