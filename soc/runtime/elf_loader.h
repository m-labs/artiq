#ifndef __ELF_LOADER_H
#define __ELF_LOADER_H

int load_elf(void *elf_data, int elf_length, void *dest, int dest_length);

#endif /* __ELF_LOADER_H */
