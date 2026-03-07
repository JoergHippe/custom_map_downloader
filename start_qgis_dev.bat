@echo off
setlocal enableextensions

set "PROFILE=%~1"
if /I "%PROFILE%"=="" set "PROFILE=default"

set "MODE=%~2"
if /I "%MODE%"=="" set "MODE=link"

set "REPO_DIR=%~dp0"
cd /d "%REPO_DIR%" || (
  echo [ERROR] Could not switch to repo directory: %REPO_DIR%
  exit /b 1
)

if not defined OSGEO4W_ROOT (
  if exist "C:\OSGeo4W64\bin\o4w_env.bat" set "OSGEO4W_ROOT=C:\OSGeo4W64"
  if not defined OSGEO4W_ROOT if exist "C:\OSGeo4W\bin\o4w_env.bat" set "OSGEO4W_ROOT=C:\OSGeo4W"
)

if not defined OSGEO4W_ROOT (
  echo [ERROR] OSGEO4W/QGIS installation not found.
  exit /b 1
)

call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

set "QGIS_PATH=%OSGEO4W_ROOT%\apps\qgis"
set "QGIS_BIN=%QGIS_PATH%\bin\qgis-bin.exe"
if not exist "%QGIS_BIN%" set "QGIS_BIN=%QGIS_PATH%\bin\qgis.exe"
if not exist "%QGIS_BIN%" (
  echo [ERROR] QGIS executable not found under %QGIS_PATH%\bin
  exit /b 1
)

set "PATH=%QGIS_PATH%\bin;%PATH%"
set "PYTHONPATH=%QGIS_PATH%\python;%QGIS_PATH%\python\plugins;%PYTHONPATH%"
set "QT_QPA_PLATFORM_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\Qt5\plugins\platforms"
set "QGIS_PREFIX_PATH=%QGIS_PATH%"

set "PYTHON_CMD="
if exist "%OSGEO4W_ROOT%\bin\python-qgis.bat" (
  set "PYTHON_CMD=%OSGEO4W_ROOT%\bin\python-qgis.bat"
) else (
  where python >nul 2>nul || (
    echo [ERROR] No Python interpreter available for deployment helper.
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

echo [INFO] Repo: %REPO_DIR%
echo [INFO] Profile: %PROFILE%
echo [INFO] Deploy mode: %MODE%
echo [INFO] QGIS bin: %QGIS_BIN%

"%PYTHON_CMD%" scripts\install_dev_plugin.py --profile "%PROFILE%" --mode "%MODE%"
if errorlevel 1 exit /b %errorlevel%

start "" "%QGIS_BIN%" --profile "%PROFILE%"
exit /b 0
