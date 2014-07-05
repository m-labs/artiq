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

struct elf32_name {
	char name[12];
} __attribute__((packed));

struct elf32_rela {
	unsigned int offset;  /* Location to be relocated. */
	unsigned int info;    /* Relocation type and symbol index. */
	int addend;           /* Addend. */
} __attribute__((packed));

#define ELF32_R_SYM(info)  ((info) >> 8)
#define ELF32_R_TYPE(info) ((unsigned char)(info))

#define R_OR1K_INSN_REL_26 6

struct elf32_sym {
	unsigned int name;     /* String table index of name. */
	unsigned int value;    /* Symbol value. */
	unsigned int size;     /* Size of associated object. */
	unsigned char info;    /* Type and binding information. */
	unsigned char other;   /* Reserved (not used). */
	unsigned short shndx;  /* Section index of symbol. */
} __attribute__((packed));


#define SANITIZE_OFFSET_SIZE(offset, size) \
	if(offset > 0x10000000) { \
		printf("Incorrect offset in ELF data"); \
		return 0; \
	} \
	if((offset + size) > elf_length) { \
		printf("Attempted to access past the end of ELF data"); \
		return 0; \
	}

#define GET_POINTER_SAFE(target, target_type, offset) \
	SANITIZE_OFFSET_SIZE(offset, sizeof(target_type)); \
	target = (target_type *)((char *)elf_data + offset)

static void *find_symbol(const struct symbol *symbols, const char *name)
{
	int i;

	i = 0;
	while((symbols[i].name != NULL) && (strcmp(symbols[i].name, name) != 0))
		i++;
	return symbols[i].target;
}

static int fixup(void *dest, int dest_length, struct elf32_rela *rela, void *target)
{
	int type, offset;
	unsigned int *_dest = dest;
	unsigned int *_target = target;

	type = ELF32_R_TYPE(rela->info);
	offset = rela->offset/4;
	if(type == R_OR1K_INSN_REL_26) {
		int val;

		val = _target - (_dest + offset);
		_dest[offset] = (_dest[offset] & 0xfc000000) | (val & 0x03ffffff);
	} else
		printf("Unsupported relocation type: %d\n", type);
	return 1;
}

int load_elf(const struct symbol *symbols, void *elf_data, int elf_length, void *dest, int dest_length)
{
	struct elf32_ehdr *ehdr;
	struct elf32_shdr *strtable;
	unsigned int shdrptr;
	int i;

	unsigned int textoff, textsize;
	unsigned int textrelaoff, textrelasize;
	unsigned int symtaboff, symtabsize;
	unsigned int strtaboff, strtabsize;


	/* validate ELF */
	GET_POINTER_SAFE(ehdr, struct elf32_ehdr, 0);
	if(memcmp(ehdr->ident, elf_magic_header, sizeof(elf_magic_header)) != 0) {
		printf("Incorrect ELF header\n");
		return 0;
	}
	if(ehdr->type != ET_REL) {
		printf("ELF is not relocatable\n");
		return 0;
	}
	if(ehdr->machine != EM_OR1K) {
		printf("ELF is for a different machine\n");
		return 0;
	}

	/* extract section info */
	GET_POINTER_SAFE(strtable, struct elf32_shdr, ehdr->shoff + ehdr->shentsize*ehdr->shstrndx);
	textoff = textsize = 0;
	textrelaoff = textrelasize = 0;
	symtaboff = symtabsize = 0;
	strtaboff = strtabsize = 0;
	shdrptr = ehdr->shoff;
	for(i=0;i<ehdr->shnum;i++) {
		struct elf32_shdr *shdr;
		struct elf32_name *name;

		GET_POINTER_SAFE(shdr, struct elf32_shdr, shdrptr);
		GET_POINTER_SAFE(name, struct elf32_name, strtable->offset + shdr->name);
		
		if(strncmp(name->name, ".text", 5) == 0) {
			textoff = shdr->offset;
			textsize = shdr->size;
		} else if(strncmp(name->name, ".rela.text", 10) == 0) {
			textrelaoff = shdr->offset;
			textrelasize = shdr->size;
		} else if(strncmp(name->name, ".symtab", 7) == 0) {
			symtaboff = shdr->offset;
			symtabsize = shdr->size;
		} else if(strncmp(name->name, ".strtab", 7) == 0) {
			strtaboff = shdr->offset;
			strtabsize = shdr->size;
		}

		shdrptr += ehdr->shentsize;
	}
	SANITIZE_OFFSET_SIZE(textoff, textsize);
	SANITIZE_OFFSET_SIZE(textrelaoff, textrelasize);
	SANITIZE_OFFSET_SIZE(symtaboff, symtabsize);
	SANITIZE_OFFSET_SIZE(strtaboff, strtabsize);

	/* load .text section */
	if(textsize > dest_length) {
		printf(".text section is too large\n");
		return 0;
	}
	memcpy(dest, (char *)elf_data + textoff, textsize);

	/* process .text relocations */
	for(i=0;i<textrelasize;i+=sizeof(struct elf32_rela)) {
		struct elf32_rela *rela;
		struct elf32_sym *sym;
		char *name;

		GET_POINTER_SAFE(rela, struct elf32_rela, textrelaoff + i);
		GET_POINTER_SAFE(sym, struct elf32_sym, symtaboff + sizeof(struct elf32_sym)*ELF32_R_SYM(rela->info));
		if(sym->name != 0) {
			void *target;

			name = (char *)elf_data + strtaboff + sym->name;
			target = find_symbol(symbols, name);
			if(target == NULL) {
				printf("Undefined symbol: %s\n", name);
				return 0;
			}
			if(!fixup(dest, dest_length, rela, target))
				return 0;
		} else {
			printf("Unsupported relocation\n");
			return 0;
		}
	}

	return 1;
}
