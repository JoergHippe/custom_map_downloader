@echo off
setlocal enableextensions

set "MODE=%~1"
if /I "%MODE%"=="" set "MODE=all"

set "REPO_DIR=%~dp0"
cd /d "%REPO_DIR%" || (
  echo [ERROR] Could not switch to repo directory: %REPO_DIR%
  exit /b 1
)

if not defined QGIS_PREFIX_PATH (
  if exist "C:\OSGeo4W64\apps\qgis" set "QGIS_PREFIX_PATH=C:\OSGeo4W64\apps\qgis"
  if not defined QGIS_PREFIX_PATH if exist "C:\OSGeo4W\apps\qgis" set "QGIS_PREFIX_PATH=C:\OSGeo4W\apps\qgis"
)

if not defined OSGEO4W_ROOT (
  if exist "C:\OSGeo4W64\bin\python-qgis.bat" set "OSGEO4W_ROOT=C:\OSGeo4W64"
  if not defined OSGEO4W_ROOT if exist "C:\OSGeo4W\bin\python-qgis.bat" set "OSGEO4W_ROOT=C:\OSGeo4W"
)

set "PYQGIS_BAT="
if defined OSGEO4W_ROOT set "PYQGIS_BAT=%OSGEO4W_ROOT%\bin\python-qgis.bat"
if not defined PYQGIS_BAT if exist "C:\OSGeo4W64\bin\python-qgis.bat" set "PYQGIS_BAT=C:\OSGeo4W64\bin\python-qgis.bat"
if not defined PYQGIS_BAT if exist "C:\OSGeo4W\bin\python-qgis.bat" set "PYQGIS_BAT=C:\OSGeo4W\bin\python-qgis.bat"

if exist "%PYQGIS_BAT%" (
  set "PYTHON_CMD=%PYQGIS_BAT%"
) else (
  where python >nul 2>nul || (
    echo [ERROR] No python interpreter found. Start from OSGeo4W/QGIS shell or install Python.
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

echo [INFO] Repo: %REPO_DIR%
echo [INFO] Mode: %MODE%
echo [INFO] QGIS_PREFIX_PATH: %QGIS_PREFIX_PATH%
echo [INFO] Python command: %PYTHON_CMD%

"%PYTHON_CMD%" -c "import qgis.core" >nul 2>nul
if errorlevel 1 (
  echo [ERROR] qgis.core is not importable in this shell.
  echo [HINT] Use OSGeo4W/QGIS shell or ensure QGIS Python is on PATH.
  exit /b 1
)

if /I "%MODE%"=="all" (
  "%PYTHON_CMD%" -m unittest discover -s test/integration -v
  exit /b %errorlevel%
)

if /I "%MODE%"=="smoke" (
  "%PYTHON_CMD%" -m unittest -v test.integration.test_export_smoke
  exit /b %errorlevel%
)

if /I "%MODE%"=="network" (
  set "ALLOW_INTEGRATION_NETWORK=1"
  "%PYTHON_CMD%" -m unittest -v test.integration.test_export_network
  exit /b %errorlevel%
)

echo [ERROR] Unknown mode "%MODE%".
echo Usage: run_integration_tests.bat [all^|smoke^|network]
exit /b 2
