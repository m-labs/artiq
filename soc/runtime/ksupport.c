void exception_handler(unsigned long vect, unsigned long *sp);
void exception_handler(unsigned long vect, unsigned long *sp)
{
    /* TODO: report hardware exception to comm CPU */
    for(;;);
}

extern void kmain(void);

int main(void);
int main(void)
{
    kmain();
    /* TODO: report end of kernel to comm CPU */
    return 0;
}
