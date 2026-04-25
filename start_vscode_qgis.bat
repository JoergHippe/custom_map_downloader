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
set "PATH=%QGIS_PATH%\bin;%PATH%"
set "PYTHONPATH=%QGIS_PATH%\python;%QGIS_PATH%\python\plugins;%PYTHONPATH%"
set "QT_QPA_PLATFORM_PLUGIN_PATH=%OSGEO4W_ROOT%\apps\Qt5\plugins\platforms"
set "QGIS_PREFIX_PATH=%QGIS_PATH%"
if defined APPDATA (
  set "QGIS_CUSTOM_CONFIG_PATH=%APPDATA%\QGIS\QGIS3"
)
set "QGIS_PROFILE=%PROFILE%"

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

call "%PYTHON_CMD%" scripts\install_dev_plugin.py --profile "%PROFILE%" --mode "%MODE%"
if errorlevel 1 (
  set "ERROR_CODE=%ERRORLEVEL%"
  goto fail
)

set "VSCODE_EXE=C:\Users\joerg\AppData\Local\Programs\Microsoft VS Code Insiders\Code - Insiders.exe"
if not exist "%VSCODE_EXE%" set "VSCODE_EXE=%LOCALAPPDATA%\Programs\Microsoft VS Code Insiders\Code - Insiders.exe"
if not exist "%VSCODE_EXE%" set "VSCODE_EXE=%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"
if not exist "%VSCODE_EXE%" set "VSCODE_EXE=%ProgramFiles%\Microsoft VS Code\Code.exe"
if not exist "%VSCODE_EXE%" set "VSCODE_EXE=%ProgramFiles(x86)%\Microsoft VS Code\Code.exe"
if not exist "%VSCODE_EXE%" (
  where code-insiders >nul 2>nul && set "VSCODE_EXE=code-insiders"
)
if not exist "%VSCODE_EXE%" set "VSCODE_EXE=code"
if "%VSCODE_EXE%"=="code-insiders" (
  where code-insiders >nul 2>nul || (
    echo [ERROR] VS Code Insiders command not found.
    echo [HINT] Install the code-insiders command, install VS Code, or update VSCODE_EXE in this script.
    set "ERROR_CODE=1"
    goto fail
  )
) else if "%VSCODE_EXE%"=="code" (
  where code >nul 2>nul || (
    echo [ERROR] VS Code executable not found.
    echo [HINT] Install VS Code, add the code command to PATH, or update VSCODE_EXE in this script.
    set "ERROR_CODE=1"
    goto fail
  )
)

echo [INFO] Repo: %REPO_DIR%
echo [INFO] Profile: %PROFILE%
echo [INFO] Deploy mode: %MODE%
echo [INFO] QGIS_PREFIX_PATH: %QGIS_PREFIX_PATH%
echo [INFO] VS Code: %VSCODE_EXE%

start "" "%VSCODE_EXE%" .
if errorlevel 1 (
  set "ERROR_CODE=%ERRORLEVEL%"
  goto fail
)
exit /b 0

:fail
if not defined ERROR_CODE set "ERROR_CODE=1"
echo.
echo [ERROR] start_vscode_qgis.bat failed with exit code %ERROR_CODE%.
echo [HINT] Set CMD_PAUSE_ON_ERROR=0 to disable this pause.
if not "%CMD_PAUSE_ON_ERROR%"=="0" pause
exit /b %ERROR_CODE%
