#include <stdio.h>
#include <string.h>

#include "elf_loader.h"

#define EI_NIDENT 16

struct elf32_ehdr {
	unsigned char ident[EI_NIDENT];    /* ident bytes */
	unsigned short type;               /* file type */
	unsigned short machine;            /* target machine */
	unsigned int version;              /* file version */
	unsigned int entry;                /* start address */
	unsigned int phoff;                /* phdr file offset */
	unsigned int shoff;                /* shdr file offset */
	unsigned int flags;                /* file flags */
	unsigned short ehsize;             /* sizeof ehdr */
	unsigned short phentsize;          /* sizeof phdr */
	unsigned short phnum;              /* number phdrs */
	unsigned short shentsize;          /* sizeof shdr */
	unsigned short shnum;              /* number shdrs */
	unsigned short shstrndx;           /* shdr string index */
} __attribute__((packed));

static const unsigned char elf_magic_header[] = {
	0x7f, 0x45, 0x4c, 0x46,  /* 0x7f, 'E', 'L', 'F' */
	0x01,                    /* Only 32-bit objects. */
	0x02,                    /* Only big-endian. */
	0x01,                    /* Only ELF version 1. */
};

#define ET_NONE         0       /* Unknown type. */
#define ET_REL          1       /* Relocatable. */
#define ET_EXEC         2       /* Executable. */
#define ET_DYN          3       /* Shared object. */
#define ET_CORE         4       /* Core file. */

#define EM_OR1K 0x005c

struct elf32_shdr {
  unsigned int name;        /* section name */
  unsigned int type;        /* SHT_... */
  unsigned int flags;       /* SHF_... */
  unsigned int addr;        /* virtual address */
  unsigned int offset;      /* file offset */
  unsigned int size;        /* section size */
  unsigned int link;        /* misc info */
  unsigned int info;        /* misc info */
  unsigned int addralign;   /* memory alignment */
  unsigned int entsize;     /* entry size if table */
} __attribute__((packed));

#define SHT_NULL        0               /* inactive */
#define SHT_PROGBITS    1               /* program defined information */
#define SHT_SYMTAB      2               /* symbol table section */
#define SHT_STRTAB      3               /* string table section */
#define SHT_RELA        4               /* relocation section with addends*/
#define SHT_HASH        5               /* symbol hash table section */
#define SHT_DYNAMIC     6               /* dynamic section */
#define SHT_NOTE        7               /* note section */
#define SHT_NOBITS      8               /* no space section */
#define SHT_REL         9               /* relation section without addends */
#define SHT_SHLIB       10              /* reserved - purpose unknown */
#define SHT_DYNSYM      11              /* dynamic symbol table section */
#define SHT_LOPROC      0x70000000      /* reserved range for processor */
#define SHT_HIPROC      0x7fffffff      /* specific section header types */
#define SHT_LOUSER      0x80000000      /* reserved range for application */
#define SHT_HIUSER      0xffffffff      /* specific indexes */

struct elf32_name {
	char name[12];
} __attribute__((packed));

#define SANITIZE_OFFSET_SIZE(offset, size) \
	if(offset > 0x10000000) \
		return 0; \
	if((offset + size) > elf_length) \
		return 0

#define GET_POINTER_SAFE(target, target_type, offset) \
	SANITIZE_OFFSET_SIZE(offset, sizeof(target_type)); \
	target = (target_type *)((char *)elf_data + offset)

int load_elf(void *elf_data, int elf_length, void *dest, int dest_length)
{
	struct elf32_ehdr *ehdr;
	struct elf32_shdr *strtable;
	struct elf32_shdr *shdr;
	struct elf32_name *name;
	unsigned int shdrptr;
	int i;

	unsigned int textoff;
	unsigned int textsize;


	GET_POINTER_SAFE(ehdr, struct elf32_ehdr, 0);
	if(memcmp(ehdr->ident, elf_magic_header, sizeof(elf_magic_header)) != 0)
		return 0;
	if(ehdr->type != ET_REL) return 0;
	if(ehdr->machine != EM_OR1K) return 0;

	GET_POINTER_SAFE(strtable, struct elf32_shdr, ehdr->shoff + ehdr->shentsize*ehdr->shstrndx);
	
	textoff = textsize = 0;
	shdrptr = ehdr->shoff;
	for(i=0;i<ehdr->shnum;i++) {
		GET_POINTER_SAFE(shdr, struct elf32_shdr, shdrptr);
		GET_POINTER_SAFE(name, struct elf32_name, strtable->offset + shdr->name);
		
		if(strncmp(name->name, ".text", 5) == 0) {
			textoff = shdr->offset;
			textsize = shdr->size;
		}

		shdrptr += ehdr->shentsize;
	}

	SANITIZE_OFFSET_SIZE(textoff, textsize);
	if(textsize > dest_length)
		return 0;
	memcpy(dest, (char *)elf_data + textoff, textsize);

	return 1;
}
