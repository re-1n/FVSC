@echo off
REM Local dev helper — copies built plugin into the user's vault.
REM Run from the obsidian-plugin/ directory: install-to-vault.cmd
REM Adjust VAULT below if your vault lives elsewhere.

set "VAULT=C:\Users\daur1\Desktop\экзокортекс для fvsc map\Rein"
set "DEST=%VAULT%\.obsidian\plugins\fvsc-antourage"

if not exist "%DEST%" mkdir "%DEST%"

copy /Y "manifest.json" "%DEST%\manifest.json" >nul
copy /Y "main.js"       "%DEST%\main.js"       >nul
copy /Y "styles.css"    "%DEST%\styles.css"    >nul

echo Plugin installed to: %DEST%
