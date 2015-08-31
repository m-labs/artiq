    def visit_With(self, node):
        self.generic_visit(node)
        if (isinstance(node.items[0].context_expr, ast.Call)
                and node.items[0].context_expr.func.id == "watchdog"):

            idname = "__watchdog_id_" + str(self.watchdog_id_counter)
            self.watchdog_id_counter += 1

            time = ast.BinOp(left=node.items[0].context_expr.args[0],
                             op=ast.Mult(),
                             right=ast.Num(1000))
            time_int = ast.Call(
                func=ast.Name("round", ast.Load()),
                args=[time],
                keywords=[], starargs=None, kwargs=None)
            syscall_set = ast.Call(
                func=ast.Name("syscall", ast.Load()),
                args=[ast.Str("watchdog_set"), time_int],
                keywords=[], starargs=None, kwargs=None)
            stmt_set = ast.copy_location(
                ast.Assign(targets=[ast.Name(idname, ast.Store())],
                           value=syscall_set),
                node)

            syscall_clear = ast.Call(
                func=ast.Name("syscall", ast.Load()),
                args=[ast.Str("watchdog_clear"),
                              ast.Name(idname, ast.Load())],
                keywords=[], starargs=None, kwargs=None)
            stmt_clear = ast.copy_location(ast.Expr(syscall_clear), node)

            node.items[0] = ast.withitem(
                context_expr=ast.Name(id="sequential",
                ctx=ast.Load()),
                optional_vars=None)
            node.body = [
                stmt_set,
                ast.Try(body=node.body,
                        handlers=[],
                        orelse=[],
                        finalbody=[stmt_clear])
            ]
        return node
