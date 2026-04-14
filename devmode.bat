@echo off
pushd "%~dp0" || exit /b 1
set "PYTHON_GIL=0"
if exist DOOM-Tools.exe (
    DOOM-Tools.exe -dev
) else (
    echo DOOM-Tools.exe not found in %cd%
    pause
    popd
    exit /b 1
)
popd
exit /b %ERRORLEVEL%