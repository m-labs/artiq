import sys, fileinput, os
from pythonparser import source, diagnostic, algorithm, parse_buffer
from .. import prelude, types
from ..transforms import ASTTypedRewriter, Inferencer, IntMonomorphizer, CastMonomorphizer
from ..transforms import IODelayEstimator
from ..validators import ConstnessValidator

class Printer(algorithm.Visitor):
    """
    :class:`Printer` prints ``:`` and the node type after every typed node,
    and ``->`` and the node type before the colon in a function definition.

    In almost all cases (except function definition) this does not result
    in valid Python syntax.

    :ivar rewriter: (:class:`pythonparser.source.Rewriter`) rewriter instance
    """

    def __init__(self, buf):
        self.rewriter = source.Rewriter(buf)
        self.type_printer = types.TypePrinter()

    def rewrite(self):
        return self.rewriter.rewrite()

    def visit_FunctionDefT(self, node):
        super().generic_visit(node)

        self.rewriter.insert_before(node.colon_loc,
                                    "->{}".format(self.type_printer.name(node.return_type)))

    def visit_ExceptHandlerT(self, node):
        super().generic_visit(node)

        if node.name_loc:
            self.rewriter.insert_after(node.name_loc,
                                       ":{}".format(self.type_printer.name(node.name_type)))

    def visit_ForT(self, node):
        super().generic_visit(node)

        if node.trip_count is not None and node.trip_interval is not None:
            self.rewriter.insert_after(node.keyword_loc,
                                       "[{} x {} mu]".format(node.trip_count.fold(),
                                                             node.trip_interval.fold()))

    def generic_visit(self, node):
        super().generic_visit(node)

        if hasattr(node, "type"):
            self.rewriter.insert_after(node.loc,
                                       ":{}".format(self.type_printer.name(node.type)))

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "+mono":
        del sys.argv[1]
        monomorphize = True
    else:
        monomorphize = False

    if len(sys.argv) > 1 and sys.argv[1] == "+iodelay":
        del sys.argv[1]
        iodelay = True
    else:
        iodelay = False

    if len(sys.argv) > 1 and sys.argv[1] == "+diag":
        del sys.argv[1]
        def process_diagnostic(diag):
            print("\n".join(diag.render(only_line=True)))
            if diag.level == "fatal":
                exit()
    else:
        def process_diagnostic(diag):
            print("\n".join(diag.render()))
            if diag.level in ("fatal", "error"):
                exit(1)

    engine = diagnostic.Engine()
    engine.process = process_diagnostic

    buf = source.Buffer("".join(fileinput.input()).expandtabs(),
                        os.path.basename(fileinput.filename()))
    parsed, comments = parse_buffer(buf, engine=engine)
    typed = ASTTypedRewriter(engine=engine, prelude=prelude.globals()).visit(parsed)
    Inferencer(engine=engine).visit(typed)
    ConstnessValidator(engine=engine).visit(typed)
    if monomorphize:
        CastMonomorphizer(engine=engine).visit(typed)
        IntMonomorphizer(engine=engine).visit(typed)
        Inferencer(engine=engine).visit(typed)
    if iodelay:
        IODelayEstimator(engine=engine, ref_period=1e6).visit_fixpoint(typed)

    printer = Printer(buf)
    printer.visit(typed)
    for comment in comments:
        if comment.text.find("CHECK") >= 0:
            printer.rewriter.remove(comment.loc)
    print(printer.rewrite().source)

if __name__ == "__main__":
    main()
