import ast
import types

from artiq.transforms.tools import *


# -1 statement duration could not be pre-determined
#  0 statement has no effect on timeline
# >0 statement is a static delay that advances the timeline
#     by the given amount
def _get_duration(stmt):
    if isinstance(stmt, (ast.Expr, ast.Assign)):
        return _get_duration(stmt.value)
    elif isinstance(stmt, ast.If):
        if (all(_get_duration(s) == 0 for s in stmt.body)
                and all(_get_duration(s) == 0 for s in stmt.orelse)):
            return 0
        else:
            return -1
    elif isinstance(stmt, ast.Try):
        if (all(_get_duration(s) == 0 for s in stmt.body)
                and all(_get_duration(s) == 0 for s in stmt.orelse)
                and all(_get_duration(s) == 0 for s in stmt.finalbody)
                and all(_get_duration(s) == 0 for s in handler.body
                        for handler in stmt.handlers)):
            return 0
        else:
            return -1
    elif isinstance(stmt, ast.Call):
        name = stmt.func.id
        assert(name != "delay")
        if name == "delay_mu":
            try:
                da = eval_constant(stmt.args[0])
            except NotConstant:
                da = -1
            return da
        elif name == "at_mu":
            return -1
        else:
            return 0
    else:
        return 0


def _interleave_timelines(timelines):
    r = []

    current_stmts = []
    for stmts in timelines:
        it = iter(stmts)
        try:
            stmt = next(it)
        except StopIteration:
            pass
        else:
            current_stmts.append(types.SimpleNamespace(
                delay=_get_duration(stmt), stmt=stmt, it=it))

    while current_stmts:
        dt = min(stmt.delay for stmt in current_stmts)
        if dt < 0:
            # contains statement(s) with indeterminate duration
            return None
        if dt > 0:
            # advance timeline by dt
            for stmt in current_stmts:
                stmt.delay -= dt
                if stmt.delay == 0:
                    ref_stmt = stmt.stmt
            delay_stmt = ast.copy_location(
                ast.Expr(ast.Call(
                    func=ast.Name("delay_mu", ast.Load()),
                    args=[value_to_ast(dt)],
                    keywords=[], starargs=[], kwargs=[])),
                ref_stmt)
            r.append(delay_stmt)
        else:
            for stmt in current_stmts:
                if stmt.delay == 0:
                    r.append(stmt.stmt)
        # discard executed statements
        exhausted_list = []
        for stmt_i, stmt in enumerate(current_stmts):
            if stmt.delay == 0:
                try:
                    stmt.stmt = next(stmt.it)
                except StopIteration:
                    exhausted_list.append(stmt_i)
                else:
                    stmt.delay = _get_duration(stmt.stmt)
        for offset, i in enumerate(exhausted_list):
            current_stmts.pop(i-offset)

    return r


def _interleave_stmts(stmts):
    replacements = []
    for stmt_i, stmt in enumerate(stmts):
        if isinstance(stmt, (ast.For, ast.While, ast.If)):
            _interleave_stmts(stmt.body)
            _interleave_stmts(stmt.orelse)
        elif isinstance(stmt, ast.Try):
            _interleave_stmts(stmt.body)
            _interleave_stmts(stmt.orelse)
            _interleave_stmts(stmt.finalbody)
            for handler in stmt.handlers:
                _interleave_stmts(handler.body)
        elif isinstance(stmt, ast.With):
            btype = stmt.items[0].context_expr.id
            if btype == "sequential":
                _interleave_stmts(stmt.body)
                replacements.append((stmt_i, stmt.body))
            elif btype == "parallel":
                timelines = [[s] for s in stmt.body]
                for timeline in timelines:
                    _interleave_stmts(timeline)
                merged = _interleave_timelines(timelines)
                if merged is not None:
                    replacements.append((stmt_i, merged))
            else:
                raise ValueError("Unknown block type: " + btype)
    offset = 0
    for location, new_stmts in replacements:
        stmts[offset+location:offset+location+1] = new_stmts
        offset += len(new_stmts) - 1


def interleave(func_def):
    _interleave_stmts(func_def.body)
