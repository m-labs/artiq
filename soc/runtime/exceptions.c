#include <setjmp.h>

#include "exceptions.h"

static struct exception_env *env_top;
static int stored_id;

int exception_catch(struct exception_env *ee, int *id)
{
	ee->prev = env_top;
	env_top = ee;
	if(setjmp(env_top->jb)) {
		*id = stored_id;
		return 1;
	} else
		return 0;
}

void exception_pop(void)
{
	env_top = env_top->prev;
}

void exception_raise(int id)
{
	struct exception_env *ee;

	ee = env_top;
	env_top = env_top->prev;
	stored_id = id; /* __builtin_longjmp needs its second argument set to 1 */
	longjmp(ee->jb, 1);
}
