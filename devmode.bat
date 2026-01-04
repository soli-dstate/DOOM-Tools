@echo off
pushd "%~dp0.." || exit /b 1
if exist main.py (
    py -3 main.py -dev 2>nul || python main.py -dev
) else (
    echo main.py not found in %cd%
    pause
    popd
    exit /b 1
)
popd
exit /b %ERRORLEVEL%