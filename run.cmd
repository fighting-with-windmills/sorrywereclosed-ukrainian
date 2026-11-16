@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

if "%~1"=="" goto :usage
if /i "%~1"=="extract" goto :extract
if /i "%~1"=="apply" goto :apply
if /i "%~1"=="restore" goto :restore
if /i "%~1"=="verify" goto :verify
goto :usage

:extract
echo === Exporting translatable text to translations\uk\ ===
echo.
python tools\extract.py %2 %3 %4 %5 %6 %7 %8 %9
if errorlevel 1 goto :failed
echo.
echo Done. Edit translations\uk\*.json, then run: run.cmd apply
goto :done

:apply
echo === 1/3  Writing the Ukrainian text into the game bundles ===
echo.
python tools\apply.py --fonts --apply %2 %3 %4 %5 %6 %7 %8 %9
if errorlevel 1 goto :failed
echo.
echo === 2/3  Patching Assembly-CSharp.dll (language menu entry) ===
echo.
dotnet run --project tools\AssemblyPatcher -c Release -- --in-place
if errorlevel 1 goto :failed
echo.
echo === 3/3  Verifying the result ===
echo.
python tools\verify.py
echo.
echo Finished. Start the game and pick "Українська" in the language menu.
goto :done

:restore
echo === Restoring the original bundles and Assembly-CSharp.dll ===
echo.
python tools\restore.py --assembly %2 %3 %4 %5 %6 %7 %8 %9
if errorlevel 1 goto :failed
echo.
echo Restored.
goto :done

:verify
python tools\verify.py --check-assembly %2 %3 %4 %5 %6 %7 %8 %9
goto :done

:usage
echo Usage: run.cmd ^<extract^|apply^|restore^|verify^> [options]
echo.
echo   extract   write translations\uk\*.json from the game
echo   apply     patch bundles + assembly, then verify
echo   restore   copy the original files back
echo   verify    re-check a patched installation
exit /b 2

:failed
echo.
echo Something failed - see the messages above.
echo The original files are in the _uk_backup folder; run "run.cmd restore" to undo.
goto :done

:done
echo.
pause
exit /b 0
