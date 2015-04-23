#ifndef __ELF_LOADER_H
#define __ELF_LOADER_H

struct symbol {
    char *name;
    void *target;
};

typedef void * (*symbol_resolver)(const char *);
typedef int (*symbol_callback)(const char *, void *);

void *find_symbol(const struct symbol *symbols, const char *name);
/* elf_data must be aligned on a 32-bit boundary */
int load_elf(symbol_resolver resolver, symbol_callback callback, void *elf_data, int elf_length, void *dest, int dest_length);

#endif /* __ELF_LOADER_H */
