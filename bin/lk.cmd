@echo off
REM Thin launcher: run the bundled `lk` CLI from anywhere (Windows).
setlocal
set "HERE=%~dp0"
python "%HERE%lk.py" %*
exit /b %ERRORLEVEL%
