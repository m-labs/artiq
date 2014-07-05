#ifndef __ELF_LOADER_H
#define __ELF_LOADER_H

struct symbol {
	char *name;
	void *target;
};

int load_elf(const struct symbol *symbols, void *elf_data, int elf_length, void *dest, int dest_length);

#endif /* __ELF_LOADER_H */
