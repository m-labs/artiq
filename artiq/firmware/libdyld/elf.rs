/* generated from elf.h with rust-bindgen and then manually altered */
#![allow(non_camel_case_types, non_snake_case, non_upper_case_globals)]

pub const EI_NIDENT: usize = 16;
pub const EI_MAG0: usize = 0;
pub const ELFMAG0: u8 = 127;
pub const EI_MAG1: usize = 1;
pub const ELFMAG1: u8 = b'E';
pub const EI_MAG2: usize = 2;
pub const ELFMAG2: u8 = b'L';
pub const EI_MAG3: usize = 3;
pub const ELFMAG3: u8 = b'F';
pub const ELFMAG: &'static [u8; 5usize] = b"\x7fELF\x00";
pub const SELFMAG: usize = 4;
pub const EI_CLASS: usize = 4;
pub const ELFCLASSNONE: u8 = 0;
pub const ELFCLASS32: u8 = 1;
pub const ELFCLASS64: u8 = 2;
pub const ELFCLASSNUM: u8 = 3;
pub const EI_DATA: usize = 5;
pub const ELFDATANONE: u8 = 0;
pub const ELFDATA2LSB: u8 = 1;
pub const ELFDATA2MSB: u8 = 2;
pub const ELFDATANUM: u8 = 3;
pub const EI_VERSION: usize = 6;
pub const EI_OSABI: usize = 7;
pub const ELFOSABI_NONE: u8 = 0;
pub const ELFOSABI_SYSV: u8 = 0;
pub const ELFOSABI_HPUX: u8 = 1;
pub const ELFOSABI_NETBSD: u8 = 2;
pub const ELFOSABI_GNU: u8 = 3;
pub const ELFOSABI_LINUX: u8 = 3;
pub const ELFOSABI_SOLARIS: u8 = 6;
pub const ELFOSABI_AIX: u8 = 7;
pub const ELFOSABI_IRIX: u8 = 8;
pub const ELFOSABI_FREEBSD: u8 = 9;
pub const ELFOSABI_TRU64: u8 = 10;
pub const ELFOSABI_MODESTO: u8 = 11;
pub const ELFOSABI_OPENBSD: u8 = 12;
pub const ELFOSABI_ARM_AEABI: u8 = 64;
pub const ELFOSABI_ARM: u8 = 97;
pub const ELFOSABI_STANDALONE: u8 = 255;
pub const EI_ABIVERSION: usize = 8;
pub const EI_PAD: usize = 9;
pub const ET_NONE: u16 = 0;
pub const ET_REL: u16 = 1;
pub const ET_EXEC: u16 = 2;
pub const ET_DYN: u16 = 3;
pub const ET_CORE: u16 = 4;
pub const ET_NUM: u16 = 5;
pub const ET_LOOS: u16 = 65024;
pub const ET_HIOS: u16 = 65279;
pub const ET_LOPROC: u16 = 65280;
pub const ET_HIPROC: u16 = 65535;
pub const EM_NONE: u16 = 0;
pub const EM_M32: u16 = 1;
pub const EM_SPARC: u16 = 2;
pub const EM_386: u16 = 3;
pub const EM_68K: u16 = 4;
pub const EM_88K: u16 = 5;
pub const EM_860: u16 = 7;
pub const EM_MIPS: u16 = 8;
pub const EM_S370: u16 = 9;
pub const EM_MIPS_RS3_LE: u16 = 10;
pub const EM_PARISC: u16 = 15;
pub const EM_VPP500: u16 = 17;
pub const EM_SPARC32PLUS: u16 = 18;
pub const EM_960: u16 = 19;
pub const EM_PPC: u16 = 20;
pub const EM_PPC64: u16 = 21;
pub const EM_S390: u16 = 22;
pub const EM_V800: u16 = 36;
pub const EM_FR20: u16 = 37;
pub const EM_RH32: u16 = 38;
pub const EM_RCE: u16 = 39;
pub const EM_ARM: u16 = 40;
pub const EM_FAKE_ALPHA: u16 = 41;
pub const EM_SH: u16 = 42;
pub const EM_SPARCV9: u16 = 43;
pub const EM_TRICORE: u16 = 44;
pub const EM_ARC: u16 = 45;
pub const EM_H8_300: u16 = 46;
pub const EM_H8_300H: u16 = 47;
pub const EM_H8S: u16 = 48;
pub const EM_H8_500: u16 = 49;
pub const EM_IA_64: u16 = 50;
pub const EM_MIPS_X: u16 = 51;
pub const EM_COLDFIRE: u16 = 52;
pub const EM_68HC12: u16 = 53;
pub const EM_MMA: u16 = 54;
pub const EM_PCP: u16 = 55;
pub const EM_NCPU: u16 = 56;
pub const EM_NDR1: u16 = 57;
pub const EM_STARCORE: u16 = 58;
pub const EM_ME16: u16 = 59;
pub const EM_ST100: u16 = 60;
pub const EM_TINYJ: u16 = 61;
pub const EM_X86_64: u16 = 62;
pub const EM_PDSP: u16 = 63;
pub const EM_FX66: u16 = 66;
pub const EM_ST9PLUS: u16 = 67;
pub const EM_ST7: u16 = 68;
pub const EM_68HC16: u16 = 69;
pub const EM_68HC11: u16 = 70;
pub const EM_68HC08: u16 = 71;
pub const EM_68HC05: u16 = 72;
pub const EM_SVX: u16 = 73;
pub const EM_ST19: u16 = 74;
pub const EM_VAX: u16 = 75;
pub const EM_CRIS: u16 = 76;
pub const EM_JAVELIN: u16 = 77;
pub const EM_FIREPATH: u16 = 78;
pub const EM_ZSP: u16 = 79;
pub const EM_MMIX: u16 = 80;
pub const EM_HUANY: u16 = 81;
pub const EM_PRISM: u16 = 82;
pub const EM_AVR: u16 = 83;
pub const EM_FR30: u16 = 84;
pub const EM_D10V: u16 = 85;
pub const EM_D30V: u16 = 86;
pub const EM_V850: u16 = 87;
pub const EM_M32R: u16 = 88;
pub const EM_MN10300: u16 = 89;
pub const EM_MN10200: u16 = 90;
pub const EM_PJ: u16 = 91;
pub const EM_OPENRISC: u16 = 92;
pub const EM_ARC_A5: u16 = 93;
pub const EM_XTENSA: u16 = 94;
pub const EM_AARCH64: u16 = 183;
pub const EM_TILEPRO: u16 = 188;
pub const EM_MICROBLAZE: u16 = 189;
pub const EM_TILEGX: u16 = 191;
pub const EM_NUM: u16 = 192;
pub const EM_ALPHA: u16 = 36902;
pub const EV_NONE: u8 = 0;
pub const EV_CURRENT: u8 = 1;
pub const EV_NUM: u8 = 2;
pub const SHN_UNDEF: u16 = 0;
pub const SHN_LORESERVE: u16 = 65280;
pub const SHN_LOPROC: u16 = 65280;
pub const SHN_BEFORE: u16 = 65280;
pub const SHN_AFTER: u16 = 65281;
pub const SHN_HIPROC: u16 = 65311;
pub const SHN_LOOS: u16 = 65312;
pub const SHN_HIOS: u16 = 65343;
pub const SHN_ABS: u16 = 65521;
pub const SHN_COMMON: u16 = 65522;
pub const SHN_XINDEX: u16 = 65535;
pub const SHN_HIRESERVE: u16 = 65535;
pub const SHT_NULL: usize = 0;
pub const SHT_PROGBITS: usize = 1;
pub const SHT_SYMTAB: usize = 2;
pub const SHT_STRTAB: usize = 3;
pub const SHT_RELA: usize = 4;
pub const SHT_HASH: usize = 5;
pub const SHT_DYNAMIC: usize = 6;
pub const SHT_NOTE: usize = 7;
pub const SHT_NOBITS: usize = 8;
pub const SHT_REL: usize = 9;
pub const SHT_SHLIB: usize = 10;
pub const SHT_DYNSYM: usize = 11;
pub const SHT_INIT_ARRAY: usize = 14;
pub const SHT_FINI_ARRAY: usize = 15;
pub const SHT_PREINIT_ARRAY: usize = 16;
pub const SHT_GROUP: usize = 17;
pub const SHT_SYMTAB_SHNDX: usize = 18;
pub const SHT_NUM: usize = 19;
pub const SHT_LOOS: usize = 1610612736;
pub const SHT_GNU_ATTRIBUTES: usize = 1879048181;
pub const SHT_GNU_HASH: usize = 1879048182;
pub const SHT_GNU_LIBLIST: usize = 1879048183;
pub const SHT_CHECKSUM: usize = 1879048184;
pub const SHT_LOSUNW: usize = 1879048186;
pub const SHT_SUNW_move: usize = 1879048186;
pub const SHT_SUNW_COMDAT: usize = 1879048187;
pub const SHT_SUNW_syminfo: usize = 1879048188;
pub const SHT_GNU_verdef: usize = 1879048189;
pub const SHT_GNU_verneed: usize = 1879048190;
pub const SHT_GNU_versym: usize = 1879048191;
pub const SHT_HISUNW: usize = 1879048191;
pub const SHT_HIOS: usize = 1879048191;
pub const SHT_LOPROC: usize = 1879048192;
pub const SHT_HIPROC: usize = 2147483647;
pub const SHT_LOUSER: usize = 2147483648;
pub const SHT_HIUSER: usize = 2415919103;
pub const SHF_WRITE: usize = 1;
pub const SHF_ALLOC: usize = 2;
pub const SHF_EXECINSTR: usize = 4;
pub const SHF_MERGE: usize = 16;
pub const SHF_STRINGS: usize = 32;
pub const SHF_INFO_LINK: usize = 64;
pub const SHF_LINK_ORDER: usize = 128;
pub const SHF_OS_NONCONFORMING: usize = 256;
pub const SHF_GROUP: usize = 512;
pub const SHF_TLS: usize = 1024;
pub const SHF_MASKOS: usize = 267386880;
pub const SHF_MASKPROC: usize = 4026531840;
pub const SHF_ORDERED: usize = 1073741824;
pub const SHF_EXCLUDE: usize = 2147483648;
pub const GRP_COMDAT: usize = 1;
pub const SYMINFO_BT_SELF: usize = 65535;
pub const SYMINFO_BT_PARENT: usize = 65534;
pub const SYMINFO_BT_LOWRESERVE: usize = 65280;
pub const SYMINFO_FLG_DIRECT: usize = 1;
pub const SYMINFO_FLG_PASSTHRU: usize = 2;
pub const SYMINFO_FLG_COPY: usize = 4;
pub const SYMINFO_FLG_LAZYLOAD: usize = 8;
pub const SYMINFO_NONE: usize = 0;
pub const SYMINFO_CURRENT: usize = 1;
pub const SYMINFO_NUM: usize = 2;
pub const STB_LOCAL: u8 = 0;
pub const STB_GLOBAL: u8 = 1;
pub const STB_WEAK: u8 = 2;
pub const STB_NUM: u8 = 3;
pub const STB_LOOS: u8 = 10;
pub const STB_GNU_UNIQUE: u8 = 10;
pub const STB_HIOS: u8 = 12;
pub const STB_LOPROC: u8 = 13;
pub const STB_HIPROC: u8 = 15;
pub const STT_NOTYPE: u8 = 0;
pub const STT_OBJECT: u8 = 1;
pub const STT_FUNC: u8 = 2;
pub const STT_SECTION: u8 = 3;
pub const STT_FILE: u8 = 4;
pub const STT_COMMON: u8 = 5;
pub const STT_TLS: u8 = 6;
pub const STT_NUM: u8 = 7;
pub const STT_LOOS: u8 = 10;
pub const STT_GNU_IFUNC: u8 = 10;
pub const STT_HIOS: u8 = 12;
pub const STT_LOPROC: u8 = 13;
pub const STT_HIPROC: u8 = 15;
pub const STN_UNDEF: usize = 0;
pub const STV_DEFAULT: usize = 0;
pub const STV_INTERNAL: usize = 1;
pub const STV_HIDDEN: usize = 2;
pub const STV_PROTECTED: usize = 3;
pub const PN_XNUM: usize = 65535;
pub const PT_NULL: u32 = 0;
pub const PT_LOAD: u32 = 1;
pub const PT_DYNAMIC: u32 = 2;
pub const PT_INTERP: u32 = 3;
pub const PT_NOTE: u32 = 4;
pub const PT_SHLIB: u32 = 5;
pub const PT_PHDR: u32 = 6;
pub const PT_TLS: u32 = 7;
pub const PT_NUM: u32 = 8;
pub const PT_LOOS: u32 = 1610612736;
pub const PT_GNU_EH_FRAME: u32 = 1685382480;
pub const PT_GNU_STACK: u32 = 1685382481;
pub const PT_GNU_RELRO: u32 = 1685382482;
pub const PT_LOSUNW: u32 = 1879048186;
pub const PT_SUNWBSS: u32 = 1879048186;
pub const PT_SUNWSTACK: u32 = 1879048187;
pub const PT_HISUNW: u32 = 1879048191;
pub const PT_HIOS: u32 = 1879048191;
pub const PT_LOPROC: u32 = 1879048192;
pub const PT_HIPROC: u32 = 2147483647;
pub const PF_X: usize = 1;
pub const PF_W: usize = 2;
pub const PF_R: usize = 4;
pub const PF_MASKOS: usize = 267386880;
pub const PF_MASKPROC: usize = 4026531840;
pub const NT_PRSTATUS: usize = 1;
pub const NT_FPREGSET: usize = 2;
pub const NT_PRPSINFO: usize = 3;
pub const NT_PRXREG: usize = 4;
pub const NT_TASKSTRUCT: usize = 4;
pub const NT_PLATFORM: usize = 5;
pub const NT_AUXV: usize = 6;
pub const NT_GWINDOWS: usize = 7;
pub const NT_ASRS: usize = 8;
pub const NT_PSTATUS: usize = 10;
pub const NT_PSINFO: usize = 13;
pub const NT_PRCRED: usize = 14;
pub const NT_UTSNAME: usize = 15;
pub const NT_LWPSTATUS: usize = 16;
pub const NT_LWPSINFO: usize = 17;
pub const NT_PRFPXREG: usize = 20;
pub const NT_SIGINFO: usize = 1397311305;
pub const NT_FILE: usize = 1179208773;
pub const NT_PRXFPREG: usize = 1189489535;
pub const NT_PPC_VMX: usize = 256;
pub const NT_PPC_SPE: usize = 257;
pub const NT_PPC_VSX: usize = 258;
pub const NT_386_TLS: usize = 512;
pub const NT_386_IOPERM: usize = 513;
pub const NT_X86_XSTATE: usize = 514;
pub const NT_S390_HIGH_GPRS: usize = 768;
pub const NT_S390_TIMER: usize = 769;
pub const NT_S390_TODCMP: usize = 770;
pub const NT_S390_TODPREG: usize = 771;
pub const NT_S390_CTRS: usize = 772;
pub const NT_S390_PREFIX: usize = 773;
pub const NT_S390_LAST_BREAK: usize = 774;
pub const NT_S390_SYSTEM_CALL: usize = 775;
pub const NT_S390_TDB: usize = 776;
pub const NT_ARM_VFP: usize = 1024;
pub const NT_ARM_TLS: usize = 1025;
pub const NT_ARM_HW_BREAK: usize = 1026;
pub const NT_ARM_HW_WATCH: usize = 1027;
pub const NT_VERSION: usize = 1;
pub const DT_NULL: i32 = 0;
pub const DT_NEEDED: i32 = 1;
pub const DT_PLTRELSZ: i32 = 2;
pub const DT_PLTGOT: i32 = 3;
pub const DT_HASH: i32 = 4;
pub const DT_STRTAB: i32 = 5;
pub const DT_SYMTAB: i32 = 6;
pub const DT_RELA: i32 = 7;
pub const DT_RELASZ: i32 = 8;
pub const DT_RELAENT: i32 = 9;
pub const DT_STRSZ: i32 = 10;
pub const DT_SYMENT: i32 = 11;
pub const DT_INIT: i32 = 12;
pub const DT_FINI: i32 = 13;
pub const DT_SONAME: i32 = 14;
pub const DT_RPATH: i32 = 15;
pub const DT_SYMBOLIC: i32 = 16;
pub const DT_REL: i32 = 17;
pub const DT_RELSZ: i32 = 18;
pub const DT_RELENT: i32 = 19;
pub const DT_PLTREL: i32 = 20;
pub const DT_DEBUG: i32 = 21;
pub const DT_TEXTREL: i32 = 22;
pub const DT_JMPREL: i32 = 23;
pub const DT_BIND_NOW: i32 = 24;
pub const DT_INIT_ARRAY: i32 = 25;
pub const DT_FINI_ARRAY: i32 = 26;
pub const DT_INIT_ARRAYSZ: i32 = 27;
pub const DT_FINI_ARRAYSZ: i32 = 28;
pub const DT_RUNPATH: i32 = 29;
pub const DT_FLAGS: i32 = 30;
pub const DT_ENCODING: i32 = 32;
pub const DT_PREINIT_ARRAY: i32 = 32;
pub const DT_PREINIT_ARRAYSZ: i32 = 33;
pub const DT_NUM: i32 = 34;
pub const DT_LOOS: i32 = 1610612749;
pub const DT_HIOS: i32 = 1879044096;
pub const DT_LOPROC: i32 = 1879048192;
pub const DT_HIPROC: i32 = 2147483647;
pub const DT_VALRNGLO: i32 = 1879047424;
pub const DT_GNU_PRELINKED: i32 = 1879047669;
pub const DT_GNU_CONFLICTSZ: i32 = 1879047670;
pub const DT_GNU_LIBLISTSZ: i32 = 1879047671;
pub const DT_CHECKSUM: i32 = 1879047672;
pub const DT_PLTPADSZ: i32 = 1879047673;
pub const DT_MOVEENT: i32 = 1879047674;
pub const DT_MOVESZ: i32 = 1879047675;
pub const DT_FEATURE_1: i32 = 1879047676;
pub const DT_POSFLAG_1: i32 = 1879047677;
pub const DT_SYMINSZ: i32 = 1879047678;
pub const DT_SYMINENT: i32 = 1879047679;
pub const DT_VALRNGHI: i32 = 1879047679;
pub const DT_VALNUM: i32 = 12;
pub const DT_ADDRRNGLO: i32 = 1879047680;
pub const DT_GNU_HASH: i32 = 1879047925;
pub const DT_TLSDESC_PLT: i32 = 1879047926;
pub const DT_TLSDESC_GOT: i32 = 1879047927;
pub const DT_GNU_CONFLICT: i32 = 1879047928;
pub const DT_GNU_LIBLIST: i32 = 1879047929;
pub const DT_CONFIG: i32 = 1879047930;
pub const DT_DEPAUDIT: i32 = 1879047931;
pub const DT_AUDIT: i32 = 1879047932;
pub const DT_PLTPAD: i32 = 1879047933;
pub const DT_MOVETAB: i32 = 1879047934;
pub const DT_SYMINFO: i32 = 1879047935;
pub const DT_ADDRRNGHI: i32 = 1879047935;
pub const DT_ADDRNUM: i32 = 11;
pub const DT_VERSYM: i32 = 1879048176;
pub const DT_RELACOUNT: i32 = 1879048185;
pub const DT_RELCOUNT: i32 = 1879048186;
pub const DT_FLAGS_1: i32 = 1879048187;
pub const DT_VERDEF: i32 = 1879048188;
pub const DT_VERDEFNUM: i32 = 1879048189;
pub const DT_VERNEED: i32 = 1879048190;
pub const DT_VERNEEDNUM: i32 = 1879048191;
pub const DT_VERSIONTAGNUM: i32 = 16;
pub const DT_AUXILIARY: i32 = 2147483645;
pub const DT_FILTER: i32 = 2147483647;
pub const DT_EXTRANUM: i32 = 3;
pub const DF_ORIGIN: usize = 1;
pub const DF_SYMBOLIC: usize = 2;
pub const DF_TEXTREL: usize = 4;
pub const DF_BIND_NOW: usize = 8;
pub const DF_STATIC_TLS: usize = 16;
pub const DF_1_NOW: usize = 1;
pub const DF_1_GLOBAL: usize = 2;
pub const DF_1_GROUP: usize = 4;
pub const DF_1_NODELETE: usize = 8;
pub const DF_1_LOADFLTR: usize = 16;
pub const DF_1_INITFIRST: usize = 32;
pub const DF_1_NOOPEN: usize = 64;
pub const DF_1_ORIGIN: usize = 128;
pub const DF_1_DIRECT: usize = 256;
pub const DF_1_TRANS: usize = 512;
pub const DF_1_INTERPOSE: usize = 1024;
pub const DF_1_NODEFLIB: usize = 2048;
pub const DF_1_NODUMP: usize = 4096;
pub const DF_1_CONFALT: usize = 8192;
pub const DF_1_ENDFILTEE: usize = 16384;
pub const DF_1_DISPRELDNE: usize = 32768;
pub const DF_1_DISPRELPND: usize = 65536;
pub const DF_1_NODIRECT: usize = 131072;
pub const DF_1_IGNMULDEF: usize = 262144;
pub const DF_1_NOKSYMS: usize = 524288;
pub const DF_1_NOHDR: usize = 1048576;
pub const DF_1_EDITED: usize = 2097152;
pub const DF_1_NORELOC: usize = 4194304;
pub const DF_1_SYMINTPOSE: usize = 8388608;
pub const DF_1_GLOBAUDIT: usize = 16777216;
pub const DF_1_SINGLETON: usize = 33554432;
pub const DTF_1_PARINIT: usize = 1;
pub const DTF_1_CONFEXP: usize = 2;
pub const DF_P1_LAZYLOAD: usize = 1;
pub const DF_P1_GROUPPERM: usize = 2;
pub const VER_DEF_NONE: usize = 0;
pub const VER_DEF_CURRENT: usize = 1;
pub const VER_DEF_NUM: usize = 2;
pub const VER_FLG_BASE: usize = 1;
pub const VER_FLG_WEAK: usize = 2;
pub const VER_NDX_LOCAL: usize = 0;
pub const VER_NDX_GLOBAL: usize = 1;
pub const VER_NDX_LORESERVE: usize = 65280;
pub const VER_NDX_ELIMINATE: usize = 65281;
pub const VER_NEED_NONE: usize = 0;
pub const VER_NEED_CURRENT: usize = 1;
pub const VER_NEED_NUM: usize = 2;
pub const ELF_NOTE_SOLARIS: &'static [u8; 13usize] = b"SUNW Solaris\x00";
pub const ELF_NOTE_GNU: &'static [u8; 4usize] = b"GNU\x00";
pub const ELF_NOTE_PAGESIZE_HINT: usize = 1;
pub const NT_GNU_ABI_TAG: usize = 1;
pub const ELF_NOTE_ABI: usize = 1;
pub const ELF_NOTE_OS_LINUX: usize = 0;
pub const ELF_NOTE_OS_GNU: usize = 1;
pub const ELF_NOTE_OS_SOLARIS2: usize = 2;
pub const ELF_NOTE_OS_FREEBSD: usize = 3;
pub const NT_GNU_HWCAP: usize = 2;
pub const NT_GNU_BUILD_ID: usize = 3;
pub const NT_GNU_GOLD_VERSION: usize = 4;
pub const EF_CPU32: usize = 8454144;
pub const R_68K_NONE: usize = 0;
pub const R_68K_32: usize = 1;
pub const R_68K_16: usize = 2;
pub const R_68K_8: usize = 3;
pub const R_68K_PC32: usize = 4;
pub const R_68K_PC16: usize = 5;
pub const R_68K_PC8: usize = 6;
pub const R_68K_GOT32: usize = 7;
pub const R_68K_GOT16: usize = 8;
pub const R_68K_GOT8: usize = 9;
pub const R_68K_GOT32O: usize = 10;
pub const R_68K_GOT16O: usize = 11;
pub const R_68K_GOT8O: usize = 12;
pub const R_68K_PLT32: usize = 13;
pub const R_68K_PLT16: usize = 14;
pub const R_68K_PLT8: usize = 15;
pub const R_68K_PLT32O: usize = 16;
pub const R_68K_PLT16O: usize = 17;
pub const R_68K_PLT8O: usize = 18;
pub const R_68K_COPY: usize = 19;
pub const R_68K_GLOB_DAT: usize = 20;
pub const R_68K_JMP_SLOT: usize = 21;
pub const R_68K_RELATIVE: usize = 22;
pub const R_68K_TLS_GD32: usize = 25;
pub const R_68K_TLS_GD16: usize = 26;
pub const R_68K_TLS_GD8: usize = 27;
pub const R_68K_TLS_LDM32: usize = 28;
pub const R_68K_TLS_LDM16: usize = 29;
pub const R_68K_TLS_LDM8: usize = 30;
pub const R_68K_TLS_LDO32: usize = 31;
pub const R_68K_TLS_LDO16: usize = 32;
pub const R_68K_TLS_LDO8: usize = 33;
pub const R_68K_TLS_IE32: usize = 34;
pub const R_68K_TLS_IE16: usize = 35;
pub const R_68K_TLS_IE8: usize = 36;
pub const R_68K_TLS_LE32: usize = 37;
pub const R_68K_TLS_LE16: usize = 38;
pub const R_68K_TLS_LE8: usize = 39;
pub const R_68K_TLS_DTPMOD32: usize = 40;
pub const R_68K_TLS_DTPREL32: usize = 41;
pub const R_68K_TLS_TPREL32: usize = 42;
pub const R_68K_NUM: usize = 43;
pub const R_386_NONE: usize = 0;
pub const R_386_32: usize = 1;
pub const R_386_PC32: usize = 2;
pub const R_386_GOT32: usize = 3;
pub const R_386_PLT32: usize = 4;
pub const R_386_COPY: usize = 5;
pub const R_386_GLOB_DAT: usize = 6;
pub const R_386_JMP_SLOT: usize = 7;
pub const R_386_RELATIVE: usize = 8;
pub const R_386_GOTOFF: usize = 9;
pub const R_386_GOTPC: usize = 10;
pub const R_386_32PLT: usize = 11;
pub const R_386_TLS_TPOFF: usize = 14;
pub const R_386_TLS_IE: usize = 15;
pub const R_386_TLS_GOTIE: usize = 16;
pub const R_386_TLS_LE: usize = 17;
pub const R_386_TLS_GD: usize = 18;
pub const R_386_TLS_LDM: usize = 19;
pub const R_386_16: usize = 20;
pub const R_386_PC16: usize = 21;
pub const R_386_8: usize = 22;
pub const R_386_PC8: usize = 23;
pub const R_386_TLS_GD_32: usize = 24;
pub const R_386_TLS_GD_PUSH: usize = 25;
pub const R_386_TLS_GD_CALL: usize = 26;
pub const R_386_TLS_GD_POP: usize = 27;
pub const R_386_TLS_LDM_32: usize = 28;
pub const R_386_TLS_LDM_PUSH: usize = 29;
pub const R_386_TLS_LDM_CALL: usize = 30;
pub const R_386_TLS_LDM_POP: usize = 31;
pub const R_386_TLS_LDO_32: usize = 32;
pub const R_386_TLS_IE_32: usize = 33;
pub const R_386_TLS_LE_32: usize = 34;
pub const R_386_TLS_DTPMOD32: usize = 35;
pub const R_386_TLS_DTPOFF32: usize = 36;
pub const R_386_TLS_TPOFF32: usize = 37;
pub const R_386_SIZE32: usize = 38;
pub const R_386_TLS_GOTDESC: usize = 39;
pub const R_386_TLS_DESC_CALL: usize = 40;
pub const R_386_TLS_DESC: usize = 41;
pub const R_386_IRELATIVE: usize = 42;
pub const R_386_NUM: usize = 43;
pub const STT_SPARC_REGISTER: usize = 13;
pub const EF_SPARCV9_MM: usize = 3;
pub const EF_SPARCV9_TSO: usize = 0;
pub const EF_SPARCV9_PSO: usize = 1;
pub const EF_SPARCV9_RMO: usize = 2;
pub const EF_SPARC_LEDATA: usize = 8388608;
pub const EF_SPARC_EXT_MASK: usize = 16776960;
pub const EF_SPARC_32PLUS: usize = 256;
pub const EF_SPARC_SUN_US1: usize = 512;
pub const EF_SPARC_HAL_R1: usize = 1024;
pub const EF_SPARC_SUN_US3: usize = 2048;
pub const R_SPARC_NONE: usize = 0;
pub const R_SPARC_8: usize = 1;
pub const R_SPARC_16: usize = 2;
pub const R_SPARC_32: usize = 3;
pub const R_SPARC_DISP8: usize = 4;
pub const R_SPARC_DISP16: usize = 5;
pub const R_SPARC_DISP32: usize = 6;
pub const R_SPARC_WDISP30: usize = 7;
pub const R_SPARC_WDISP22: usize = 8;
pub const R_SPARC_HI22: usize = 9;
pub const R_SPARC_22: usize = 10;
pub const R_SPARC_13: usize = 11;
pub const R_SPARC_LO10: usize = 12;
pub const R_SPARC_GOT10: usize = 13;
pub const R_SPARC_GOT13: usize = 14;
pub const R_SPARC_GOT22: usize = 15;
pub const R_SPARC_PC10: usize = 16;
pub const R_SPARC_PC22: usize = 17;
pub const R_SPARC_WPLT30: usize = 18;
pub const R_SPARC_COPY: usize = 19;
pub const R_SPARC_GLOB_DAT: usize = 20;
pub const R_SPARC_JMP_SLOT: usize = 21;
pub const R_SPARC_RELATIVE: usize = 22;
pub const R_SPARC_UA32: usize = 23;
pub const R_SPARC_PLT32: usize = 24;
pub const R_SPARC_HIPLT22: usize = 25;
pub const R_SPARC_LOPLT10: usize = 26;
pub const R_SPARC_PCPLT32: usize = 27;
pub const R_SPARC_PCPLT22: usize = 28;
pub const R_SPARC_PCPLT10: usize = 29;
pub const R_SPARC_10: usize = 30;
pub const R_SPARC_11: usize = 31;
pub const R_SPARC_64: usize = 32;
pub const R_SPARC_OLO10: usize = 33;
pub const R_SPARC_HH22: usize = 34;
pub const R_SPARC_HM10: usize = 35;
pub const R_SPARC_LM22: usize = 36;
pub const R_SPARC_PC_HH22: usize = 37;
pub const R_SPARC_PC_HM10: usize = 38;
pub const R_SPARC_PC_LM22: usize = 39;
pub const R_SPARC_WDISP16: usize = 40;
pub const R_SPARC_WDISP19: usize = 41;
pub const R_SPARC_GLOB_JMP: usize = 42;
pub const R_SPARC_7: usize = 43;
pub const R_SPARC_5: usize = 44;
pub const R_SPARC_6: usize = 45;
pub const R_SPARC_DISP64: usize = 46;
pub const R_SPARC_PLT64: usize = 47;
pub const R_SPARC_HIX22: usize = 48;
pub const R_SPARC_LOX10: usize = 49;
pub const R_SPARC_H44: usize = 50;
pub const R_SPARC_M44: usize = 51;
pub const R_SPARC_L44: usize = 52;
pub const R_SPARC_REGISTER: usize = 53;
pub const R_SPARC_UA64: usize = 54;
pub const R_SPARC_UA16: usize = 55;
pub const R_SPARC_TLS_GD_HI22: usize = 56;
pub const R_SPARC_TLS_GD_LO10: usize = 57;
pub const R_SPARC_TLS_GD_ADD: usize = 58;
pub const R_SPARC_TLS_GD_CALL: usize = 59;
pub const R_SPARC_TLS_LDM_HI22: usize = 60;
pub const R_SPARC_TLS_LDM_LO10: usize = 61;
pub const R_SPARC_TLS_LDM_ADD: usize = 62;
pub const R_SPARC_TLS_LDM_CALL: usize = 63;
pub const R_SPARC_TLS_LDO_HIX22: usize = 64;
pub const R_SPARC_TLS_LDO_LOX10: usize = 65;
pub const R_SPARC_TLS_LDO_ADD: usize = 66;
pub const R_SPARC_TLS_IE_HI22: usize = 67;
pub const R_SPARC_TLS_IE_LO10: usize = 68;
pub const R_SPARC_TLS_IE_LD: usize = 69;
pub const R_SPARC_TLS_IE_LDX: usize = 70;
pub const R_SPARC_TLS_IE_ADD: usize = 71;
pub const R_SPARC_TLS_LE_HIX22: usize = 72;
pub const R_SPARC_TLS_LE_LOX10: usize = 73;
pub const R_SPARC_TLS_DTPMOD32: usize = 74;
pub const R_SPARC_TLS_DTPMOD64: usize = 75;
pub const R_SPARC_TLS_DTPOFF32: usize = 76;
pub const R_SPARC_TLS_DTPOFF64: usize = 77;
pub const R_SPARC_TLS_TPOFF32: usize = 78;
pub const R_SPARC_TLS_TPOFF64: usize = 79;
pub const R_SPARC_GOTDATA_HIX22: usize = 80;
pub const R_SPARC_GOTDATA_LOX10: usize = 81;
pub const R_SPARC_GOTDATA_OP_HIX22: usize = 82;
pub const R_SPARC_GOTDATA_OP_LOX10: usize = 83;
pub const R_SPARC_GOTDATA_OP: usize = 84;
pub const R_SPARC_H34: usize = 85;
pub const R_SPARC_SIZE32: usize = 86;
pub const R_SPARC_SIZE64: usize = 87;
pub const R_SPARC_WDISP10: usize = 88;
pub const R_SPARC_JMP_IREL: usize = 248;
pub const R_SPARC_IRELATIVE: usize = 249;
pub const R_SPARC_GNU_VTINHERIT: usize = 250;
pub const R_SPARC_GNU_VTENTRY: usize = 251;
pub const R_SPARC_REV32: usize = 252;
pub const R_SPARC_NUM: usize = 253;
pub const DT_SPARC_REGISTER: usize = 1879048193;
pub const DT_SPARC_NUM: usize = 2;
pub const EF_MIPS_NOREORDER: usize = 1;
pub const EF_MIPS_PIC: usize = 2;
pub const EF_MIPS_CPIC: usize = 4;
pub const EF_MIPS_XGOT: usize = 8;
pub const EF_MIPS_64BIT_WHIRL: usize = 16;
pub const EF_MIPS_ABI2: usize = 32;
pub const EF_MIPS_ABI_ON32: usize = 64;
pub const EF_MIPS_NAN2008: usize = 1024;
pub const EF_MIPS_ARCH: usize = 4026531840;
pub const EF_MIPS_ARCH_1: usize = 0;
pub const EF_MIPS_ARCH_2: usize = 268435456;
pub const EF_MIPS_ARCH_3: usize = 536870912;
pub const EF_MIPS_ARCH_4: usize = 805306368;
pub const EF_MIPS_ARCH_5: usize = 1073741824;
pub const EF_MIPS_ARCH_32: usize = 1342177280;
pub const EF_MIPS_ARCH_64: usize = 1610612736;
pub const EF_MIPS_ARCH_32R2: usize = 1879048192;
pub const EF_MIPS_ARCH_64R2: usize = 2147483648;
pub const E_MIPS_ARCH_1: usize = 0;
pub const E_MIPS_ARCH_2: usize = 268435456;
pub const E_MIPS_ARCH_3: usize = 536870912;
pub const E_MIPS_ARCH_4: usize = 805306368;
pub const E_MIPS_ARCH_5: usize = 1073741824;
pub const E_MIPS_ARCH_32: usize = 1342177280;
pub const E_MIPS_ARCH_64: usize = 1610612736;
pub const SHN_MIPS_ACOMMON: usize = 65280;
pub const SHN_MIPS_TEXT: usize = 65281;
pub const SHN_MIPS_DATA: usize = 65282;
pub const SHN_MIPS_SCOMMON: usize = 65283;
pub const SHN_MIPS_SUNDEFINED: usize = 65284;
pub const SHT_MIPS_LIBLIST: usize = 1879048192;
pub const SHT_MIPS_MSYM: usize = 1879048193;
pub const SHT_MIPS_CONFLICT: usize = 1879048194;
pub const SHT_MIPS_GPTAB: usize = 1879048195;
pub const SHT_MIPS_UCODE: usize = 1879048196;
pub const SHT_MIPS_DEBUG: usize = 1879048197;
pub const SHT_MIPS_REGINFO: usize = 1879048198;
pub const SHT_MIPS_PACKAGE: usize = 1879048199;
pub const SHT_MIPS_PACKSYM: usize = 1879048200;
pub const SHT_MIPS_RELD: usize = 1879048201;
pub const SHT_MIPS_IFACE: usize = 1879048203;
pub const SHT_MIPS_CONTENT: usize = 1879048204;
pub const SHT_MIPS_OPTIONS: usize = 1879048205;
pub const SHT_MIPS_SHDR: usize = 1879048208;
pub const SHT_MIPS_FDESC: usize = 1879048209;
pub const SHT_MIPS_EXTSYM: usize = 1879048210;
pub const SHT_MIPS_DENSE: usize = 1879048211;
pub const SHT_MIPS_PDESC: usize = 1879048212;
pub const SHT_MIPS_LOCSYM: usize = 1879048213;
pub const SHT_MIPS_AUXSYM: usize = 1879048214;
pub const SHT_MIPS_OPTSYM: usize = 1879048215;
pub const SHT_MIPS_LOCSTR: usize = 1879048216;
pub const SHT_MIPS_LINE: usize = 1879048217;
pub const SHT_MIPS_RFDESC: usize = 1879048218;
pub const SHT_MIPS_DELTASYM: usize = 1879048219;
pub const SHT_MIPS_DELTAINST: usize = 1879048220;
pub const SHT_MIPS_DELTACLASS: usize = 1879048221;
pub const SHT_MIPS_DWARF: usize = 1879048222;
pub const SHT_MIPS_DELTADECL: usize = 1879048223;
pub const SHT_MIPS_SYMBOL_LIB: usize = 1879048224;
pub const SHT_MIPS_EVENTS: usize = 1879048225;
pub const SHT_MIPS_TRANSLATE: usize = 1879048226;
pub const SHT_MIPS_PIXIE: usize = 1879048227;
pub const SHT_MIPS_XLATE: usize = 1879048228;
pub const SHT_MIPS_XLATE_DEBUG: usize = 1879048229;
pub const SHT_MIPS_WHIRL: usize = 1879048230;
pub const SHT_MIPS_EH_REGION: usize = 1879048231;
pub const SHT_MIPS_XLATE_OLD: usize = 1879048232;
pub const SHT_MIPS_PDR_EXCEPTION: usize = 1879048233;
pub const SHF_MIPS_GPREL: usize = 268435456;
pub const SHF_MIPS_MERGE: usize = 536870912;
pub const SHF_MIPS_ADDR: usize = 1073741824;
pub const SHF_MIPS_STRINGS: usize = 2147483648;
pub const SHF_MIPS_NOSTRIP: usize = 134217728;
pub const SHF_MIPS_LOCAL: usize = 67108864;
pub const SHF_MIPS_NAMES: usize = 33554432;
pub const SHF_MIPS_NODUPE: usize = 16777216;
pub const STO_MIPS_DEFAULT: usize = 0;
pub const STO_MIPS_INTERNAL: usize = 1;
pub const STO_MIPS_HIDDEN: usize = 2;
pub const STO_MIPS_PROTECTED: usize = 3;
pub const STO_MIPS_PLT: usize = 8;
pub const STO_MIPS_SC_ALIGN_UNUSED: usize = 255;
pub const STB_MIPS_SPLIT_COMMON: usize = 13;
pub const ODK_NULL: usize = 0;
pub const ODK_REGINFO: usize = 1;
pub const ODK_EXCEPTIONS: usize = 2;
pub const ODK_PAD: usize = 3;
pub const ODK_HWPATCH: usize = 4;
pub const ODK_FILL: usize = 5;
pub const ODK_TAGS: usize = 6;
pub const ODK_HWAND: usize = 7;
pub const ODK_HWOR: usize = 8;
pub const OEX_FPU_MIN: usize = 31;
pub const OEX_FPU_MAX: usize = 7936;
pub const OEX_PAGE0: usize = 65536;
pub const OEX_SMM: usize = 131072;
pub const OEX_FPDBUG: usize = 262144;
pub const OEX_PRECISEFP: usize = 262144;
pub const OEX_DISMISS: usize = 524288;
pub const OEX_FPU_INVAL: usize = 16;
pub const OEX_FPU_DIV0: usize = 8;
pub const OEX_FPU_OFLO: usize = 4;
pub const OEX_FPU_UFLO: usize = 2;
pub const OEX_FPU_INEX: usize = 1;
pub const OHW_R4KEOP: usize = 1;
pub const OHW_R8KPFETCH: usize = 2;
pub const OHW_R5KEOP: usize = 4;
pub const OHW_R5KCVTL: usize = 8;
pub const OPAD_PREFIX: usize = 1;
pub const OPAD_POSTFIX: usize = 2;
pub const OPAD_SYMBOL: usize = 4;
pub const OHWA0_R4KEOP_CHECKED: usize = 1;
pub const OHWA1_R4KEOP_CLEAN: usize = 2;
pub const R_MIPS_NONE: usize = 0;
pub const R_MIPS_16: usize = 1;
pub const R_MIPS_32: usize = 2;
pub const R_MIPS_REL32: usize = 3;
pub const R_MIPS_26: usize = 4;
pub const R_MIPS_HI16: usize = 5;
pub const R_MIPS_LO16: usize = 6;
pub const R_MIPS_GPREL16: usize = 7;
pub const R_MIPS_LITERAL: usize = 8;
pub const R_MIPS_GOT16: usize = 9;
pub const R_MIPS_PC16: usize = 10;
pub const R_MIPS_CALL16: usize = 11;
pub const R_MIPS_GPREL32: usize = 12;
pub const R_MIPS_SHIFT5: usize = 16;
pub const R_MIPS_SHIFT6: usize = 17;
pub const R_MIPS_64: usize = 18;
pub const R_MIPS_GOT_DISP: usize = 19;
pub const R_MIPS_GOT_PAGE: usize = 20;
pub const R_MIPS_GOT_OFST: usize = 21;
pub const R_MIPS_GOT_HI16: usize = 22;
pub const R_MIPS_GOT_LO16: usize = 23;
pub const R_MIPS_SUB: usize = 24;
pub const R_MIPS_INSERT_A: usize = 25;
pub const R_MIPS_INSERT_B: usize = 26;
pub const R_MIPS_DELETE: usize = 27;
pub const R_MIPS_HIGHER: usize = 28;
pub const R_MIPS_HIGHEST: usize = 29;
pub const R_MIPS_CALL_HI16: usize = 30;
pub const R_MIPS_CALL_LO16: usize = 31;
pub const R_MIPS_SCN_DISP: usize = 32;
pub const R_MIPS_REL16: usize = 33;
pub const R_MIPS_ADD_IMMEDIATE: usize = 34;
pub const R_MIPS_PJUMP: usize = 35;
pub const R_MIPS_RELGOT: usize = 36;
pub const R_MIPS_JALR: usize = 37;
pub const R_MIPS_TLS_DTPMOD32: usize = 38;
pub const R_MIPS_TLS_DTPREL32: usize = 39;
pub const R_MIPS_TLS_DTPMOD64: usize = 40;
pub const R_MIPS_TLS_DTPREL64: usize = 41;
pub const R_MIPS_TLS_GD: usize = 42;
pub const R_MIPS_TLS_LDM: usize = 43;
pub const R_MIPS_TLS_DTPREL_HI16: usize = 44;
pub const R_MIPS_TLS_DTPREL_LO16: usize = 45;
pub const R_MIPS_TLS_GOTTPREL: usize = 46;
pub const R_MIPS_TLS_TPREL32: usize = 47;
pub const R_MIPS_TLS_TPREL64: usize = 48;
pub const R_MIPS_TLS_TPREL_HI16: usize = 49;
pub const R_MIPS_TLS_TPREL_LO16: usize = 50;
pub const R_MIPS_GLOB_DAT: usize = 51;
pub const R_MIPS_COPY: usize = 126;
pub const R_MIPS_JUMP_SLOT: usize = 127;
pub const R_MIPS_NUM: usize = 128;
pub const PT_MIPS_REGINFO: usize = 1879048192;
pub const PT_MIPS_RTPROC: usize = 1879048193;
pub const PT_MIPS_OPTIONS: usize = 1879048194;
pub const PF_MIPS_LOCAL: usize = 268435456;
pub const DT_MIPS_RLD_VERSION: usize = 1879048193;
pub const DT_MIPS_TIME_STAMP: usize = 1879048194;
pub const DT_MIPS_ICHECKSUM: usize = 1879048195;
pub const DT_MIPS_IVERSION: usize = 1879048196;
pub const DT_MIPS_FLAGS: usize = 1879048197;
pub const DT_MIPS_BASE_ADDRESS: usize = 1879048198;
pub const DT_MIPS_MSYM: usize = 1879048199;
pub const DT_MIPS_CONFLICT: usize = 1879048200;
pub const DT_MIPS_LIBLIST: usize = 1879048201;
pub const DT_MIPS_LOCAL_GOTNO: usize = 1879048202;
pub const DT_MIPS_CONFLICTNO: usize = 1879048203;
pub const DT_MIPS_LIBLISTNO: usize = 1879048208;
pub const DT_MIPS_SYMTABNO: usize = 1879048209;
pub const DT_MIPS_UNREFEXTNO: usize = 1879048210;
pub const DT_MIPS_GOTSYM: usize = 1879048211;
pub const DT_MIPS_HIPAGENO: usize = 1879048212;
pub const DT_MIPS_RLD_MAP: usize = 1879048214;
pub const DT_MIPS_DELTA_CLASS: usize = 1879048215;
pub const DT_MIPS_DELTA_CLASS_NO: usize = 1879048216;
pub const DT_MIPS_DELTA_INSTANCE: usize = 1879048217;
pub const DT_MIPS_DELTA_INSTANCE_NO: usize = 1879048218;
pub const DT_MIPS_DELTA_RELOC: usize = 1879048219;
pub const DT_MIPS_DELTA_RELOC_NO: usize = 1879048220;
pub const DT_MIPS_DELTA_SYM: usize = 1879048221;
pub const DT_MIPS_DELTA_SYM_NO: usize = 1879048222;
pub const DT_MIPS_DELTA_CLASSSYM: usize = 1879048224;
pub const DT_MIPS_DELTA_CLASSSYM_NO: usize = 1879048225;
pub const DT_MIPS_CXX_FLAGS: usize = 1879048226;
pub const DT_MIPS_PIXIE_INIT: usize = 1879048227;
pub const DT_MIPS_SYMBOL_LIB: usize = 1879048228;
pub const DT_MIPS_LOCALPAGE_GOTIDX: usize = 1879048229;
pub const DT_MIPS_LOCAL_GOTIDX: usize = 1879048230;
pub const DT_MIPS_HIDDEN_GOTIDX: usize = 1879048231;
pub const DT_MIPS_PROTECTED_GOTIDX: usize = 1879048232;
pub const DT_MIPS_OPTIONS: usize = 1879048233;
pub const DT_MIPS_INTERFACE: usize = 1879048234;
pub const DT_MIPS_DYNSTR_ALIGN: usize = 1879048235;
pub const DT_MIPS_INTERFACE_SIZE: usize = 1879048236;
pub const DT_MIPS_RLD_TEXT_RESOLVE_ADDR: usize = 1879048237;
pub const DT_MIPS_PERF_SUFFIX: usize = 1879048238;
pub const DT_MIPS_COMPACT_SIZE: usize = 1879048239;
pub const DT_MIPS_GP_VALUE: usize = 1879048240;
pub const DT_MIPS_AUX_DYNAMIC: usize = 1879048241;
pub const DT_MIPS_PLTGOT: usize = 1879048242;
pub const DT_MIPS_RWPLT: usize = 1879048244;
pub const DT_MIPS_NUM: usize = 53;
pub const RHF_NONE: usize = 0;
pub const RHF_QUICKSTART: usize = 1;
pub const RHF_NOTPOT: usize = 2;
pub const RHF_NO_LIBRARY_REPLACEMENT: usize = 4;
pub const RHF_NO_MOVE: usize = 8;
pub const RHF_SGI_ONLY: usize = 16;
pub const RHF_GUARANTEE_INIT: usize = 32;
pub const RHF_DELTA_C_PLUS_PLUS: usize = 64;
pub const RHF_GUARANTEE_START_INIT: usize = 128;
pub const RHF_PIXIE: usize = 256;
pub const RHF_DEFAULT_DELAY_LOAD: usize = 512;
pub const RHF_REQUICKSTART: usize = 1024;
pub const RHF_REQUICKSTARTED: usize = 2048;
pub const RHF_CORD: usize = 4096;
pub const RHF_NO_UNRES_UNDEF: usize = 8192;
pub const RHF_RLD_ORDER_SAFE: usize = 16384;
pub const LL_NONE: usize = 0;
pub const LL_EXACT_MATCH: usize = 1;
pub const LL_IGNORE_INT_VER: usize = 2;
pub const LL_REQUIRE_MINOR: usize = 4;
pub const LL_EXPORTS: usize = 8;
pub const LL_DELAY_LOAD: usize = 16;
pub const LL_DELTA: usize = 32;
pub const EF_PARISC_TRAPNIL: usize = 65536;
pub const EF_PARISC_EXT: usize = 131072;
pub const EF_PARISC_LSB: usize = 262144;
pub const EF_PARISC_WIDE: usize = 524288;
pub const EF_PARISC_NO_KABP: usize = 1048576;
pub const EF_PARISC_LAZYSWAP: usize = 4194304;
pub const EF_PARISC_ARCH: usize = 65535;
pub const EFA_PARISC_1_0: usize = 523;
pub const EFA_PARISC_1_1: usize = 528;
pub const EFA_PARISC_2_0: usize = 532;
pub const SHN_PARISC_ANSI_COMMON: usize = 65280;
pub const SHN_PARISC_HUGE_COMMON: usize = 65281;
pub const SHT_PARISC_EXT: usize = 1879048192;
pub const SHT_PARISC_UNWIND: usize = 1879048193;
pub const SHT_PARISC_DOC: usize = 1879048194;
pub const SHF_PARISC_SHORT: usize = 536870912;
pub const SHF_PARISC_HUGE: usize = 1073741824;
pub const SHF_PARISC_SBP: usize = 2147483648;
pub const STT_PARISC_MILLICODE: usize = 13;
pub const STT_HP_OPAQUE: usize = 11;
pub const STT_HP_STUB: usize = 12;
pub const R_PARISC_NONE: usize = 0;
pub const R_PARISC_DIR32: usize = 1;
pub const R_PARISC_DIR21L: usize = 2;
pub const R_PARISC_DIR17R: usize = 3;
pub const R_PARISC_DIR17F: usize = 4;
pub const R_PARISC_DIR14R: usize = 6;
pub const R_PARISC_PCREL32: usize = 9;
pub const R_PARISC_PCREL21L: usize = 10;
pub const R_PARISC_PCREL17R: usize = 11;
pub const R_PARISC_PCREL17F: usize = 12;
pub const R_PARISC_PCREL14R: usize = 14;
pub const R_PARISC_DPREL21L: usize = 18;
pub const R_PARISC_DPREL14R: usize = 22;
pub const R_PARISC_GPREL21L: usize = 26;
pub const R_PARISC_GPREL14R: usize = 30;
pub const R_PARISC_LTOFF21L: usize = 34;
pub const R_PARISC_LTOFF14R: usize = 38;
pub const R_PARISC_SECREL32: usize = 41;
pub const R_PARISC_SEGBASE: usize = 48;
pub const R_PARISC_SEGREL32: usize = 49;
pub const R_PARISC_PLTOFF21L: usize = 50;
pub const R_PARISC_PLTOFF14R: usize = 54;
pub const R_PARISC_LTOFF_FPTR32: usize = 57;
pub const R_PARISC_LTOFF_FPTR21L: usize = 58;
pub const R_PARISC_LTOFF_FPTR14R: usize = 62;
pub const R_PARISC_FPTR64: usize = 64;
pub const R_PARISC_PLABEL32: usize = 65;
pub const R_PARISC_PLABEL21L: usize = 66;
pub const R_PARISC_PLABEL14R: usize = 70;
pub const R_PARISC_PCREL64: usize = 72;
pub const R_PARISC_PCREL22F: usize = 74;
pub const R_PARISC_PCREL14WR: usize = 75;
pub const R_PARISC_PCREL14DR: usize = 76;
pub const R_PARISC_PCREL16F: usize = 77;
pub const R_PARISC_PCREL16WF: usize = 78;
pub const R_PARISC_PCREL16DF: usize = 79;
pub const R_PARISC_DIR64: usize = 80;
pub const R_PARISC_DIR14WR: usize = 83;
pub const R_PARISC_DIR14DR: usize = 84;
pub const R_PARISC_DIR16F: usize = 85;
pub const R_PARISC_DIR16WF: usize = 86;
pub const R_PARISC_DIR16DF: usize = 87;
pub const R_PARISC_GPREL64: usize = 88;
pub const R_PARISC_GPREL14WR: usize = 91;
pub const R_PARISC_GPREL14DR: usize = 92;
pub const R_PARISC_GPREL16F: usize = 93;
pub const R_PARISC_GPREL16WF: usize = 94;
pub const R_PARISC_GPREL16DF: usize = 95;
pub const R_PARISC_LTOFF64: usize = 96;
pub const R_PARISC_LTOFF14WR: usize = 99;
pub const R_PARISC_LTOFF14DR: usize = 100;
pub const R_PARISC_LTOFF16F: usize = 101;
pub const R_PARISC_LTOFF16WF: usize = 102;
pub const R_PARISC_LTOFF16DF: usize = 103;
pub const R_PARISC_SECREL64: usize = 104;
pub const R_PARISC_SEGREL64: usize = 112;
pub const R_PARISC_PLTOFF14WR: usize = 115;
pub const R_PARISC_PLTOFF14DR: usize = 116;
pub const R_PARISC_PLTOFF16F: usize = 117;
pub const R_PARISC_PLTOFF16WF: usize = 118;
pub const R_PARISC_PLTOFF16DF: usize = 119;
pub const R_PARISC_LTOFF_FPTR64: usize = 120;
pub const R_PARISC_LTOFF_FPTR14WR: usize = 123;
pub const R_PARISC_LTOFF_FPTR14DR: usize = 124;
pub const R_PARISC_LTOFF_FPTR16F: usize = 125;
pub const R_PARISC_LTOFF_FPTR16WF: usize = 126;
pub const R_PARISC_LTOFF_FPTR16DF: usize = 127;
pub const R_PARISC_LORESERVE: usize = 128;
pub const R_PARISC_COPY: usize = 128;
pub const R_PARISC_IPLT: usize = 129;
pub const R_PARISC_EPLT: usize = 130;
pub const R_PARISC_TPREL32: usize = 153;
pub const R_PARISC_TPREL21L: usize = 154;
pub const R_PARISC_TPREL14R: usize = 158;
pub const R_PARISC_LTOFF_TP21L: usize = 162;
pub const R_PARISC_LTOFF_TP14R: usize = 166;
pub const R_PARISC_LTOFF_TP14F: usize = 167;
pub const R_PARISC_TPREL64: usize = 216;
pub const R_PARISC_TPREL14WR: usize = 219;
pub const R_PARISC_TPREL14DR: usize = 220;
pub const R_PARISC_TPREL16F: usize = 221;
pub const R_PARISC_TPREL16WF: usize = 222;
pub const R_PARISC_TPREL16DF: usize = 223;
pub const R_PARISC_LTOFF_TP64: usize = 224;
pub const R_PARISC_LTOFF_TP14WR: usize = 227;
pub const R_PARISC_LTOFF_TP14DR: usize = 228;
pub const R_PARISC_LTOFF_TP16F: usize = 229;
pub const R_PARISC_LTOFF_TP16WF: usize = 230;
pub const R_PARISC_LTOFF_TP16DF: usize = 231;
pub const R_PARISC_GNU_VTENTRY: usize = 232;
pub const R_PARISC_GNU_VTINHERIT: usize = 233;
pub const R_PARISC_TLS_GD21L: usize = 234;
pub const R_PARISC_TLS_GD14R: usize = 235;
pub const R_PARISC_TLS_GDCALL: usize = 236;
pub const R_PARISC_TLS_LDM21L: usize = 237;
pub const R_PARISC_TLS_LDM14R: usize = 238;
pub const R_PARISC_TLS_LDMCALL: usize = 239;
pub const R_PARISC_TLS_LDO21L: usize = 240;
pub const R_PARISC_TLS_LDO14R: usize = 241;
pub const R_PARISC_TLS_DTPMOD32: usize = 242;
pub const R_PARISC_TLS_DTPMOD64: usize = 243;
pub const R_PARISC_TLS_DTPOFF32: usize = 244;
pub const R_PARISC_TLS_DTPOFF64: usize = 245;
pub const R_PARISC_TLS_LE21L: usize = 154;
pub const R_PARISC_TLS_LE14R: usize = 158;
pub const R_PARISC_TLS_IE21L: usize = 162;
pub const R_PARISC_TLS_IE14R: usize = 166;
pub const R_PARISC_TLS_TPREL32: usize = 153;
pub const R_PARISC_TLS_TPREL64: usize = 216;
pub const R_PARISC_HIRESERVE: usize = 255;
pub const PT_HP_TLS: usize = 1610612736;
pub const PT_HP_CORE_NONE: usize = 1610612737;
pub const PT_HP_CORE_VERSION: usize = 1610612738;
pub const PT_HP_CORE_KERNEL: usize = 1610612739;
pub const PT_HP_CORE_COMM: usize = 1610612740;
pub const PT_HP_CORE_PROC: usize = 1610612741;
pub const PT_HP_CORE_LOADABLE: usize = 1610612742;
pub const PT_HP_CORE_STACK: usize = 1610612743;
pub const PT_HP_CORE_SHM: usize = 1610612744;
pub const PT_HP_CORE_MMF: usize = 1610612745;
pub const PT_HP_PARALLEL: usize = 1610612752;
pub const PT_HP_FASTBIND: usize = 1610612753;
pub const PT_HP_OPT_ANNOT: usize = 1610612754;
pub const PT_HP_HSL_ANNOT: usize = 1610612755;
pub const PT_HP_STACK: usize = 1610612756;
pub const PT_PARISC_ARCHEXT: usize = 1879048192;
pub const PT_PARISC_UNWIND: usize = 1879048193;
pub const PF_PARISC_SBP: usize = 134217728;
pub const PF_HP_PAGE_SIZE: usize = 1048576;
pub const PF_HP_FAR_SHARED: usize = 2097152;
pub const PF_HP_NEAR_SHARED: usize = 4194304;
pub const PF_HP_CODE: usize = 16777216;
pub const PF_HP_MODIFY: usize = 33554432;
pub const PF_HP_LAZYSWAP: usize = 67108864;
pub const PF_HP_SBP: usize = 134217728;
pub const EF_ALPHA_32BIT: usize = 1;
pub const EF_ALPHA_CANRELAX: usize = 2;
pub const SHT_ALPHA_DEBUG: usize = 1879048193;
pub const SHT_ALPHA_REGINFO: usize = 1879048194;
pub const SHF_ALPHA_GPREL: usize = 268435456;
pub const STO_ALPHA_NOPV: usize = 128;
pub const STO_ALPHA_STD_GPLOAD: usize = 136;
pub const R_ALPHA_NONE: usize = 0;
pub const R_ALPHA_REFLONG: usize = 1;
pub const R_ALPHA_REFQUAD: usize = 2;
pub const R_ALPHA_GPREL32: usize = 3;
pub const R_ALPHA_LITERAL: usize = 4;
pub const R_ALPHA_LITUSE: usize = 5;
pub const R_ALPHA_GPDISP: usize = 6;
pub const R_ALPHA_BRADDR: usize = 7;
pub const R_ALPHA_HINT: usize = 8;
pub const R_ALPHA_SREL16: usize = 9;
pub const R_ALPHA_SREL32: usize = 10;
pub const R_ALPHA_SREL64: usize = 11;
pub const R_ALPHA_GPRELHIGH: usize = 17;
pub const R_ALPHA_GPRELLOW: usize = 18;
pub const R_ALPHA_GPREL16: usize = 19;
pub const R_ALPHA_COPY: usize = 24;
pub const R_ALPHA_GLOB_DAT: usize = 25;
pub const R_ALPHA_JMP_SLOT: usize = 26;
pub const R_ALPHA_RELATIVE: usize = 27;
pub const R_ALPHA_TLS_GD_HI: usize = 28;
pub const R_ALPHA_TLSGD: usize = 29;
pub const R_ALPHA_TLS_LDM: usize = 30;
pub const R_ALPHA_DTPMOD64: usize = 31;
pub const R_ALPHA_GOTDTPREL: usize = 32;
pub const R_ALPHA_DTPREL64: usize = 33;
pub const R_ALPHA_DTPRELHI: usize = 34;
pub const R_ALPHA_DTPRELLO: usize = 35;
pub const R_ALPHA_DTPREL16: usize = 36;
pub const R_ALPHA_GOTTPREL: usize = 37;
pub const R_ALPHA_TPREL64: usize = 38;
pub const R_ALPHA_TPRELHI: usize = 39;
pub const R_ALPHA_TPRELLO: usize = 40;
pub const R_ALPHA_TPREL16: usize = 41;
pub const R_ALPHA_NUM: usize = 46;
pub const LITUSE_ALPHA_ADDR: usize = 0;
pub const LITUSE_ALPHA_BASE: usize = 1;
pub const LITUSE_ALPHA_BYTOFF: usize = 2;
pub const LITUSE_ALPHA_JSR: usize = 3;
pub const LITUSE_ALPHA_TLS_GD: usize = 4;
pub const LITUSE_ALPHA_TLS_LDM: usize = 5;
pub const DT_ALPHA_PLTRO: usize = 1879048192;
pub const DT_ALPHA_NUM: usize = 1;
pub const EF_PPC_EMB: usize = 2147483648;
pub const EF_PPC_RELOCATABLE: usize = 65536;
pub const EF_PPC_RELOCATABLE_LIB: usize = 32768;
pub const R_PPC_NONE: usize = 0;
pub const R_PPC_ADDR32: usize = 1;
pub const R_PPC_ADDR24: usize = 2;
pub const R_PPC_ADDR16: usize = 3;
pub const R_PPC_ADDR16_LO: usize = 4;
pub const R_PPC_ADDR16_HI: usize = 5;
pub const R_PPC_ADDR16_HA: usize = 6;
pub const R_PPC_ADDR14: usize = 7;
pub const R_PPC_ADDR14_BRTAKEN: usize = 8;
pub const R_PPC_ADDR14_BRNTAKEN: usize = 9;
pub const R_PPC_REL24: usize = 10;
pub const R_PPC_REL14: usize = 11;
pub const R_PPC_REL14_BRTAKEN: usize = 12;
pub const R_PPC_REL14_BRNTAKEN: usize = 13;
pub const R_PPC_GOT16: usize = 14;
pub const R_PPC_GOT16_LO: usize = 15;
pub const R_PPC_GOT16_HI: usize = 16;
pub const R_PPC_GOT16_HA: usize = 17;
pub const R_PPC_PLTREL24: usize = 18;
pub const R_PPC_COPY: usize = 19;
pub const R_PPC_GLOB_DAT: usize = 20;
pub const R_PPC_JMP_SLOT: usize = 21;
pub const R_PPC_RELATIVE: usize = 22;
pub const R_PPC_LOCAL24PC: usize = 23;
pub const R_PPC_UADDR32: usize = 24;
pub const R_PPC_UADDR16: usize = 25;
pub const R_PPC_REL32: usize = 26;
pub const R_PPC_PLT32: usize = 27;
pub const R_PPC_PLTREL32: usize = 28;
pub const R_PPC_PLT16_LO: usize = 29;
pub const R_PPC_PLT16_HI: usize = 30;
pub const R_PPC_PLT16_HA: usize = 31;
pub const R_PPC_SDAREL16: usize = 32;
pub const R_PPC_SECTOFF: usize = 33;
pub const R_PPC_SECTOFF_LO: usize = 34;
pub const R_PPC_SECTOFF_HI: usize = 35;
pub const R_PPC_SECTOFF_HA: usize = 36;
pub const R_PPC_TLS: usize = 67;
pub const R_PPC_DTPMOD32: usize = 68;
pub const R_PPC_TPREL16: usize = 69;
pub const R_PPC_TPREL16_LO: usize = 70;
pub const R_PPC_TPREL16_HI: usize = 71;
pub const R_PPC_TPREL16_HA: usize = 72;
pub const R_PPC_TPREL32: usize = 73;
pub const R_PPC_DTPREL16: usize = 74;
pub const R_PPC_DTPREL16_LO: usize = 75;
pub const R_PPC_DTPREL16_HI: usize = 76;
pub const R_PPC_DTPREL16_HA: usize = 77;
pub const R_PPC_DTPREL32: usize = 78;
pub const R_PPC_GOT_TLSGD16: usize = 79;
pub const R_PPC_GOT_TLSGD16_LO: usize = 80;
pub const R_PPC_GOT_TLSGD16_HI: usize = 81;
pub const R_PPC_GOT_TLSGD16_HA: usize = 82;
pub const R_PPC_GOT_TLSLD16: usize = 83;
pub const R_PPC_GOT_TLSLD16_LO: usize = 84;
pub const R_PPC_GOT_TLSLD16_HI: usize = 85;
pub const R_PPC_GOT_TLSLD16_HA: usize = 86;
pub const R_PPC_GOT_TPREL16: usize = 87;
pub const R_PPC_GOT_TPREL16_LO: usize = 88;
pub const R_PPC_GOT_TPREL16_HI: usize = 89;
pub const R_PPC_GOT_TPREL16_HA: usize = 90;
pub const R_PPC_GOT_DTPREL16: usize = 91;
pub const R_PPC_GOT_DTPREL16_LO: usize = 92;
pub const R_PPC_GOT_DTPREL16_HI: usize = 93;
pub const R_PPC_GOT_DTPREL16_HA: usize = 94;
pub const R_PPC_EMB_NADDR32: usize = 101;
pub const R_PPC_EMB_NADDR16: usize = 102;
pub const R_PPC_EMB_NADDR16_LO: usize = 103;
pub const R_PPC_EMB_NADDR16_HI: usize = 104;
pub const R_PPC_EMB_NADDR16_HA: usize = 105;
pub const R_PPC_EMB_SDAI16: usize = 106;
pub const R_PPC_EMB_SDA2I16: usize = 107;
pub const R_PPC_EMB_SDA2REL: usize = 108;
pub const R_PPC_EMB_SDA21: usize = 109;
pub const R_PPC_EMB_MRKREF: usize = 110;
pub const R_PPC_EMB_RELSEC16: usize = 111;
pub const R_PPC_EMB_RELST_LO: usize = 112;
pub const R_PPC_EMB_RELST_HI: usize = 113;
pub const R_PPC_EMB_RELST_HA: usize = 114;
pub const R_PPC_EMB_BIT_FLD: usize = 115;
pub const R_PPC_EMB_RELSDA: usize = 116;
pub const R_PPC_DIAB_SDA21_LO: usize = 180;
pub const R_PPC_DIAB_SDA21_HI: usize = 181;
pub const R_PPC_DIAB_SDA21_HA: usize = 182;
pub const R_PPC_DIAB_RELSDA_LO: usize = 183;
pub const R_PPC_DIAB_RELSDA_HI: usize = 184;
pub const R_PPC_DIAB_RELSDA_HA: usize = 185;
pub const R_PPC_IRELATIVE: usize = 248;
pub const R_PPC_REL16: usize = 249;
pub const R_PPC_REL16_LO: usize = 250;
pub const R_PPC_REL16_HI: usize = 251;
pub const R_PPC_REL16_HA: usize = 252;
pub const R_PPC_TOC16: usize = 255;
pub const DT_PPC_GOT: usize = 1879048192;
pub const DT_PPC_NUM: usize = 1;
pub const R_PPC64_NONE: usize = 0;
pub const R_PPC64_ADDR32: usize = 1;
pub const R_PPC64_ADDR24: usize = 2;
pub const R_PPC64_ADDR16: usize = 3;
pub const R_PPC64_ADDR16_LO: usize = 4;
pub const R_PPC64_ADDR16_HI: usize = 5;
pub const R_PPC64_ADDR16_HA: usize = 6;
pub const R_PPC64_ADDR14: usize = 7;
pub const R_PPC64_ADDR14_BRTAKEN: usize = 8;
pub const R_PPC64_ADDR14_BRNTAKEN: usize = 9;
pub const R_PPC64_REL24: usize = 10;
pub const R_PPC64_REL14: usize = 11;
pub const R_PPC64_REL14_BRTAKEN: usize = 12;
pub const R_PPC64_REL14_BRNTAKEN: usize = 13;
pub const R_PPC64_GOT16: usize = 14;
pub const R_PPC64_GOT16_LO: usize = 15;
pub const R_PPC64_GOT16_HI: usize = 16;
pub const R_PPC64_GOT16_HA: usize = 17;
pub const R_PPC64_COPY: usize = 19;
pub const R_PPC64_GLOB_DAT: usize = 20;
pub const R_PPC64_JMP_SLOT: usize = 21;
pub const R_PPC64_RELATIVE: usize = 22;
pub const R_PPC64_UADDR32: usize = 24;
pub const R_PPC64_UADDR16: usize = 25;
pub const R_PPC64_REL32: usize = 26;
pub const R_PPC64_PLT32: usize = 27;
pub const R_PPC64_PLTREL32: usize = 28;
pub const R_PPC64_PLT16_LO: usize = 29;
pub const R_PPC64_PLT16_HI: usize = 30;
pub const R_PPC64_PLT16_HA: usize = 31;
pub const R_PPC64_SECTOFF: usize = 33;
pub const R_PPC64_SECTOFF_LO: usize = 34;
pub const R_PPC64_SECTOFF_HI: usize = 35;
pub const R_PPC64_SECTOFF_HA: usize = 36;
pub const R_PPC64_ADDR30: usize = 37;
pub const R_PPC64_ADDR64: usize = 38;
pub const R_PPC64_ADDR16_HIGHER: usize = 39;
pub const R_PPC64_ADDR16_HIGHERA: usize = 40;
pub const R_PPC64_ADDR16_HIGHEST: usize = 41;
pub const R_PPC64_ADDR16_HIGHESTA: usize = 42;
pub const R_PPC64_UADDR64: usize = 43;
pub const R_PPC64_REL64: usize = 44;
pub const R_PPC64_PLT64: usize = 45;
pub const R_PPC64_PLTREL64: usize = 46;
pub const R_PPC64_TOC16: usize = 47;
pub const R_PPC64_TOC16_LO: usize = 48;
pub const R_PPC64_TOC16_HI: usize = 49;
pub const R_PPC64_TOC16_HA: usize = 50;
pub const R_PPC64_TOC: usize = 51;
pub const R_PPC64_PLTGOT16: usize = 52;
pub const R_PPC64_PLTGOT16_LO: usize = 53;
pub const R_PPC64_PLTGOT16_HI: usize = 54;
pub const R_PPC64_PLTGOT16_HA: usize = 55;
pub const R_PPC64_ADDR16_DS: usize = 56;
pub const R_PPC64_ADDR16_LO_DS: usize = 57;
pub const R_PPC64_GOT16_DS: usize = 58;
pub const R_PPC64_GOT16_LO_DS: usize = 59;
pub const R_PPC64_PLT16_LO_DS: usize = 60;
pub const R_PPC64_SECTOFF_DS: usize = 61;
pub const R_PPC64_SECTOFF_LO_DS: usize = 62;
pub const R_PPC64_TOC16_DS: usize = 63;
pub const R_PPC64_TOC16_LO_DS: usize = 64;
pub const R_PPC64_PLTGOT16_DS: usize = 65;
pub const R_PPC64_PLTGOT16_LO_DS: usize = 66;
pub const R_PPC64_TLS: usize = 67;
pub const R_PPC64_DTPMOD64: usize = 68;
pub const R_PPC64_TPREL16: usize = 69;
pub const R_PPC64_TPREL16_LO: usize = 70;
pub const R_PPC64_TPREL16_HI: usize = 71;
pub const R_PPC64_TPREL16_HA: usize = 72;
pub const R_PPC64_TPREL64: usize = 73;
pub const R_PPC64_DTPREL16: usize = 74;
pub const R_PPC64_DTPREL16_LO: usize = 75;
pub const R_PPC64_DTPREL16_HI: usize = 76;
pub const R_PPC64_DTPREL16_HA: usize = 77;
pub const R_PPC64_DTPREL64: usize = 78;
pub const R_PPC64_GOT_TLSGD16: usize = 79;
pub const R_PPC64_GOT_TLSGD16_LO: usize = 80;
pub const R_PPC64_GOT_TLSGD16_HI: usize = 81;
pub const R_PPC64_GOT_TLSGD16_HA: usize = 82;
pub const R_PPC64_GOT_TLSLD16: usize = 83;
pub const R_PPC64_GOT_TLSLD16_LO: usize = 84;
pub const R_PPC64_GOT_TLSLD16_HI: usize = 85;
pub const R_PPC64_GOT_TLSLD16_HA: usize = 86;
pub const R_PPC64_GOT_TPREL16_DS: usize = 87;
pub const R_PPC64_GOT_TPREL16_LO_DS: usize = 88;
pub const R_PPC64_GOT_TPREL16_HI: usize = 89;
pub const R_PPC64_GOT_TPREL16_HA: usize = 90;
pub const R_PPC64_GOT_DTPREL16_DS: usize = 91;
pub const R_PPC64_GOT_DTPREL16_LO_DS: usize = 92;
pub const R_PPC64_GOT_DTPREL16_HI: usize = 93;
pub const R_PPC64_GOT_DTPREL16_HA: usize = 94;
pub const R_PPC64_TPREL16_DS: usize = 95;
pub const R_PPC64_TPREL16_LO_DS: usize = 96;
pub const R_PPC64_TPREL16_HIGHER: usize = 97;
pub const R_PPC64_TPREL16_HIGHERA: usize = 98;
pub const R_PPC64_TPREL16_HIGHEST: usize = 99;
pub const R_PPC64_TPREL16_HIGHESTA: usize = 100;
pub const R_PPC64_DTPREL16_DS: usize = 101;
pub const R_PPC64_DTPREL16_LO_DS: usize = 102;
pub const R_PPC64_DTPREL16_HIGHER: usize = 103;
pub const R_PPC64_DTPREL16_HIGHERA: usize = 104;
pub const R_PPC64_DTPREL16_HIGHEST: usize = 105;
pub const R_PPC64_DTPREL16_HIGHESTA: usize = 106;
pub const R_PPC64_TLSGD: usize = 107;
pub const R_PPC64_TLSLD: usize = 108;
pub const R_PPC64_TOCSAVE: usize = 109;
pub const R_PPC64_ADDR16_HIGH: usize = 110;
pub const R_PPC64_ADDR16_HIGHA: usize = 111;
pub const R_PPC64_TPREL16_HIGH: usize = 112;
pub const R_PPC64_TPREL16_HIGHA: usize = 113;
pub const R_PPC64_DTPREL16_HIGH: usize = 114;
pub const R_PPC64_DTPREL16_HIGHA: usize = 115;
pub const R_PPC64_JMP_IREL: usize = 247;
pub const R_PPC64_IRELATIVE: usize = 248;
pub const R_PPC64_REL16: usize = 249;
pub const R_PPC64_REL16_LO: usize = 250;
pub const R_PPC64_REL16_HI: usize = 251;
pub const R_PPC64_REL16_HA: usize = 252;
pub const EF_PPC64_ABI: usize = 3;
pub const DT_PPC64_GLINK: usize = 1879048192;
pub const DT_PPC64_OPD: usize = 1879048193;
pub const DT_PPC64_OPDSZ: usize = 1879048194;
pub const DT_PPC64_OPT: usize = 1879048195;
pub const DT_PPC64_NUM: usize = 3;
pub const PPC64_OPT_TLS: usize = 1;
pub const PPC64_OPT_MULTI_TOC: usize = 2;
pub const STO_PPC64_LOCAL_BIT: usize = 5;
pub const STO_PPC64_LOCAL_MASK: usize = 224;
pub const EF_ARM_RELEXEC: usize = 1;
pub const EF_ARM_HASENTRY: usize = 2;
pub const EF_ARM_INTERWORK: usize = 4;
pub const EF_ARM_APCS_26: usize = 8;
pub const EF_ARM_APCS_FLOAT: usize = 16;
pub const EF_ARM_PIC: usize = 32;
pub const EF_ARM_ALIGN8: usize = 64;
pub const EF_ARM_NEW_ABI: usize = 128;
pub const EF_ARM_OLD_ABI: usize = 256;
pub const EF_ARM_SOFT_FLOAT: usize = 512;
pub const EF_ARM_VFP_FLOAT: usize = 1024;
pub const EF_ARM_MAVERICK_FLOAT: usize = 2048;
pub const EF_ARM_ABI_FLOAT_SOFT: usize = 512;
pub const EF_ARM_ABI_FLOAT_HARD: usize = 1024;
pub const EF_ARM_SYMSARESORTED: usize = 4;
pub const EF_ARM_DYNSYMSUSESEGIDX: usize = 8;
pub const EF_ARM_MAPSYMSFIRST: usize = 16;
pub const EF_ARM_BE8: usize = 8388608;
pub const EF_ARM_LE8: usize = 4194304;
pub const EF_ARM_EABI_UNKNOWN: usize = 0;
pub const EF_ARM_EABI_VER1: usize = 16777216;
pub const EF_ARM_EABI_VER2: usize = 33554432;
pub const EF_ARM_EABI_VER3: usize = 50331648;
pub const EF_ARM_EABI_VER4: usize = 67108864;
pub const EF_ARM_EABI_VER5: usize = 83886080;
pub const STT_ARM_TFUNC: usize = 13;
pub const STT_ARM_16BIT: usize = 15;
pub const SHF_ARM_ENTRYSECT: usize = 268435456;
pub const SHF_ARM_COMDEF: usize = 2147483648;
pub const PF_ARM_SB: usize = 268435456;
pub const PF_ARM_PI: usize = 536870912;
pub const PF_ARM_ABS: usize = 1073741824;
pub const PT_ARM_EXIDX: usize = 1879048193;
pub const SHT_ARM_EXIDX: usize = 1879048193;
pub const SHT_ARM_PREEMPTMAP: usize = 1879048194;
pub const SHT_ARM_ATTRIBUTES: usize = 1879048195;
pub const R_AARCH64_NONE: usize = 0;
pub const R_AARCH64_ABS64: usize = 257;
pub const R_AARCH64_ABS32: usize = 258;
pub const R_AARCH64_ABS16: usize = 259;
pub const R_AARCH64_PREL64: usize = 260;
pub const R_AARCH64_PREL32: usize = 261;
pub const R_AARCH64_PREL16: usize = 262;
pub const R_AARCH64_MOVW_UABS_G0: usize = 263;
pub const R_AARCH64_MOVW_UABS_G0_NC: usize = 264;
pub const R_AARCH64_MOVW_UABS_G1: usize = 265;
pub const R_AARCH64_MOVW_UABS_G1_NC: usize = 266;
pub const R_AARCH64_MOVW_UABS_G2: usize = 267;
pub const R_AARCH64_MOVW_UABS_G2_NC: usize = 268;
pub const R_AARCH64_MOVW_UABS_G3: usize = 269;
pub const R_AARCH64_MOVW_SABS_G0: usize = 270;
pub const R_AARCH64_MOVW_SABS_G1: usize = 271;
pub const R_AARCH64_MOVW_SABS_G2: usize = 272;
pub const R_AARCH64_LD_PREL_LO19: usize = 273;
pub const R_AARCH64_ADR_PREL_LO21: usize = 274;
pub const R_AARCH64_ADR_PREL_PG_HI21: usize = 275;
pub const R_AARCH64_ADR_PREL_PG_HI21_NC: usize = 276;
pub const R_AARCH64_ADD_ABS_LO12_NC: usize = 277;
pub const R_AARCH64_LDST8_ABS_LO12_NC: usize = 278;
pub const R_AARCH64_TSTBR14: usize = 279;
pub const R_AARCH64_CONDBR19: usize = 280;
pub const R_AARCH64_JUMP26: usize = 282;
pub const R_AARCH64_CALL26: usize = 283;
pub const R_AARCH64_LDST16_ABS_LO12_NC: usize = 284;
pub const R_AARCH64_LDST32_ABS_LO12_NC: usize = 285;
pub const R_AARCH64_LDST64_ABS_LO12_NC: usize = 286;
pub const R_AARCH64_MOVW_PREL_G0: usize = 287;
pub const R_AARCH64_MOVW_PREL_G0_NC: usize = 288;
pub const R_AARCH64_MOVW_PREL_G1: usize = 289;
pub const R_AARCH64_MOVW_PREL_G1_NC: usize = 290;
pub const R_AARCH64_MOVW_PREL_G2: usize = 291;
pub const R_AARCH64_MOVW_PREL_G2_NC: usize = 292;
pub const R_AARCH64_MOVW_PREL_G3: usize = 293;
pub const R_AARCH64_LDST128_ABS_LO12_NC: usize = 299;
pub const R_AARCH64_MOVW_GOTOFF_G0: usize = 300;
pub const R_AARCH64_MOVW_GOTOFF_G0_NC: usize = 301;
pub const R_AARCH64_MOVW_GOTOFF_G1: usize = 302;
pub const R_AARCH64_MOVW_GOTOFF_G1_NC: usize = 303;
pub const R_AARCH64_MOVW_GOTOFF_G2: usize = 304;
pub const R_AARCH64_MOVW_GOTOFF_G2_NC: usize = 305;
pub const R_AARCH64_MOVW_GOTOFF_G3: usize = 306;
pub const R_AARCH64_GOTREL64: usize = 307;
pub const R_AARCH64_GOTREL32: usize = 308;
pub const R_AARCH64_GOT_LD_PREL19: usize = 309;
pub const R_AARCH64_LD64_GOTOFF_LO15: usize = 310;
pub const R_AARCH64_ADR_GOT_PAGE: usize = 311;
pub const R_AARCH64_LD64_GOT_LO12_NC: usize = 312;
pub const R_AARCH64_LD64_GOTPAGE_LO15: usize = 313;
pub const R_AARCH64_TLSGD_ADR_PREL21: usize = 512;
pub const R_AARCH64_TLSGD_ADR_PAGE21: usize = 513;
pub const R_AARCH64_TLSGD_ADD_LO12_NC: usize = 514;
pub const R_AARCH64_TLSGD_MOVW_G1: usize = 515;
pub const R_AARCH64_TLSGD_MOVW_G0_NC: usize = 516;
pub const R_AARCH64_TLSLD_ADR_PREL21: usize = 517;
pub const R_AARCH64_TLSLD_ADR_PAGE21: usize = 518;
pub const R_AARCH64_TLSLD_ADD_LO12_NC: usize = 519;
pub const R_AARCH64_TLSLD_MOVW_G1: usize = 520;
pub const R_AARCH64_TLSLD_MOVW_G0_NC: usize = 521;
pub const R_AARCH64_TLSLD_LD_PREL19: usize = 522;
pub const R_AARCH64_TLSLD_MOVW_DTPREL_G2: usize = 523;
pub const R_AARCH64_TLSLD_MOVW_DTPREL_G1: usize = 524;
pub const R_AARCH64_TLSLD_MOVW_DTPREL_G1_NC: usize = 525;
pub const R_AARCH64_TLSLD_MOVW_DTPREL_G0: usize = 526;
pub const R_AARCH64_TLSLD_MOVW_DTPREL_G0_NC: usize = 527;
pub const R_AARCH64_TLSLD_ADD_DTPREL_HI12: usize = 528;
pub const R_AARCH64_TLSLD_ADD_DTPREL_LO12: usize = 529;
pub const R_AARCH64_TLSLD_ADD_DTPREL_LO12_NC: usize = 530;
pub const R_AARCH64_TLSLD_LDST8_DTPREL_LO12: usize = 531;
pub const R_AARCH64_TLSLD_LDST8_DTPREL_LO12_NC: usize = 532;
pub const R_AARCH64_TLSLD_LDST16_DTPREL_LO12: usize = 533;
pub const R_AARCH64_TLSLD_LDST16_DTPREL_LO12_NC: usize = 534;
pub const R_AARCH64_TLSLD_LDST32_DTPREL_LO12: usize = 535;
pub const R_AARCH64_TLSLD_LDST32_DTPREL_LO12_NC: usize = 536;
pub const R_AARCH64_TLSLD_LDST64_DTPREL_LO12: usize = 537;
pub const R_AARCH64_TLSLD_LDST64_DTPREL_LO12_NC: usize = 538;
pub const R_AARCH64_TLSIE_MOVW_GOTTPREL_G1: usize = 539;
pub const R_AARCH64_TLSIE_MOVW_GOTTPREL_G0_NC: usize = 540;
pub const R_AARCH64_TLSIE_ADR_GOTTPREL_PAGE21: usize = 541;
pub const R_AARCH64_TLSIE_LD64_GOTTPREL_LO12_NC: usize = 542;
pub const R_AARCH64_TLSIE_LD_GOTTPREL_PREL19: usize = 543;
pub const R_AARCH64_TLSLE_MOVW_TPREL_G2: usize = 544;
pub const R_AARCH64_TLSLE_MOVW_TPREL_G1: usize = 545;
pub const R_AARCH64_TLSLE_MOVW_TPREL_G1_NC: usize = 546;
pub const R_AARCH64_TLSLE_MOVW_TPREL_G0: usize = 547;
pub const R_AARCH64_TLSLE_MOVW_TPREL_G0_NC: usize = 548;
pub const R_AARCH64_TLSLE_ADD_TPREL_HI12: usize = 549;
pub const R_AARCH64_TLSLE_ADD_TPREL_LO12: usize = 550;
pub const R_AARCH64_TLSLE_ADD_TPREL_LO12_NC: usize = 551;
pub const R_AARCH64_TLSLE_LDST8_TPREL_LO12: usize = 552;
pub const R_AARCH64_TLSLE_LDST8_TPREL_LO12_NC: usize = 553;
pub const R_AARCH64_TLSLE_LDST16_TPREL_LO12: usize = 554;
pub const R_AARCH64_TLSLE_LDST16_TPREL_LO12_NC: usize = 555;
pub const R_AARCH64_TLSLE_LDST32_TPREL_LO12: usize = 556;
pub const R_AARCH64_TLSLE_LDST32_TPREL_LO12_NC: usize = 557;
pub const R_AARCH64_TLSLE_LDST64_TPREL_LO12: usize = 558;
pub const R_AARCH64_TLSLE_LDST64_TPREL_LO12_NC: usize = 559;
pub const R_AARCH64_TLSDESC_LD_PREL19: usize = 560;
pub const R_AARCH64_TLSDESC_ADR_PREL21: usize = 561;
pub const R_AARCH64_TLSDESC_ADR_PAGE21: usize = 562;
pub const R_AARCH64_TLSDESC_LD64_LO12: usize = 563;
pub const R_AARCH64_TLSDESC_ADD_LO12: usize = 564;
pub const R_AARCH64_TLSDESC_OFF_G1: usize = 565;
pub const R_AARCH64_TLSDESC_OFF_G0_NC: usize = 566;
pub const R_AARCH64_TLSDESC_LDR: usize = 567;
pub const R_AARCH64_TLSDESC_ADD: usize = 568;
pub const R_AARCH64_TLSDESC_CALL: usize = 569;
pub const R_AARCH64_TLSLE_LDST128_TPREL_LO12: usize = 570;
pub const R_AARCH64_TLSLE_LDST128_TPREL_LO12_NC: usize = 571;
pub const R_AARCH64_TLSLD_LDST128_DTPREL_LO12: usize = 572;
pub const R_AARCH64_TLSLD_LDST128_DTPREL_LO12_NC: usize =
    573;
pub const R_AARCH64_COPY: usize = 1024;
pub const R_AARCH64_GLOB_DAT: usize = 1025;
pub const R_AARCH64_JUMP_SLOT: usize = 1026;
pub const R_AARCH64_RELATIVE: usize = 1027;
pub const R_AARCH64_TLS_DTPMOD64: usize = 1028;
pub const R_AARCH64_TLS_DTPREL64: usize = 1029;
pub const R_AARCH64_TLS_TPREL64: usize = 1030;
pub const R_AARCH64_TLSDESC: usize = 1031;
pub const R_AARCH64_IRELATIVE: usize = 1032;
pub const R_ARM_NONE: usize = 0;
pub const R_ARM_PC24: usize = 1;
pub const R_ARM_ABS32: usize = 2;
pub const R_ARM_REL32: usize = 3;
pub const R_ARM_PC13: usize = 4;
pub const R_ARM_ABS16: usize = 5;
pub const R_ARM_ABS12: usize = 6;
pub const R_ARM_THM_ABS5: usize = 7;
pub const R_ARM_ABS8: usize = 8;
pub const R_ARM_SBREL32: usize = 9;
pub const R_ARM_THM_PC22: usize = 10;
pub const R_ARM_THM_PC8: usize = 11;
pub const R_ARM_AMP_VCALL9: usize = 12;
pub const R_ARM_SWI24: usize = 13;
pub const R_ARM_TLS_DESC: usize = 13;
pub const R_ARM_THM_SWI8: usize = 14;
pub const R_ARM_XPC25: usize = 15;
pub const R_ARM_THM_XPC22: usize = 16;
pub const R_ARM_TLS_DTPMOD32: usize = 17;
pub const R_ARM_TLS_DTPOFF32: usize = 18;
pub const R_ARM_TLS_TPOFF32: usize = 19;
pub const R_ARM_COPY: usize = 20;
pub const R_ARM_GLOB_DAT: usize = 21;
pub const R_ARM_JUMP_SLOT: usize = 22;
pub const R_ARM_RELATIVE: usize = 23;
pub const R_ARM_GOTOFF: usize = 24;
pub const R_ARM_GOTPC: usize = 25;
pub const R_ARM_GOT32: usize = 26;
pub const R_ARM_PLT32: usize = 27;
pub const R_ARM_CALL: usize = 28;
pub const R_ARM_JUMP24: usize = 29;
pub const R_ARM_THM_JUMP24: usize = 30;
pub const R_ARM_BASE_ABS: usize = 31;
pub const R_ARM_ALU_PCREL_7_0: usize = 32;
pub const R_ARM_ALU_PCREL_15_8: usize = 33;
pub const R_ARM_ALU_PCREL_23_15: usize = 34;
pub const R_ARM_LDR_SBREL_11_0: usize = 35;
pub const R_ARM_ALU_SBREL_19_12: usize = 36;
pub const R_ARM_ALU_SBREL_27_20: usize = 37;
pub const R_ARM_TARGET1: usize = 38;
pub const R_ARM_SBREL31: usize = 39;
pub const R_ARM_V4BX: usize = 40;
pub const R_ARM_TARGET2: usize = 41;
pub const R_ARM_PREL31: usize = 42;
pub const R_ARM_MOVW_ABS_NC: usize = 43;
pub const R_ARM_MOVT_ABS: usize = 44;
pub const R_ARM_MOVW_PREL_NC: usize = 45;
pub const R_ARM_MOVT_PREL: usize = 46;
pub const R_ARM_THM_MOVW_ABS_NC: usize = 47;
pub const R_ARM_THM_MOVT_ABS: usize = 48;
pub const R_ARM_THM_MOVW_PREL_NC: usize = 49;
pub const R_ARM_THM_MOVT_PREL: usize = 50;
pub const R_ARM_THM_JUMP19: usize = 51;
pub const R_ARM_THM_JUMP6: usize = 52;
pub const R_ARM_THM_ALU_PREL_11_0: usize = 53;
pub const R_ARM_THM_PC12: usize = 54;
pub const R_ARM_ABS32_NOI: usize = 55;
pub const R_ARM_REL32_NOI: usize = 56;
pub const R_ARM_ALU_PC_G0_NC: usize = 57;
pub const R_ARM_ALU_PC_G0: usize = 58;
pub const R_ARM_ALU_PC_G1_NC: usize = 59;
pub const R_ARM_ALU_PC_G1: usize = 60;
pub const R_ARM_ALU_PC_G2: usize = 61;
pub const R_ARM_LDR_PC_G1: usize = 62;
pub const R_ARM_LDR_PC_G2: usize = 63;
pub const R_ARM_LDRS_PC_G0: usize = 64;
pub const R_ARM_LDRS_PC_G1: usize = 65;
pub const R_ARM_LDRS_PC_G2: usize = 66;
pub const R_ARM_LDC_PC_G0: usize = 67;
pub const R_ARM_LDC_PC_G1: usize = 68;
pub const R_ARM_LDC_PC_G2: usize = 69;
pub const R_ARM_ALU_SB_G0_NC: usize = 70;
pub const R_ARM_ALU_SB_G0: usize = 71;
pub const R_ARM_ALU_SB_G1_NC: usize = 72;
pub const R_ARM_ALU_SB_G1: usize = 73;
pub const R_ARM_ALU_SB_G2: usize = 74;
pub const R_ARM_LDR_SB_G0: usize = 75;
pub const R_ARM_LDR_SB_G1: usize = 76;
pub const R_ARM_LDR_SB_G2: usize = 77;
pub const R_ARM_LDRS_SB_G0: usize = 78;
pub const R_ARM_LDRS_SB_G1: usize = 79;
pub const R_ARM_LDRS_SB_G2: usize = 80;
pub const R_ARM_LDC_SB_G0: usize = 81;
pub const R_ARM_LDC_SB_G1: usize = 82;
pub const R_ARM_LDC_SB_G2: usize = 83;
pub const R_ARM_MOVW_BREL_NC: usize = 84;
pub const R_ARM_MOVT_BREL: usize = 85;
pub const R_ARM_MOVW_BREL: usize = 86;
pub const R_ARM_THM_MOVW_BREL_NC: usize = 87;
pub const R_ARM_THM_MOVT_BREL: usize = 88;
pub const R_ARM_THM_MOVW_BREL: usize = 89;
pub const R_ARM_TLS_GOTDESC: usize = 90;
pub const R_ARM_TLS_CALL: usize = 91;
pub const R_ARM_TLS_DESCSEQ: usize = 92;
pub const R_ARM_THM_TLS_CALL: usize = 93;
pub const R_ARM_PLT32_ABS: usize = 94;
pub const R_ARM_GOT_ABS: usize = 95;
pub const R_ARM_GOT_PREL: usize = 96;
pub const R_ARM_GOT_BREL12: usize = 97;
pub const R_ARM_GOTOFF12: usize = 98;
pub const R_ARM_GOTRELAX: usize = 99;
pub const R_ARM_GNU_VTENTRY: usize = 100;
pub const R_ARM_GNU_VTINHERIT: usize = 101;
pub const R_ARM_THM_PC11: usize = 102;
pub const R_ARM_THM_PC9: usize = 103;
pub const R_ARM_TLS_GD32: usize = 104;
pub const R_ARM_TLS_LDM32: usize = 105;
pub const R_ARM_TLS_LDO32: usize = 106;
pub const R_ARM_TLS_IE32: usize = 107;
pub const R_ARM_TLS_LE32: usize = 108;
pub const R_ARM_TLS_LDO12: usize = 109;
pub const R_ARM_TLS_LE12: usize = 110;
pub const R_ARM_TLS_IE12GP: usize = 111;
pub const R_ARM_ME_TOO: usize = 128;
pub const R_ARM_THM_TLS_DESCSEQ: usize = 129;
pub const R_ARM_THM_TLS_DESCSEQ16: usize = 129;
pub const R_ARM_THM_TLS_DESCSEQ32: usize = 130;
pub const R_ARM_THM_GOT_BREL12: usize = 131;
pub const R_ARM_IRELATIVE: usize = 160;
pub const R_ARM_RXPC25: usize = 249;
pub const R_ARM_RSBREL32: usize = 250;
pub const R_ARM_THM_RPC22: usize = 251;
pub const R_ARM_RREL32: usize = 252;
pub const R_ARM_RABS22: usize = 253;
pub const R_ARM_RPC24: usize = 254;
pub const R_ARM_RBASE: usize = 255;
pub const R_ARM_NUM: usize = 256;
pub const EF_IA_64_MASKOS: usize = 15;
pub const EF_IA_64_ABI64: usize = 16;
pub const EF_IA_64_ARCH: usize = 4278190080;
pub const PT_IA_64_ARCHEXT: usize = 1879048192;
pub const PT_IA_64_UNWIND: usize = 1879048193;
pub const PT_IA_64_HP_OPT_ANOT: usize = 1610612754;
pub const PT_IA_64_HP_HSL_ANOT: usize = 1610612755;
pub const PT_IA_64_HP_STACK: usize = 1610612756;
pub const PF_IA_64_NORECOV: usize = 2147483648;
pub const SHT_IA_64_EXT: usize = 1879048192;
pub const SHT_IA_64_UNWIND: usize = 1879048193;
pub const SHF_IA_64_SHORT: usize = 268435456;
pub const SHF_IA_64_NORECOV: usize = 536870912;
pub const DT_IA_64_PLT_RESERVE: usize = 1879048192;
pub const DT_IA_64_NUM: usize = 1;
pub const R_IA64_NONE: usize = 0;
pub const R_IA64_IMM14: usize = 33;
pub const R_IA64_IMM22: usize = 34;
pub const R_IA64_IMM64: usize = 35;
pub const R_IA64_DIR32MSB: usize = 36;
pub const R_IA64_DIR32LSB: usize = 37;
pub const R_IA64_DIR64MSB: usize = 38;
pub const R_IA64_DIR64LSB: usize = 39;
pub const R_IA64_GPREL22: usize = 42;
pub const R_IA64_GPREL64I: usize = 43;
pub const R_IA64_GPREL32MSB: usize = 44;
pub const R_IA64_GPREL32LSB: usize = 45;
pub const R_IA64_GPREL64MSB: usize = 46;
pub const R_IA64_GPREL64LSB: usize = 47;
pub const R_IA64_LTOFF22: usize = 50;
pub const R_IA64_LTOFF64I: usize = 51;
pub const R_IA64_PLTOFF22: usize = 58;
pub const R_IA64_PLTOFF64I: usize = 59;
pub const R_IA64_PLTOFF64MSB: usize = 62;
pub const R_IA64_PLTOFF64LSB: usize = 63;
pub const R_IA64_FPTR64I: usize = 67;
pub const R_IA64_FPTR32MSB: usize = 68;
pub const R_IA64_FPTR32LSB: usize = 69;
pub const R_IA64_FPTR64MSB: usize = 70;
pub const R_IA64_FPTR64LSB: usize = 71;
pub const R_IA64_PCREL60B: usize = 72;
pub const R_IA64_PCREL21B: usize = 73;
pub const R_IA64_PCREL21M: usize = 74;
pub const R_IA64_PCREL21F: usize = 75;
pub const R_IA64_PCREL32MSB: usize = 76;
pub const R_IA64_PCREL32LSB: usize = 77;
pub const R_IA64_PCREL64MSB: usize = 78;
pub const R_IA64_PCREL64LSB: usize = 79;
pub const R_IA64_LTOFF_FPTR22: usize = 82;
pub const R_IA64_LTOFF_FPTR64I: usize = 83;
pub const R_IA64_LTOFF_FPTR32MSB: usize = 84;
pub const R_IA64_LTOFF_FPTR32LSB: usize = 85;
pub const R_IA64_LTOFF_FPTR64MSB: usize = 86;
pub const R_IA64_LTOFF_FPTR64LSB: usize = 87;
pub const R_IA64_SEGREL32MSB: usize = 92;
pub const R_IA64_SEGREL32LSB: usize = 93;
pub const R_IA64_SEGREL64MSB: usize = 94;
pub const R_IA64_SEGREL64LSB: usize = 95;
pub const R_IA64_SECREL32MSB: usize = 100;
pub const R_IA64_SECREL32LSB: usize = 101;
pub const R_IA64_SECREL64MSB: usize = 102;
pub const R_IA64_SECREL64LSB: usize = 103;
pub const R_IA64_REL32MSB: usize = 108;
pub const R_IA64_REL32LSB: usize = 109;
pub const R_IA64_REL64MSB: usize = 110;
pub const R_IA64_REL64LSB: usize = 111;
pub const R_IA64_LTV32MSB: usize = 116;
pub const R_IA64_LTV32LSB: usize = 117;
pub const R_IA64_LTV64MSB: usize = 118;
pub const R_IA64_LTV64LSB: usize = 119;
pub const R_IA64_PCREL21BI: usize = 121;
pub const R_IA64_PCREL22: usize = 122;
pub const R_IA64_PCREL64I: usize = 123;
pub const R_IA64_IPLTMSB: usize = 128;
pub const R_IA64_IPLTLSB: usize = 129;
pub const R_IA64_COPY: usize = 132;
pub const R_IA64_SUB: usize = 133;
pub const R_IA64_LTOFF22X: usize = 134;
pub const R_IA64_LDXMOV: usize = 135;
pub const R_IA64_TPREL14: usize = 145;
pub const R_IA64_TPREL22: usize = 146;
pub const R_IA64_TPREL64I: usize = 147;
pub const R_IA64_TPREL64MSB: usize = 150;
pub const R_IA64_TPREL64LSB: usize = 151;
pub const R_IA64_LTOFF_TPREL22: usize = 154;
pub const R_IA64_DTPMOD64MSB: usize = 166;
pub const R_IA64_DTPMOD64LSB: usize = 167;
pub const R_IA64_LTOFF_DTPMOD22: usize = 170;
pub const R_IA64_DTPREL14: usize = 177;
pub const R_IA64_DTPREL22: usize = 178;
pub const R_IA64_DTPREL64I: usize = 179;
pub const R_IA64_DTPREL32MSB: usize = 180;
pub const R_IA64_DTPREL32LSB: usize = 181;
pub const R_IA64_DTPREL64MSB: usize = 182;
pub const R_IA64_DTPREL64LSB: usize = 183;
pub const R_IA64_LTOFF_DTPREL22: usize = 186;
pub const EF_SH_MACH_MASK: usize = 31;
pub const EF_SH_UNKNOWN: usize = 0;
pub const EF_SH1: usize = 1;
pub const EF_SH2: usize = 2;
pub const EF_SH3: usize = 3;
pub const EF_SH_DSP: usize = 4;
pub const EF_SH3_DSP: usize = 5;
pub const EF_SH4AL_DSP: usize = 6;
pub const EF_SH3E: usize = 8;
pub const EF_SH4: usize = 9;
pub const EF_SH2E: usize = 11;
pub const EF_SH4A: usize = 12;
pub const EF_SH2A: usize = 13;
pub const EF_SH4_NOFPU: usize = 16;
pub const EF_SH4A_NOFPU: usize = 17;
pub const EF_SH4_NOMMU_NOFPU: usize = 18;
pub const EF_SH2A_NOFPU: usize = 19;
pub const EF_SH3_NOMMU: usize = 20;
pub const EF_SH2A_SH4_NOFPU: usize = 21;
pub const EF_SH2A_SH3_NOFPU: usize = 22;
pub const EF_SH2A_SH4: usize = 23;
pub const EF_SH2A_SH3E: usize = 24;
pub const R_SH_NONE: usize = 0;
pub const R_SH_DIR32: usize = 1;
pub const R_SH_REL32: usize = 2;
pub const R_SH_DIR8WPN: usize = 3;
pub const R_SH_IND12W: usize = 4;
pub const R_SH_DIR8WPL: usize = 5;
pub const R_SH_DIR8WPZ: usize = 6;
pub const R_SH_DIR8BP: usize = 7;
pub const R_SH_DIR8W: usize = 8;
pub const R_SH_DIR8L: usize = 9;
pub const R_SH_SWITCH16: usize = 25;
pub const R_SH_SWITCH32: usize = 26;
pub const R_SH_USES: usize = 27;
pub const R_SH_COUNT: usize = 28;
pub const R_SH_ALIGN: usize = 29;
pub const R_SH_CODE: usize = 30;
pub const R_SH_DATA: usize = 31;
pub const R_SH_LABEL: usize = 32;
pub const R_SH_SWITCH8: usize = 33;
pub const R_SH_GNU_VTINHERIT: usize = 34;
pub const R_SH_GNU_VTENTRY: usize = 35;
pub const R_SH_TLS_GD_32: usize = 144;
pub const R_SH_TLS_LD_32: usize = 145;
pub const R_SH_TLS_LDO_32: usize = 146;
pub const R_SH_TLS_IE_32: usize = 147;
pub const R_SH_TLS_LE_32: usize = 148;
pub const R_SH_TLS_DTPMOD32: usize = 149;
pub const R_SH_TLS_DTPOFF32: usize = 150;
pub const R_SH_TLS_TPOFF32: usize = 151;
pub const R_SH_GOT32: usize = 160;
pub const R_SH_PLT32: usize = 161;
pub const R_SH_COPY: usize = 162;
pub const R_SH_GLOB_DAT: usize = 163;
pub const R_SH_JMP_SLOT: usize = 164;
pub const R_SH_RELATIVE: usize = 165;
pub const R_SH_GOTOFF: usize = 166;
pub const R_SH_GOTPC: usize = 167;
pub const R_SH_NUM: usize = 256;
pub const EF_S390_HIGH_GPRS: usize = 1;
pub const R_390_NONE: usize = 0;
pub const R_390_8: usize = 1;
pub const R_390_12: usize = 2;
pub const R_390_16: usize = 3;
pub const R_390_32: usize = 4;
pub const R_390_PC32: usize = 5;
pub const R_390_GOT12: usize = 6;
pub const R_390_GOT32: usize = 7;
pub const R_390_PLT32: usize = 8;
pub const R_390_COPY: usize = 9;
pub const R_390_GLOB_DAT: usize = 10;
pub const R_390_JMP_SLOT: usize = 11;
pub const R_390_RELATIVE: usize = 12;
pub const R_390_GOTOFF32: usize = 13;
pub const R_390_GOTPC: usize = 14;
pub const R_390_GOT16: usize = 15;
pub const R_390_PC16: usize = 16;
pub const R_390_PC16DBL: usize = 17;
pub const R_390_PLT16DBL: usize = 18;
pub const R_390_PC32DBL: usize = 19;
pub const R_390_PLT32DBL: usize = 20;
pub const R_390_GOTPCDBL: usize = 21;
pub const R_390_64: usize = 22;
pub const R_390_PC64: usize = 23;
pub const R_390_GOT64: usize = 24;
pub const R_390_PLT64: usize = 25;
pub const R_390_GOTENT: usize = 26;
pub const R_390_GOTOFF16: usize = 27;
pub const R_390_GOTOFF64: usize = 28;
pub const R_390_GOTPLT12: usize = 29;
pub const R_390_GOTPLT16: usize = 30;
pub const R_390_GOTPLT32: usize = 31;
pub const R_390_GOTPLT64: usize = 32;
pub const R_390_GOTPLTENT: usize = 33;
pub const R_390_PLTOFF16: usize = 34;
pub const R_390_PLTOFF32: usize = 35;
pub const R_390_PLTOFF64: usize = 36;
pub const R_390_TLS_LOAD: usize = 37;
pub const R_390_TLS_GDCALL: usize = 38;
pub const R_390_TLS_LDCALL: usize = 39;
pub const R_390_TLS_GD32: usize = 40;
pub const R_390_TLS_GD64: usize = 41;
pub const R_390_TLS_GOTIE12: usize = 42;
pub const R_390_TLS_GOTIE32: usize = 43;
pub const R_390_TLS_GOTIE64: usize = 44;
pub const R_390_TLS_LDM32: usize = 45;
pub const R_390_TLS_LDM64: usize = 46;
pub const R_390_TLS_IE32: usize = 47;
pub const R_390_TLS_IE64: usize = 48;
pub const R_390_TLS_IEENT: usize = 49;
pub const R_390_TLS_LE32: usize = 50;
pub const R_390_TLS_LE64: usize = 51;
pub const R_390_TLS_LDO32: usize = 52;
pub const R_390_TLS_LDO64: usize = 53;
pub const R_390_TLS_DTPMOD: usize = 54;
pub const R_390_TLS_DTPOFF: usize = 55;
pub const R_390_TLS_TPOFF: usize = 56;
pub const R_390_20: usize = 57;
pub const R_390_GOT20: usize = 58;
pub const R_390_GOTPLT20: usize = 59;
pub const R_390_TLS_GOTIE20: usize = 60;
pub const R_390_IRELATIVE: usize = 61;
pub const R_390_NUM: usize = 62;
pub const R_CRIS_NONE: usize = 0;
pub const R_CRIS_8: usize = 1;
pub const R_CRIS_16: usize = 2;
pub const R_CRIS_32: usize = 3;
pub const R_CRIS_8_PCREL: usize = 4;
pub const R_CRIS_16_PCREL: usize = 5;
pub const R_CRIS_32_PCREL: usize = 6;
pub const R_CRIS_GNU_VTINHERIT: usize = 7;
pub const R_CRIS_GNU_VTENTRY: usize = 8;
pub const R_CRIS_COPY: usize = 9;
pub const R_CRIS_GLOB_DAT: usize = 10;
pub const R_CRIS_JUMP_SLOT: usize = 11;
pub const R_CRIS_RELATIVE: usize = 12;
pub const R_CRIS_16_GOT: usize = 13;
pub const R_CRIS_32_GOT: usize = 14;
pub const R_CRIS_16_GOTPLT: usize = 15;
pub const R_CRIS_32_GOTPLT: usize = 16;
pub const R_CRIS_32_GOTREL: usize = 17;
pub const R_CRIS_32_PLT_GOTREL: usize = 18;
pub const R_CRIS_32_PLT_PCREL: usize = 19;
pub const R_CRIS_NUM: usize = 20;
pub const R_X86_64_NONE: usize = 0;
pub const R_X86_64_64: usize = 1;
pub const R_X86_64_PC32: usize = 2;
pub const R_X86_64_GOT32: usize = 3;
pub const R_X86_64_PLT32: usize = 4;
pub const R_X86_64_COPY: usize = 5;
pub const R_X86_64_GLOB_DAT: usize = 6;
pub const R_X86_64_JUMP_SLOT: usize = 7;
pub const R_X86_64_RELATIVE: usize = 8;
pub const R_X86_64_GOTPCREL: usize = 9;
pub const R_X86_64_32: usize = 10;
pub const R_X86_64_32S: usize = 11;
pub const R_X86_64_16: usize = 12;
pub const R_X86_64_PC16: usize = 13;
pub const R_X86_64_8: usize = 14;
pub const R_X86_64_PC8: usize = 15;
pub const R_X86_64_DTPMOD64: usize = 16;
pub const R_X86_64_DTPOFF64: usize = 17;
pub const R_X86_64_TPOFF64: usize = 18;
pub const R_X86_64_TLSGD: usize = 19;
pub const R_X86_64_TLSLD: usize = 20;
pub const R_X86_64_DTPOFF32: usize = 21;
pub const R_X86_64_GOTTPOFF: usize = 22;
pub const R_X86_64_TPOFF32: usize = 23;
pub const R_X86_64_PC64: usize = 24;
pub const R_X86_64_GOTOFF64: usize = 25;
pub const R_X86_64_GOTPC32: usize = 26;
pub const R_X86_64_GOT64: usize = 27;
pub const R_X86_64_GOTPCREL64: usize = 28;
pub const R_X86_64_GOTPC64: usize = 29;
pub const R_X86_64_GOTPLT64: usize = 30;
pub const R_X86_64_PLTOFF64: usize = 31;
pub const R_X86_64_SIZE32: usize = 32;
pub const R_X86_64_SIZE64: usize = 33;
pub const R_X86_64_GOTPC32_TLSDESC: usize = 34;
pub const R_X86_64_TLSDESC_CALL: usize = 35;
pub const R_X86_64_TLSDESC: usize = 36;
pub const R_X86_64_IRELATIVE: usize = 37;
pub const R_X86_64_RELATIVE64: usize = 38;
pub const R_X86_64_NUM: usize = 39;
pub const R_MN10300_NONE: usize = 0;
pub const R_MN10300_32: usize = 1;
pub const R_MN10300_16: usize = 2;
pub const R_MN10300_8: usize = 3;
pub const R_MN10300_PCREL32: usize = 4;
pub const R_MN10300_PCREL16: usize = 5;
pub const R_MN10300_PCREL8: usize = 6;
pub const R_MN10300_GNU_VTINHERIT: usize = 7;
pub const R_MN10300_GNU_VTENTRY: usize = 8;
pub const R_MN10300_24: usize = 9;
pub const R_MN10300_GOTPC32: usize = 10;
pub const R_MN10300_GOTPC16: usize = 11;
pub const R_MN10300_GOTOFF32: usize = 12;
pub const R_MN10300_GOTOFF24: usize = 13;
pub const R_MN10300_GOTOFF16: usize = 14;
pub const R_MN10300_PLT32: usize = 15;
pub const R_MN10300_PLT16: usize = 16;
pub const R_MN10300_GOT32: usize = 17;
pub const R_MN10300_GOT24: usize = 18;
pub const R_MN10300_GOT16: usize = 19;
pub const R_MN10300_COPY: usize = 20;
pub const R_MN10300_GLOB_DAT: usize = 21;
pub const R_MN10300_JMP_SLOT: usize = 22;
pub const R_MN10300_RELATIVE: usize = 23;
pub const R_MN10300_TLS_GD: usize = 24;
pub const R_MN10300_TLS_LD: usize = 25;
pub const R_MN10300_TLS_LDO: usize = 26;
pub const R_MN10300_TLS_GOTIE: usize = 27;
pub const R_MN10300_TLS_IE: usize = 28;
pub const R_MN10300_TLS_LE: usize = 29;
pub const R_MN10300_TLS_DTPMOD: usize = 30;
pub const R_MN10300_TLS_DTPOFF: usize = 31;
pub const R_MN10300_TLS_TPOFF: usize = 32;
pub const R_MN10300_SYM_DIFF: usize = 33;
pub const R_MN10300_ALIGN: usize = 34;
pub const R_MN10300_NUM: usize = 35;
pub const R_M32R_NONE: usize = 0;
pub const R_M32R_16: usize = 1;
pub const R_M32R_32: usize = 2;
pub const R_M32R_24: usize = 3;
pub const R_M32R_10_PCREL: usize = 4;
pub const R_M32R_18_PCREL: usize = 5;
pub const R_M32R_26_PCREL: usize = 6;
pub const R_M32R_HI16_ULO: usize = 7;
pub const R_M32R_HI16_SLO: usize = 8;
pub const R_M32R_LO16: usize = 9;
pub const R_M32R_SDA16: usize = 10;
pub const R_M32R_GNU_VTINHERIT: usize = 11;
pub const R_M32R_GNU_VTENTRY: usize = 12;
pub const R_M32R_16_RELA: usize = 33;
pub const R_M32R_32_RELA: usize = 34;
pub const R_M32R_24_RELA: usize = 35;
pub const R_M32R_10_PCREL_RELA: usize = 36;
pub const R_M32R_18_PCREL_RELA: usize = 37;
pub const R_M32R_26_PCREL_RELA: usize = 38;
pub const R_M32R_HI16_ULO_RELA: usize = 39;
pub const R_M32R_HI16_SLO_RELA: usize = 40;
pub const R_M32R_LO16_RELA: usize = 41;
pub const R_M32R_SDA16_RELA: usize = 42;
pub const R_M32R_RELA_GNU_VTINHERIT: usize = 43;
pub const R_M32R_RELA_GNU_VTENTRY: usize = 44;
pub const R_M32R_REL32: usize = 45;
pub const R_M32R_GOT24: usize = 48;
pub const R_M32R_26_PLTREL: usize = 49;
pub const R_M32R_COPY: usize = 50;
pub const R_M32R_GLOB_DAT: usize = 51;
pub const R_M32R_JMP_SLOT: usize = 52;
pub const R_M32R_RELATIVE: usize = 53;
pub const R_M32R_GOTOFF: usize = 54;
pub const R_M32R_GOTPC24: usize = 55;
pub const R_M32R_GOT16_HI_ULO: usize = 56;
pub const R_M32R_GOT16_HI_SLO: usize = 57;
pub const R_M32R_GOT16_LO: usize = 58;
pub const R_M32R_GOTPC_HI_ULO: usize = 59;
pub const R_M32R_GOTPC_HI_SLO: usize = 60;
pub const R_M32R_GOTPC_LO: usize = 61;
pub const R_M32R_GOTOFF_HI_ULO: usize = 62;
pub const R_M32R_GOTOFF_HI_SLO: usize = 63;
pub const R_M32R_GOTOFF_LO: usize = 64;
pub const R_M32R_NUM: usize = 256;
pub const R_MICROBLAZE_NONE: usize = 0;
pub const R_MICROBLAZE_32: usize = 1;
pub const R_MICROBLAZE_32_PCREL: usize = 2;
pub const R_MICROBLAZE_64_PCREL: usize = 3;
pub const R_MICROBLAZE_32_PCREL_LO: usize = 4;
pub const R_MICROBLAZE_64: usize = 5;
pub const R_MICROBLAZE_32_LO: usize = 6;
pub const R_MICROBLAZE_SRO32: usize = 7;
pub const R_MICROBLAZE_SRW32: usize = 8;
pub const R_MICROBLAZE_64_NONE: usize = 9;
pub const R_MICROBLAZE_32_SYM_OP_SYM: usize = 10;
pub const R_MICROBLAZE_GNU_VTINHERIT: usize = 11;
pub const R_MICROBLAZE_GNU_VTENTRY: usize = 12;
pub const R_MICROBLAZE_GOTPC_64: usize = 13;
pub const R_MICROBLAZE_GOT_64: usize = 14;
pub const R_MICROBLAZE_PLT_64: usize = 15;
pub const R_MICROBLAZE_REL: usize = 16;
pub const R_MICROBLAZE_JUMP_SLOT: usize = 17;
pub const R_MICROBLAZE_GLOB_DAT: usize = 18;
pub const R_MICROBLAZE_GOTOFF_64: usize = 19;
pub const R_MICROBLAZE_GOTOFF_32: usize = 20;
pub const R_MICROBLAZE_COPY: usize = 21;
pub const R_MICROBLAZE_TLS: usize = 22;
pub const R_MICROBLAZE_TLSGD: usize = 23;
pub const R_MICROBLAZE_TLSLD: usize = 24;
pub const R_MICROBLAZE_TLSDTPMOD32: usize = 25;
pub const R_MICROBLAZE_TLSDTPREL32: usize = 26;
pub const R_MICROBLAZE_TLSDTPREL64: usize = 27;
pub const R_MICROBLAZE_TLSGOTTPREL32: usize = 28;
pub const R_MICROBLAZE_TLSTPREL32: usize = 29;
pub const R_TILEPRO_NONE: usize = 0;
pub const R_TILEPRO_32: usize = 1;
pub const R_TILEPRO_16: usize = 2;
pub const R_TILEPRO_8: usize = 3;
pub const R_TILEPRO_32_PCREL: usize = 4;
pub const R_TILEPRO_16_PCREL: usize = 5;
pub const R_TILEPRO_8_PCREL: usize = 6;
pub const R_TILEPRO_LO16: usize = 7;
pub const R_TILEPRO_HI16: usize = 8;
pub const R_TILEPRO_HA16: usize = 9;
pub const R_TILEPRO_COPY: usize = 10;
pub const R_TILEPRO_GLOB_DAT: usize = 11;
pub const R_TILEPRO_JMP_SLOT: usize = 12;
pub const R_TILEPRO_RELATIVE: usize = 13;
pub const R_TILEPRO_BROFF_X1: usize = 14;
pub const R_TILEPRO_JOFFLONG_X1: usize = 15;
pub const R_TILEPRO_JOFFLONG_X1_PLT: usize = 16;
pub const R_TILEPRO_IMM8_X0: usize = 17;
pub const R_TILEPRO_IMM8_Y0: usize = 18;
pub const R_TILEPRO_IMM8_X1: usize = 19;
pub const R_TILEPRO_IMM8_Y1: usize = 20;
pub const R_TILEPRO_MT_IMM15_X1: usize = 21;
pub const R_TILEPRO_MF_IMM15_X1: usize = 22;
pub const R_TILEPRO_IMM16_X0: usize = 23;
pub const R_TILEPRO_IMM16_X1: usize = 24;
pub const R_TILEPRO_IMM16_X0_LO: usize = 25;
pub const R_TILEPRO_IMM16_X1_LO: usize = 26;
pub const R_TILEPRO_IMM16_X0_HI: usize = 27;
pub const R_TILEPRO_IMM16_X1_HI: usize = 28;
pub const R_TILEPRO_IMM16_X0_HA: usize = 29;
pub const R_TILEPRO_IMM16_X1_HA: usize = 30;
pub const R_TILEPRO_IMM16_X0_PCREL: usize = 31;
pub const R_TILEPRO_IMM16_X1_PCREL: usize = 32;
pub const R_TILEPRO_IMM16_X0_LO_PCREL: usize = 33;
pub const R_TILEPRO_IMM16_X1_LO_PCREL: usize = 34;
pub const R_TILEPRO_IMM16_X0_HI_PCREL: usize = 35;
pub const R_TILEPRO_IMM16_X1_HI_PCREL: usize = 36;
pub const R_TILEPRO_IMM16_X0_HA_PCREL: usize = 37;
pub const R_TILEPRO_IMM16_X1_HA_PCREL: usize = 38;
pub const R_TILEPRO_IMM16_X0_GOT: usize = 39;
pub const R_TILEPRO_IMM16_X1_GOT: usize = 40;
pub const R_TILEPRO_IMM16_X0_GOT_LO: usize = 41;
pub const R_TILEPRO_IMM16_X1_GOT_LO: usize = 42;
pub const R_TILEPRO_IMM16_X0_GOT_HI: usize = 43;
pub const R_TILEPRO_IMM16_X1_GOT_HI: usize = 44;
pub const R_TILEPRO_IMM16_X0_GOT_HA: usize = 45;
pub const R_TILEPRO_IMM16_X1_GOT_HA: usize = 46;
pub const R_TILEPRO_MMSTART_X0: usize = 47;
pub const R_TILEPRO_MMEND_X0: usize = 48;
pub const R_TILEPRO_MMSTART_X1: usize = 49;
pub const R_TILEPRO_MMEND_X1: usize = 50;
pub const R_TILEPRO_SHAMT_X0: usize = 51;
pub const R_TILEPRO_SHAMT_X1: usize = 52;
pub const R_TILEPRO_SHAMT_Y0: usize = 53;
pub const R_TILEPRO_SHAMT_Y1: usize = 54;
pub const R_TILEPRO_DEST_IMM8_X1: usize = 55;
pub const R_TILEPRO_TLS_GD_CALL: usize = 60;
pub const R_TILEPRO_IMM8_X0_TLS_GD_ADD: usize = 61;
pub const R_TILEPRO_IMM8_X1_TLS_GD_ADD: usize = 62;
pub const R_TILEPRO_IMM8_Y0_TLS_GD_ADD: usize = 63;
pub const R_TILEPRO_IMM8_Y1_TLS_GD_ADD: usize = 64;
pub const R_TILEPRO_TLS_IE_LOAD: usize = 65;
pub const R_TILEPRO_IMM16_X0_TLS_GD: usize = 66;
pub const R_TILEPRO_IMM16_X1_TLS_GD: usize = 67;
pub const R_TILEPRO_IMM16_X0_TLS_GD_LO: usize = 68;
pub const R_TILEPRO_IMM16_X1_TLS_GD_LO: usize = 69;
pub const R_TILEPRO_IMM16_X0_TLS_GD_HI: usize = 70;
pub const R_TILEPRO_IMM16_X1_TLS_GD_HI: usize = 71;
pub const R_TILEPRO_IMM16_X0_TLS_GD_HA: usize = 72;
pub const R_TILEPRO_IMM16_X1_TLS_GD_HA: usize = 73;
pub const R_TILEPRO_IMM16_X0_TLS_IE: usize = 74;
pub const R_TILEPRO_IMM16_X1_TLS_IE: usize = 75;
pub const R_TILEPRO_IMM16_X0_TLS_IE_LO: usize = 76;
pub const R_TILEPRO_IMM16_X1_TLS_IE_LO: usize = 77;
pub const R_TILEPRO_IMM16_X0_TLS_IE_HI: usize = 78;
pub const R_TILEPRO_IMM16_X1_TLS_IE_HI: usize = 79;
pub const R_TILEPRO_IMM16_X0_TLS_IE_HA: usize = 80;
pub const R_TILEPRO_IMM16_X1_TLS_IE_HA: usize = 81;
pub const R_TILEPRO_TLS_DTPMOD32: usize = 82;
pub const R_TILEPRO_TLS_DTPOFF32: usize = 83;
pub const R_TILEPRO_TLS_TPOFF32: usize = 84;
pub const R_TILEPRO_IMM16_X0_TLS_LE: usize = 85;
pub const R_TILEPRO_IMM16_X1_TLS_LE: usize = 86;
pub const R_TILEPRO_IMM16_X0_TLS_LE_LO: usize = 87;
pub const R_TILEPRO_IMM16_X1_TLS_LE_LO: usize = 88;
pub const R_TILEPRO_IMM16_X0_TLS_LE_HI: usize = 89;
pub const R_TILEPRO_IMM16_X1_TLS_LE_HI: usize = 90;
pub const R_TILEPRO_IMM16_X0_TLS_LE_HA: usize = 91;
pub const R_TILEPRO_IMM16_X1_TLS_LE_HA: usize = 92;
pub const R_TILEPRO_GNU_VTINHERIT: usize = 128;
pub const R_TILEPRO_GNU_VTENTRY: usize = 129;
pub const R_TILEPRO_NUM: usize = 130;
pub const R_TILEGX_NONE: usize = 0;
pub const R_TILEGX_64: usize = 1;
pub const R_TILEGX_32: usize = 2;
pub const R_TILEGX_16: usize = 3;
pub const R_TILEGX_8: usize = 4;
pub const R_TILEGX_64_PCREL: usize = 5;
pub const R_TILEGX_32_PCREL: usize = 6;
pub const R_TILEGX_16_PCREL: usize = 7;
pub const R_TILEGX_8_PCREL: usize = 8;
pub const R_TILEGX_HW0: usize = 9;
pub const R_TILEGX_HW1: usize = 10;
pub const R_TILEGX_HW2: usize = 11;
pub const R_TILEGX_HW3: usize = 12;
pub const R_TILEGX_HW0_LAST: usize = 13;
pub const R_TILEGX_HW1_LAST: usize = 14;
pub const R_TILEGX_HW2_LAST: usize = 15;
pub const R_TILEGX_COPY: usize = 16;
pub const R_TILEGX_GLOB_DAT: usize = 17;
pub const R_TILEGX_JMP_SLOT: usize = 18;
pub const R_TILEGX_RELATIVE: usize = 19;
pub const R_TILEGX_BROFF_X1: usize = 20;
pub const R_TILEGX_JUMPOFF_X1: usize = 21;
pub const R_TILEGX_JUMPOFF_X1_PLT: usize = 22;
pub const R_TILEGX_IMM8_X0: usize = 23;
pub const R_TILEGX_IMM8_Y0: usize = 24;
pub const R_TILEGX_IMM8_X1: usize = 25;
pub const R_TILEGX_IMM8_Y1: usize = 26;
pub const R_TILEGX_DEST_IMM8_X1: usize = 27;
pub const R_TILEGX_MT_IMM14_X1: usize = 28;
pub const R_TILEGX_MF_IMM14_X1: usize = 29;
pub const R_TILEGX_MMSTART_X0: usize = 30;
pub const R_TILEGX_MMEND_X0: usize = 31;
pub const R_TILEGX_SHAMT_X0: usize = 32;
pub const R_TILEGX_SHAMT_X1: usize = 33;
pub const R_TILEGX_SHAMT_Y0: usize = 34;
pub const R_TILEGX_SHAMT_Y1: usize = 35;
pub const R_TILEGX_IMM16_X0_HW0: usize = 36;
pub const R_TILEGX_IMM16_X1_HW0: usize = 37;
pub const R_TILEGX_IMM16_X0_HW1: usize = 38;
pub const R_TILEGX_IMM16_X1_HW1: usize = 39;
pub const R_TILEGX_IMM16_X0_HW2: usize = 40;
pub const R_TILEGX_IMM16_X1_HW2: usize = 41;
pub const R_TILEGX_IMM16_X0_HW3: usize = 42;
pub const R_TILEGX_IMM16_X1_HW3: usize = 43;
pub const R_TILEGX_IMM16_X0_HW0_LAST: usize = 44;
pub const R_TILEGX_IMM16_X1_HW0_LAST: usize = 45;
pub const R_TILEGX_IMM16_X0_HW1_LAST: usize = 46;
pub const R_TILEGX_IMM16_X1_HW1_LAST: usize = 47;
pub const R_TILEGX_IMM16_X0_HW2_LAST: usize = 48;
pub const R_TILEGX_IMM16_X1_HW2_LAST: usize = 49;
pub const R_TILEGX_IMM16_X0_HW0_PCREL: usize = 50;
pub const R_TILEGX_IMM16_X1_HW0_PCREL: usize = 51;
pub const R_TILEGX_IMM16_X0_HW1_PCREL: usize = 52;
pub const R_TILEGX_IMM16_X1_HW1_PCREL: usize = 53;
pub const R_TILEGX_IMM16_X0_HW2_PCREL: usize = 54;
pub const R_TILEGX_IMM16_X1_HW2_PCREL: usize = 55;
pub const R_TILEGX_IMM16_X0_HW3_PCREL: usize = 56;
pub const R_TILEGX_IMM16_X1_HW3_PCREL: usize = 57;
pub const R_TILEGX_IMM16_X0_HW0_LAST_PCREL: usize = 58;
pub const R_TILEGX_IMM16_X1_HW0_LAST_PCREL: usize = 59;
pub const R_TILEGX_IMM16_X0_HW1_LAST_PCREL: usize = 60;
pub const R_TILEGX_IMM16_X1_HW1_LAST_PCREL: usize = 61;
pub const R_TILEGX_IMM16_X0_HW2_LAST_PCREL: usize = 62;
pub const R_TILEGX_IMM16_X1_HW2_LAST_PCREL: usize = 63;
pub const R_TILEGX_IMM16_X0_HW0_GOT: usize = 64;
pub const R_TILEGX_IMM16_X1_HW0_GOT: usize = 65;
pub const R_TILEGX_IMM16_X0_HW0_PLT_PCREL: usize = 66;
pub const R_TILEGX_IMM16_X1_HW0_PLT_PCREL: usize = 67;
pub const R_TILEGX_IMM16_X0_HW1_PLT_PCREL: usize = 68;
pub const R_TILEGX_IMM16_X1_HW1_PLT_PCREL: usize = 69;
pub const R_TILEGX_IMM16_X0_HW2_PLT_PCREL: usize = 70;
pub const R_TILEGX_IMM16_X1_HW2_PLT_PCREL: usize = 71;
pub const R_TILEGX_IMM16_X0_HW0_LAST_GOT: usize = 72;
pub const R_TILEGX_IMM16_X1_HW0_LAST_GOT: usize = 73;
pub const R_TILEGX_IMM16_X0_HW1_LAST_GOT: usize = 74;
pub const R_TILEGX_IMM16_X1_HW1_LAST_GOT: usize = 75;
pub const R_TILEGX_IMM16_X0_HW3_PLT_PCREL: usize = 76;
pub const R_TILEGX_IMM16_X1_HW3_PLT_PCREL: usize = 77;
pub const R_TILEGX_IMM16_X0_HW0_TLS_GD: usize = 78;
pub const R_TILEGX_IMM16_X1_HW0_TLS_GD: usize = 79;
pub const R_TILEGX_IMM16_X0_HW0_TLS_LE: usize = 80;
pub const R_TILEGX_IMM16_X1_HW0_TLS_LE: usize = 81;
pub const R_TILEGX_IMM16_X0_HW0_LAST_TLS_LE: usize = 82;
pub const R_TILEGX_IMM16_X1_HW0_LAST_TLS_LE: usize = 83;
pub const R_TILEGX_IMM16_X0_HW1_LAST_TLS_LE: usize = 84;
pub const R_TILEGX_IMM16_X1_HW1_LAST_TLS_LE: usize = 85;
pub const R_TILEGX_IMM16_X0_HW0_LAST_TLS_GD: usize = 86;
pub const R_TILEGX_IMM16_X1_HW0_LAST_TLS_GD: usize = 87;
pub const R_TILEGX_IMM16_X0_HW1_LAST_TLS_GD: usize = 88;
pub const R_TILEGX_IMM16_X1_HW1_LAST_TLS_GD: usize = 89;
pub const R_TILEGX_IMM16_X0_HW0_TLS_IE: usize = 92;
pub const R_TILEGX_IMM16_X1_HW0_TLS_IE: usize = 93;
pub const R_TILEGX_IMM16_X0_HW0_LAST_PLT_PCREL: usize = 94;
pub const R_TILEGX_IMM16_X1_HW0_LAST_PLT_PCREL: usize = 95;
pub const R_TILEGX_IMM16_X0_HW1_LAST_PLT_PCREL: usize = 96;
pub const R_TILEGX_IMM16_X1_HW1_LAST_PLT_PCREL: usize = 97;
pub const R_TILEGX_IMM16_X0_HW2_LAST_PLT_PCREL: usize = 98;
pub const R_TILEGX_IMM16_X1_HW2_LAST_PLT_PCREL: usize = 99;
pub const R_TILEGX_IMM16_X0_HW0_LAST_TLS_IE: usize = 100;
pub const R_TILEGX_IMM16_X1_HW0_LAST_TLS_IE: usize = 101;
pub const R_TILEGX_IMM16_X0_HW1_LAST_TLS_IE: usize = 102;
pub const R_TILEGX_IMM16_X1_HW1_LAST_TLS_IE: usize = 103;
pub const R_TILEGX_TLS_DTPMOD64: usize = 106;
pub const R_TILEGX_TLS_DTPOFF64: usize = 107;
pub const R_TILEGX_TLS_TPOFF64: usize = 108;
pub const R_TILEGX_TLS_DTPMOD32: usize = 109;
pub const R_TILEGX_TLS_DTPOFF32: usize = 110;
pub const R_TILEGX_TLS_TPOFF32: usize = 111;
pub const R_TILEGX_TLS_GD_CALL: usize = 112;
pub const R_TILEGX_IMM8_X0_TLS_GD_ADD: usize = 113;
pub const R_TILEGX_IMM8_X1_TLS_GD_ADD: usize = 114;
pub const R_TILEGX_IMM8_Y0_TLS_GD_ADD: usize = 115;
pub const R_TILEGX_IMM8_Y1_TLS_GD_ADD: usize = 116;
pub const R_TILEGX_TLS_IE_LOAD: usize = 117;
pub const R_TILEGX_IMM8_X0_TLS_ADD: usize = 118;
pub const R_TILEGX_IMM8_X1_TLS_ADD: usize = 119;
pub const R_TILEGX_IMM8_Y0_TLS_ADD: usize = 120;
pub const R_TILEGX_IMM8_Y1_TLS_ADD: usize = 121;
pub const R_TILEGX_GNU_VTINHERIT: usize = 128;
pub const R_TILEGX_GNU_VTENTRY: usize = 129;
pub const R_TILEGX_NUM: usize = 130;
pub const R_OR1K_NONE: u8 = 0;
pub const R_OR1K_32: u8 = 1;
pub const R_OR1K_16: u8 = 2;
pub const R_OR1K_8: u8 = 3;
pub const R_OR1K_LO_16_IN_INSN: u8 = 4;
pub const R_OR1K_HI_16_IN_INSN: u8 = 5;
pub const R_OR1K_INSN_REL_26: u8 = 6;
pub const R_OR1K_GNU_VTENTRY: u8 = 7;
pub const R_OR1K_GNU_VTINHERIT: u8 = 8;
pub const R_OR1K_32_PCREL: u8 = 9;
pub const R_OR1K_16_PCREL: u8 = 10;
pub const R_OR1K_8_PCREL: u8 = 11;
pub const R_OR1K_GOTPC_HI16: u8 = 12;
pub const R_OR1K_GOTPC_LO16: u8 = 13;
pub const R_OR1K_GOT16: u8 = 14;
pub const R_OR1K_PLT26: u8 = 15;
pub const R_OR1K_GOTOFF_HI16: u8 = 16;
pub const R_OR1K_GOTOFF_LO16: u8 = 17;
pub const R_OR1K_COPY: u8 = 18;
pub const R_OR1K_GLOB_DAT: u8 = 19;
pub const R_OR1K_JMP_SLOT: u8 = 20;
pub const R_OR1K_RELATIVE: u8 = 21;
pub const R_OR1K_TLS_GD_HI16: u8 = 22;
pub const R_OR1K_TLS_GD_LO16: u8 = 23;
pub const R_OR1K_TLS_LDM_HI16: u8 = 24;
pub const R_OR1K_TLS_LDM_LO16: u8 = 25;
pub const R_OR1K_TLS_LDO_HI16: u8 = 26;
pub const R_OR1K_TLS_LDO_LO16: u8 = 27;
pub const R_OR1K_TLS_IE_HI16: u8 = 28;
pub const R_OR1K_TLS_IE_LO16: u8 = 29;
pub const R_OR1K_TLS_LE_HI16: u8 = 30;
pub const R_OR1K_TLS_LE_LO16: u8 = 31;
pub const R_OR1K_TLS_TPOFF: u8 = 32;
pub const R_OR1K_TLS_DTPOFF: u8 = 33;
pub const R_OR1K_TLS_DTPMOD: u8 = 34;
pub const R_OR1K_NUM: u8 = 35;

pub type Elf32_Half = u16;
pub type Elf64_Half = u16;
pub type Elf32_Word = u32;
pub type Elf32_Sword = i32;
pub type Elf64_Word = u32;
pub type Elf64_Sword = i32;
pub type Elf32_Xword = u64;
pub type Elf32_Sxword = i64;
pub type Elf64_Xword = u64;
pub type Elf64_Sxword = i64;
pub type Elf32_Addr = u32;
pub type Elf64_Addr = u64;
pub type Elf32_Off = u32;
pub type Elf64_Off = u64;
pub type Elf32_Section = u16;
pub type Elf64_Section = u16;
pub type Elf32_Versym = Elf32_Half;
pub type Elf64_Versym = Elf64_Half;

#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Ehdr {
    pub e_ident: [u8; 16usize],
    pub e_type: Elf32_Half,
    pub e_machine: Elf32_Half,
    pub e_version: Elf32_Word,
    pub e_entry: Elf32_Addr,
    pub e_phoff: Elf32_Off,
    pub e_shoff: Elf32_Off,
    pub e_flags: Elf32_Word,
    pub e_ehsize: Elf32_Half,
    pub e_phentsize: Elf32_Half,
    pub e_phnum: Elf32_Half,
    pub e_shentsize: Elf32_Half,
    pub e_shnum: Elf32_Half,
    pub e_shstrndx: Elf32_Half,
}
impl Clone for Elf32_Ehdr {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Ehdr {
    pub e_ident: [u8; 16usize],
    pub e_type: Elf64_Half,
    pub e_machine: Elf64_Half,
    pub e_version: Elf64_Word,
    pub e_entry: Elf64_Addr,
    pub e_phoff: Elf64_Off,
    pub e_shoff: Elf64_Off,
    pub e_flags: Elf64_Word,
    pub e_ehsize: Elf64_Half,
    pub e_phentsize: Elf64_Half,
    pub e_phnum: Elf64_Half,
    pub e_shentsize: Elf64_Half,
    pub e_shnum: Elf64_Half,
    pub e_shstrndx: Elf64_Half,
}
impl Clone for Elf64_Ehdr {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Shdr {
    pub sh_name: Elf32_Word,
    pub sh_type: Elf32_Word,
    pub sh_flags: Elf32_Word,
    pub sh_addr: Elf32_Addr,
    pub sh_offset: Elf32_Off,
    pub sh_size: Elf32_Word,
    pub sh_link: Elf32_Word,
    pub sh_info: Elf32_Word,
    pub sh_addralign: Elf32_Word,
    pub sh_entsize: Elf32_Word,
}
impl Clone for Elf32_Shdr {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Shdr {
    pub sh_name: Elf64_Word,
    pub sh_type: Elf64_Word,
    pub sh_flags: Elf64_Xword,
    pub sh_addr: Elf64_Addr,
    pub sh_offset: Elf64_Off,
    pub sh_size: Elf64_Xword,
    pub sh_link: Elf64_Word,
    pub sh_info: Elf64_Word,
    pub sh_addralign: Elf64_Xword,
    pub sh_entsize: Elf64_Xword,
}
impl Clone for Elf64_Shdr {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Sym {
    pub st_name: Elf32_Word,
    pub st_value: Elf32_Addr,
    pub st_size: Elf32_Word,
    pub st_info: u8,
    pub st_other: u8,
    pub st_shndx: Elf32_Section,
}
impl Clone for Elf32_Sym {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Sym {
    pub st_name: Elf64_Word,
    pub st_info: u8,
    pub st_other: u8,
    pub st_shndx: Elf64_Section,
    pub st_value: Elf64_Addr,
    pub st_size: Elf64_Xword,
}
impl Clone for Elf64_Sym {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Syminfo {
    pub si_boundto: Elf32_Half,
    pub si_flags: Elf32_Half,
}
impl Clone for Elf32_Syminfo {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Syminfo {
    pub si_boundto: Elf64_Half,
    pub si_flags: Elf64_Half,
}
impl Clone for Elf64_Syminfo {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Rel {
    pub r_offset: Elf32_Addr,
    pub r_info: Elf32_Word,
}
impl Clone for Elf32_Rel {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Rel {
    pub r_offset: Elf64_Addr,
    pub r_info: Elf64_Xword,
}
impl Clone for Elf64_Rel {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Rela {
    pub r_offset: Elf32_Addr,
    pub r_info: Elf32_Word,
    pub r_addend: Elf32_Sword,
}
impl Clone for Elf32_Rela {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Rela {
    pub r_offset: Elf64_Addr,
    pub r_info: Elf64_Xword,
    pub r_addend: Elf64_Sxword,
}
impl Clone for Elf64_Rela {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Phdr {
    pub p_type: Elf32_Word,
    pub p_offset: Elf32_Off,
    pub p_vaddr: Elf32_Addr,
    pub p_paddr: Elf32_Addr,
    pub p_filesz: Elf32_Word,
    pub p_memsz: Elf32_Word,
    pub p_flags: Elf32_Word,
    pub p_align: Elf32_Word,
}
impl Clone for Elf32_Phdr {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Phdr {
    pub p_type: Elf64_Word,
    pub p_flags: Elf64_Word,
    pub p_offset: Elf64_Off,
    pub p_vaddr: Elf64_Addr,
    pub p_paddr: Elf64_Addr,
    pub p_filesz: Elf64_Xword,
    pub p_memsz: Elf64_Xword,
    pub p_align: Elf64_Xword,
}
impl Clone for Elf64_Phdr {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Copy)]
pub struct Elf32_Dyn {
    pub d_tag: Elf32_Sword,
    pub d_un: Elf32_Dyn__bindgen_ty_1,
}
#[repr(C)]
#[derive(Copy)]
pub union Elf32_Dyn__bindgen_ty_1 {
    pub d_val: Elf32_Word,
    pub d_ptr: Elf32_Addr,
}
impl Clone for Elf32_Dyn__bindgen_ty_1 {
    fn clone(&self) -> Self { *self }
}
impl Clone for Elf32_Dyn {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Copy)]
pub struct Elf64_Dyn {
    pub d_tag: Elf64_Sxword,
    pub d_un: Elf64_Dyn__bindgen_ty_1,
}
#[repr(C)]
#[derive(Copy)]
pub union Elf64_Dyn__bindgen_ty_1 {
    pub d_val: Elf64_Xword,
    pub d_ptr: Elf64_Addr,
}
impl Clone for Elf64_Dyn__bindgen_ty_1 {
    fn clone(&self) -> Self { *self }
}
impl Clone for Elf64_Dyn {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Verdef {
    pub vd_version: Elf32_Half,
    pub vd_flags: Elf32_Half,
    pub vd_ndx: Elf32_Half,
    pub vd_cnt: Elf32_Half,
    pub vd_hash: Elf32_Word,
    pub vd_aux: Elf32_Word,
    pub vd_next: Elf32_Word,
}
impl Clone for Elf32_Verdef {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Verdef {
    pub vd_version: Elf64_Half,
    pub vd_flags: Elf64_Half,
    pub vd_ndx: Elf64_Half,
    pub vd_cnt: Elf64_Half,
    pub vd_hash: Elf64_Word,
    pub vd_aux: Elf64_Word,
    pub vd_next: Elf64_Word,
}
impl Clone for Elf64_Verdef {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Verdaux {
    pub vda_name: Elf32_Word,
    pub vda_next: Elf32_Word,
}
impl Clone for Elf32_Verdaux {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Verdaux {
    pub vda_name: Elf64_Word,
    pub vda_next: Elf64_Word,
}
impl Clone for Elf64_Verdaux {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Verneed {
    pub vn_version: Elf32_Half,
    pub vn_cnt: Elf32_Half,
    pub vn_file: Elf32_Word,
    pub vn_aux: Elf32_Word,
    pub vn_next: Elf32_Word,
}
impl Clone for Elf32_Verneed {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Verneed {
    pub vn_version: Elf64_Half,
    pub vn_cnt: Elf64_Half,
    pub vn_file: Elf64_Word,
    pub vn_aux: Elf64_Word,
    pub vn_next: Elf64_Word,
}
impl Clone for Elf64_Verneed {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Vernaux {
    pub vna_hash: Elf32_Word,
    pub vna_flags: Elf32_Half,
    pub vna_other: Elf32_Half,
    pub vna_name: Elf32_Word,
    pub vna_next: Elf32_Word,
}
impl Clone for Elf32_Vernaux {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Vernaux {
    pub vna_hash: Elf64_Word,
    pub vna_flags: Elf64_Half,
    pub vna_other: Elf64_Half,
    pub vna_name: Elf64_Word,
    pub vna_next: Elf64_Word,
}
impl Clone for Elf64_Vernaux {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Copy)]
pub struct Elf32_auxv_t {
    pub a_type: u32,
    pub a_un: Elf32_auxv_t__bindgen_ty_1,
}
#[repr(C)]
#[derive(Copy)]
pub union Elf32_auxv_t__bindgen_ty_1 {
    pub a_val: u32,
}
impl Clone for Elf32_auxv_t__bindgen_ty_1 {
    fn clone(&self) -> Self { *self }
}
impl Clone for Elf32_auxv_t {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Copy)]
pub struct Elf64_auxv_t {
    pub a_type: u64,
    pub a_un: Elf64_auxv_t__bindgen_ty_1,
}
#[repr(C)]
#[derive(Copy)]
pub union Elf64_auxv_t__bindgen_ty_1 {
    pub a_val: u64,
}
impl Clone for Elf64_auxv_t__bindgen_ty_1 {
    fn clone(&self) -> Self { *self }
}
impl Clone for Elf64_auxv_t {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Nhdr {
    pub n_namesz: Elf32_Word,
    pub n_descsz: Elf32_Word,
    pub n_type: Elf32_Word,
}
impl Clone for Elf32_Nhdr {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Nhdr {
    pub n_namesz: Elf64_Word,
    pub n_descsz: Elf64_Word,
    pub n_type: Elf64_Word,
}
impl Clone for Elf64_Nhdr {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Move {
    pub m_value: Elf32_Xword,
    pub m_info: Elf32_Word,
    pub m_poffset: Elf32_Word,
    pub m_repeat: Elf32_Half,
    pub m_stride: Elf32_Half,
}
impl Clone for Elf32_Move {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Move {
    pub m_value: Elf64_Xword,
    pub m_info: Elf64_Xword,
    pub m_poffset: Elf64_Xword,
    pub m_repeat: Elf64_Half,
    pub m_stride: Elf64_Half,
}
impl Clone for Elf64_Move {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Copy)]
pub union Elf32_gptab {
    pub gt_header: Elf32_gptab__bindgen_ty_1,
    pub gt_entry: Elf32_gptab__bindgen_ty_2,
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_gptab__bindgen_ty_1 {
    pub gt_current_g_value: Elf32_Word,
    pub gt_unused: Elf32_Word,
}
impl Clone for Elf32_gptab__bindgen_ty_1 {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_gptab__bindgen_ty_2 {
    pub gt_g_value: Elf32_Word,
    pub gt_bytes: Elf32_Word,
}
impl Clone for Elf32_gptab__bindgen_ty_2 {
    fn clone(&self) -> Self { *self }
}
impl Clone for Elf32_gptab {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_RegInfo {
    pub ri_gprmask: Elf32_Word,
    pub ri_cprmask: [Elf32_Word; 4usize],
    pub ri_gp_value: Elf32_Sword,
}
impl Clone for Elf32_RegInfo {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf_Options {
    pub kind: u8,
    pub size: u8,
    pub section: Elf32_Section,
    pub info: Elf32_Word,
}
impl Clone for Elf_Options {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf_Options_Hw {
    pub hwp_flags1: Elf32_Word,
    pub hwp_flags2: Elf32_Word,
}
impl Clone for Elf_Options_Hw {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf32_Lib {
    pub l_name: Elf32_Word,
    pub l_time_stamp: Elf32_Word,
    pub l_checksum: Elf32_Word,
    pub l_version: Elf32_Word,
    pub l_flags: Elf32_Word,
}
impl Clone for Elf32_Lib {
    fn clone(&self) -> Self { *self }
}
#[repr(C)]
#[derive(Debug, Copy)]
pub struct Elf64_Lib {
    pub l_name: Elf64_Word,
    pub l_time_stamp: Elf64_Word,
    pub l_checksum: Elf64_Word,
    pub l_version: Elf64_Word,
    pub l_flags: Elf64_Word,
}
impl Clone for Elf64_Lib {
    fn clone(&self) -> Self { *self }
}
pub type Elf32_Conflict = Elf32_Addr;

pub fn ELF32_R_SYM(info: Elf32_Word) -> Elf32_Word { info >> 8 }
pub fn ELF32_R_TYPE(info: Elf32_Word) -> u8 { info as u8 }
pub fn ELF32_R_INFO(sym: Elf32_Word, ty: u8) -> Elf32_Word { sym << 8 | ty as Elf32_Word }

pub fn ELF32_ST_BIND(info: u8) -> u8 { info >> 4 }
pub fn ELF32_ST_TYPE(info: u8) -> u8 { info & 0xf }
pub fn ELF32_ST_INFO(bind: u8, ty: u8) -> u8 { (bind << 4) | (ty & 0xf) }
