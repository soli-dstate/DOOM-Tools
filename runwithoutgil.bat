@echo off
pushd "%~dp0" || exit /b 1
setlocal
set "EXE=DOOM-Tools.exe"
set "PYFILE=main.py"
set "found_exe=0"
set "found_py=0"
if exist "%EXE%" set "found_exe=1"
if exist "%PYFILE%" set "found_py=1"
if "%found_exe%"=="0" if "%found_py%"=="0" (
  echo Neither %EXE% nor %PYFILE% found in %CD%.
  pause
  endlocal
  popd
  exit /b 1
)
set "TARGET="
if "%found_exe%"=="1" if "%found_py%"=="1" (
  echo Both %EXE% and %PYFILE% found.
  set /p "CHOICE=Choose target to run - E=exe, P=py: "
  if "%CHOICE%"=="" (
    echo No choice entered.
    pause
    endlocal
    popd
    exit /b 2
  )
  set "CHOICE=%CHOICE:~0,1%"
  if /I "%CHOICE%"=="E" set "TARGET=%EXE%"
  if /I "%CHOICE%"=="P" set "TARGET=%PYFILE%"
)

if "%TARGET%"=="" (
  if "%found_exe%"=="1" set "TARGET=%EXE%"
  if "%found_py%"=="1" set "TARGET=%PYFILE%"
)

if "%TARGET%"=="" (
  echo No target selected.
  pause
  endlocal
  popd
  exit /b 1
)
echo Launching %TARGET% with PYTHON_GIL=0
set "PYTHON_GIL=0"
for %%I in ("%TARGET%") do set "EXT=%%~xI"
if /I "%EXT%"==".exe" (
  "%TARGET%"
) else (
  where py >nul 2>&1
  if errorlevel 1 (
    python "%TARGET%"
  ) else (
    py "%TARGET%"
  )
)
set "RET=%ERRORLEVEL%"
endlocal & set "RET=%RET%"
popd
echo.
echo Process exited with code %RET%
pause
exit /b %RET%
@echo off
pushd "%~dp0" || exit /b 1
setlocal
set "EXE=main.exe"
set "PYFILE=main.py"
set "found_exe=0"
set "TARGET="
if "%found_exe%"=="1" if "%found_py%"=="1" (
  echo Both %EXE% and %PYFILE% found.
  set /p "CHOICE=Choose target to run - E=exe, P=py: "
  if "%CHOICE%"=="" (
    echo No choice entered.
    endlocal
    popd
    exit /b 2
  )
  set "CHOICE=%CHOICE:~0,1%"
  if /I "%CHOICE%"=="E" set "TARGET=%EXE%"
  if /I "%CHOICE%"=="P" set "TARGET=%PYFILE%"
)
if "%TARGET%"=="" (
  if "%found_exe%"=="1" set "TARGET=%EXE%"
  if "%found_py%"=="1" set "TARGET=%PYFILE%"
)
if "%TARGET%"=="" (
  echo No target selected.
  pause
  endlocal
  popd
  exit /b 1
)
  if /I "%CHOICE%"=="E" (
    set "TARGET=%EXE%"
  ) else if /I "%CHOICE%"=="P" (
    set "TARGET=%PYFILE%"
  ) else (
    echo Invalid choice: %CHOICE%
    pause
    endlocal
    popd
    exit /b 2
  )
) else (
  if "%found_exe%"=="1" set "TARGET=%EXE%"
  if "%found_py%"=="1" set "TARGET=%PYFILE%"
)
if "%TARGET%"=="" (
  echo No target selected.
  pause
  endlocal
  popd
  exit /b 1
)
echo Launching %TARGET% with PYTHON_GIL=0
set "PYTHON_GIL=0"
for %%I in ("%TARGET%") do set "EXT=%%~xI"
if /I "%EXT%"==".exe" (
  "%TARGET%"
) else (
  where py >nul 2>&1
  if errorlevel 1 (
    python "%TARGET%"
  ) else (
    py "%TARGET%"
  )
)
set "RET=%ERRORLEVEL%"
endlocal & set "RET=%RET%"
popd
echo.
echo Process exited with code %RET%
pause
exit /b %RET%