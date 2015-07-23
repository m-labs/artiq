@rem Let CMake know about the LLVM install path, for find_package()
set CMAKE_PREFIX_PATH=%LIBRARY_PREFIX%

@rem Ensure there are no build leftovers (CMake can complain)
if exist ffi\build rmdir /S /Q ffi\build

@rem Apply patches
patch -p1 <  %RECIPE_DIR%/../../misc/llvmlite-add-all-targets.patch
patch -p1 <  %RECIPE_DIR%/../../misc/llvmlite-rename.patch
patch -p1 <  %RECIPE_DIR%/../../misc/llvmlite-build-as-debug-on-windows.patch

%PYTHON% -S setup.py install
if errorlevel 1 exit 1
