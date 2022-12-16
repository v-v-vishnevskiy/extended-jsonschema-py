import ast

from collections import defaultdict
from typing import List, Union

from extendedjsonschema.errors import OptimizerError


class Optimizer:
    def __init__(self):
        self._type_callings = defaultdict(int)
        self._additional_code = {}

    def _count_type_calling(self, ast_obj: Union[ast.AST, List[ast.AST]]):
        if type(ast_obj) == ast.If and \
                type(ast_obj.test) == ast.Compare and \
                type(ast_obj.test.left) == ast.Call and \
                type(ast_obj.test.left.func) == ast.Name and \
                ast_obj.test.left.func.id == "type":
            self._type_callings[ast.unparse(ast_obj.test.left.args[0])] += 1
            for _ast_obj in ast_obj.body:
                self._count_type_calling(_ast_obj)
            for _ast_obj in ast_obj.orelse:
                self._count_type_calling(_ast_obj)
        elif type(ast_obj) == list:
            for i, _ast_obj in enumerate(ast_obj):
                self._count_type_calling(_ast_obj)
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                self._count_type_calling(getattr(ast_obj, field))

    def __replace_type_calling(self, ast_obj: ast.AST) -> Union[ast.AST, None]:
        additional_code = None
        argument = ast.unparse(ast_obj.test.left.args[0])
        if self._type_callings[argument] == 1:
            isinstance_call = ast.Call(
                func=ast.Name(id="isinstance", ctx=ast.Load()),
                args=[
                    ast_obj.test.left.args[0],
                    ast_obj.test.comparators[0]
                ],
                keywords=[]
            )
            if type(ast_obj.test.ops[0]) in (ast.NotEq, ast.NotIn):
                ast_obj.test = ast.UnaryOp(op=ast.Not(), operand=isinstance_call)
            else:
                ast_obj.test = isinstance_call
        elif self._type_callings[argument] > 1:
            argument = argument.replace('"', "").replace("[", "").replace("]", "")
            if not self._additional_code.get(argument):
                additional_code = ast.Assign(
                    targets=[ast.Name(id=f"type_{argument}", ctx=ast.Store())],
                    value=ast_obj.test.left,
                    lineno=0
                )
                self._additional_code[argument] = True
            ast_obj.test.left = ast.Name(id=f"type_{argument}", ctx=ast.Load())
        return additional_code

    def _replace_type_calling(self, ast_obj: Union[ast.AST, List[ast.AST]]):
        if type(ast_obj) == list:
            i = 0
            while i < len(ast_obj):
                if type(ast_obj[i]) == ast.If and \
                        type(ast_obj[i].test) == ast.Compare and \
                        type(ast_obj[i].test.left) == ast.Call and \
                        type(ast_obj[i].test.left.func) == ast.Name and \
                        ast_obj[i].test.left.func.id == "type":
                    additional_code = self.__replace_type_calling(ast_obj[i])
                    if additional_code:
                        ast_obj.insert(i, additional_code)
                        i += 1
                    for _ast_obj in ast_obj[i].body:
                        self._replace_type_calling(_ast_obj)
                    for _ast_obj in ast_obj[i].orelse:
                        self._replace_type_calling(_ast_obj)
                self._replace_type_calling(ast_obj[i])
                i += 1
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                self._replace_type_calling(getattr(ast_obj, field))

    def _type_calling(self, ast_function: ast.FunctionDef):
        self._count_type_calling(ast_function.body)
        self._replace_type_calling(ast_function.body)

    def _count_error_appending(self, ast_obj: Union[ast.AST, List[ast.AST]], parent_is_loop: bool) -> int:
        result = 0
        if type(ast_obj) == ast.Call and ast.unparse(ast_obj.func) == "errors.append":
            return 2 if parent_is_loop else 1
        elif type(ast_obj) == list:
            for i, _ast_obj in enumerate(ast_obj):
                result += self._count_error_appending(_ast_obj, parent_is_loop)
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                is_loop = parent_is_loop or field == "body" and isinstance(ast_obj, (ast.AsyncFor, ast.For, ast.While))
                result += self._count_error_appending(getattr(ast_obj, field), is_loop)
        return result

    def _replace_error_appending(self, ast_obj: Union[ast.AST, List[ast.AST]]) -> Union[ast.AST, List[ast.AST]]:
        if type(ast_obj) == ast.Call and ast.unparse(ast_obj.func) == "errors.append":
            return ast.Return(value=ast.List(elts=[ast_obj.args[0]], ctx=ast.Load()))
        elif type(ast_obj) == list:
            for i, _ast_obj in enumerate(ast_obj):
                ast_obj[i] = self._replace_error_appending(_ast_obj)
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                setattr(ast_obj, field, self._replace_error_appending(getattr(ast_obj, field)))
        return ast_obj

    def _error_handling(self, ast_function: ast.FunctionDef):
        if self._count_error_appending(ast_function.body) == 1:
            ast_function.body.pop(0)
            ast_function.body.pop(-1)
            ast_function.body = self._replace_error_appending(ast_function.body)

    def _to_ast(self, code) -> ast.FunctionDef:
        ast_module: ast.Module = ast.parse(code)

        if len(ast_module.body) == 0:
            raise OptimizerError("Got empty module")

        if type(ast_module.body[0]) != ast.FunctionDef:
            raise OptimizerError(f"Got '{ast_module.body[0].__class__.__name__}' instead of 'FunctionDef'")

        return ast_module.body[0]

    def run(self, code: str) -> str:
        ast_function = self._to_ast(code)
        self._type_calling(ast_function)
        self._error_handling(ast_function)
        return ast.unparse(ast_function)
