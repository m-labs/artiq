#ifndef __ELF_LOADER_H
#define __ELF_LOADER_H

struct symbol {
    char *name;
    void *target;
};

void *find_symbol(const struct symbol *symbols, const char *name);

typedef void * (*symbol_resolver)(const char *name);
int load_elf(symbol_resolver resolver, void *elf_data, int elf_length, void *dest, int dest_length);

#endif /* __ELF_LOADER_H */
