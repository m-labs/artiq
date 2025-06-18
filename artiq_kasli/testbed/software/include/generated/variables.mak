ifeq ($(CPU),vexriscv-g)
TRIPLE=riscv32-unknown-linux
CPUFLAGS=-D__vexriscv__ -march=rv32g -mabi=ilp32d
CLANG=1
LLVM_TOOLS=1
endif
ifeq ($(CPU),vexriscv)
TRIPLE=riscv32-unknown-linux
CPUFLAGS=-D__vexriscv__ -march=rv32ima -mabi=ilp32
CLANG=1
LLVM_TOOLS=1
endif
MISOC_DIRECTORY=/nix/store/dwh6ls215041nj6l802ad47l3q30ckr1-python3-3.12.10-env/lib/python3.12/site-packages/misoc
BUILDINC_DIRECTORY=/home/artiq-alkaline/ARTIQ-alkaline-fork/artiq_kasli/testbed/software/include
export BUILDINC_DIRECTORY
BOOTLOADER_DIRECTORY=/home/artiq-alkaline/ARTIQ-alkaline-fork/artiq/firmware/bootloader
LIBM_DIRECTORY=/nix/store/dwh6ls215041nj6l802ad47l3q30ckr1-python3-3.12.10-env/lib/python3.12/site-packages/misoc/software/libm
LIBPRINTF_DIRECTORY=/nix/store/dwh6ls215041nj6l802ad47l3q30ckr1-python3-3.12.10-env/lib/python3.12/site-packages/misoc/software/libprintf
LIBUNWIND_DIRECTORY=/nix/store/dwh6ls215041nj6l802ad47l3q30ckr1-python3-3.12.10-env/lib/python3.12/site-packages/misoc/software/libunwind
KSUPPORT_DIRECTORY=/home/artiq-alkaline/ARTIQ-alkaline-fork/artiq/firmware/ksupport
LIBUNWIND_DIRECTORY=/nix/store/dwh6ls215041nj6l802ad47l3q30ckr1-python3-3.12.10-env/lib/python3.12/site-packages/misoc/software/libunwind
RUNTIME_DIRECTORY=/home/artiq-alkaline/ARTIQ-alkaline-fork/artiq/firmware/runtime
