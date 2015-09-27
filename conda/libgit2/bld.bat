mkdir build
cd build
REM Configure step
if "%ARCH%"=="32" (
set CMAKE_GENERATOR=Visual Studio 12 2013
) else (
set CMAKE_GENERATOR=Visual Studio 12 2013 Win64
)
set CMAKE_GENERATOR_TOOLSET=v120_xp
cmake -G "%CMAKE_GENERATOR%" -DCMAKE_INSTALL_PREFIX=%PREFIX% -DSTDCALL=OFF -DCMAKE_PREFIX_PATH=$PREFIX %SRC_DIR%
if errorlevel 1 exit 1
REM Build step
cmake --build .
if errorlevel 1 exit 1
REM Install step
cmake --build . --target install
if errorlevel 1 exit 1
REM Hack to help pygit2 to find libgit2
mkdir %PREFIX%\Scripts
copy "%PREFIX%\bin\git2.dll" "%PREFIX%\Scripts\"