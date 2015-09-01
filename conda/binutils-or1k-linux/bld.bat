FOR /F "tokens=* USEBACKQ" %%F IN (`cygpath -u %PREFIX%`) DO (
SET var=%%F
)
set PREFIX=%var%
FOR /F "tokens=* USEBACKQ" %%F IN (`cygpath -u %RECIPE_DIR%`) DO (
SET var=%%F
)
set RECIPE_DIR=%var%
sh %RECIPE_DIR%/build.sh
if errorlevel 1 exit 1
