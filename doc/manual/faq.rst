FAQ
###

How do I ...
============

override the sysclk frequency of just one dds?
----------------------------------------------

Override the parameter using an argument in the ddb.

organize parameters in folders?
-------------------------------

Use gui auto-completion and filtering.
Names need to be unique.

enforce functional dependencies between parameters?
---------------------------------------------------

Use wrapper experiments, overriding parameters of arguments.

get rid of `DbKeys`?
--------------------

`DbKeys` enforces valid parameter/argument names, references
keys in pdb and hints at metadata on how values can be retrieved.

write a generator feeding a kernel feeding an analyze function?
---------------------------------------------------------------

  Like this::

    def run(self):
        self.parse(self.pipe(iter(range(10))))

    def pipe(self, gen):
        for i in gen:
            r = self.do(i)
            yield r

    def parse(self, gen):
        for i in gen:
            pass

    @kernel
    def do(self, i):
        return i

create and use variable lengths arrays?
------------------------------------------------

Don't. Preallocate everything. Or chunk it and e.g. read 100 events per
function call, push them upstream and retry until the gate time closes.

execute multiple slow controller RPCs in parallel without loosing time? 
-----------------------------------------------------------------------

Use `threading.Thread`: portable, fast, simple for one-shot calls

write part of my experiment as a coroutine/Task/generator?
----------------------------------------------------------

You want to write experiment preparation (`__init__()` or `build()`)
or analysis (`analyze()`)

No. That would make reusing your own code in sub-experiments difficult and
fragile.
