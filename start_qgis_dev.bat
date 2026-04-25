@echo off
setlocal enableextensions
if not defined CMD_PAUSE_ON_ERROR set "CMD_PAUSE_ON_ERROR=1"

set "PROFILE=%~1"
if /I "%PROFILE%"=="" set "PROFILE=default"

set "MODE=%~2"
if /I "%MODE%"=="" set "MODE=link"

set "REPO_DIR=%~dp0"
cd /d "%REPO_DIR%" || (
  echo [ERROR] Could not switch to repo directory: %REPO_DIR%
  set "ERROR_CODE=1"
  goto fail
)

if not defined OSGEO4W_ROOT (
  if exist "C:\OSGeo4W64\bin\o4w_env.bat" set "OSGEO4W_ROOT=C:\OSGeo4W64"
  if not defined OSGEO4W_ROOT if exist "C:\OSGeo4W\bin\o4w_env.bat" set "OSGEO4W_ROOT=C:\OSGeo4W"
)

if not defined OSGEO4W_ROOT (
  echo [ERROR] OSGEO4W/QGIS installation not found.
  set "ERROR_CODE=1"
  goto fail
)

call "%OSGEO4W_ROOT%\bin\o4w_env.bat"

set "QGIS_PATH=%OSGEO4W_ROOT%\apps\qgis"
set "QGIS_BIN="
set "QGIS_BIN_IS_BAT=0"
if exist "%OSGEO4W_ROOT%\bin\qgis.bat" (
  set "QGIS_BIN=%OSGEO4W_ROOT%\bin\qgis.bat"
  set "QGIS_BIN_IS_BAT=1"
)
if not defined QGIS_BIN if exist "%OSGEO4W_ROOT%\bin\qgis-bin.exe" set "QGIS_BIN=%OSGEO4W_ROOT%\bin\qgis-bin.exe"
if not defined QGIS_BIN if exist "%QGIS_PATH%\bin\qgis-bin.exe" set "QGIS_BIN=%QGIS_PATH%\bin\qgis-bin.exe"
if not defined QGIS_BIN if exist "%QGIS_PATH%\bin\qgis.exe" set "QGIS_BIN=%QGIS_PATH%\bin\qgis.exe"
if not defined QGIS_BIN (
  echo [ERROR] QGIS executable not found.
  echo [HINT] Checked:
  echo        %OSGEO4W_ROOT%\bin\qgis.bat
  echo        %OSGEO4W_ROOT%\bin\qgis-bin.exe
  echo        %QGIS_PATH%\bin\qgis-bin.exe
  echo        %QGIS_PATH%\bin\qgis.exe
  set "ERROR_CODE=1"
  goto fail
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
    set "ERROR_CODE=1"
    goto fail
  )
  set "PYTHON_CMD=python"
)

echo [INFO] Repo: %REPO_DIR%
echo [INFO] Profile: %PROFILE%
echo [INFO] Deploy mode: %MODE%
echo [INFO] QGIS bin: %QGIS_BIN%

call "%PYTHON_CMD%" scripts\install_dev_plugin.py --profile "%PROFILE%" --mode "%MODE%"
if errorlevel 1 (
  set "ERROR_CODE=%ERRORLEVEL%"
  goto fail
)

if "%QGIS_BIN_IS_BAT%"=="1" (
  call "%QGIS_BIN%" --profile "%PROFILE%"
) else (
  start "" "%QGIS_BIN%" --profile "%PROFILE%"
  if errorlevel 1 (
    set "ERROR_CODE=%ERRORLEVEL%"
    goto fail
  )
)
exit /b 0

:fail
if not defined ERROR_CODE set "ERROR_CODE=1"
echo.
echo [ERROR] start_qgis_dev.bat failed with exit code %ERROR_CODE%.
echo [HINT] Set CMD_PAUSE_ON_ERROR=0 to disable this pause.
if not "%CMD_PAUSE_ON_ERROR%"=="0" pause
exit /b %ERROR_CODE%
