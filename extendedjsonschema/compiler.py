import ast
import inspect
import re
from collections.abc import Iterable
from collections import defaultdict
from typing import Any, Callable, List, Tuple, Union

from extendedjsonschema.errors import CompilerError
from extendedjsonschema.keyword import Keyword
from extendedjsonschema.schema import Program


BEFORE_FUNCTION_CODE = """import re
from collections import defaultdict
from extendedjsonschema.errors import ValidationError
from extendedjsonschema.tools import is_equal


class ReturnStmt(Exception):
    pass


NoneType = type(None)"""


class Compiler:
    def __init__(self, program: Program):
        self.program = program
        self._init()

    def _init(self):
        self._attributes = defaultdict(dict)
        self._programs = []

    def to_ast(self, fn: Callable) -> ast.FunctionDef:
        fn_source = inspect.getsource(fn)
        fn_source = self.remove_extra_indents(fn_source)
        ast_module: ast.Module = ast.parse(fn_source)

        if len(ast_module.body) == 0:
            raise CompilerError("Got empty module")

        if type(ast_module.body[0]) != ast.FunctionDef:
            raise CompilerError(f"Got '{ast_module.body[0].__class__.__name__}' instead of 'FunctionDef'")

        return ast_module.body[0]

    def remove_extra_indents(self, source: str) -> str:
        i = 0
        indent_char = None
        while i < len(source):
            if source[i] in {" ", "\t"}:
                i += 1
            else:
                break

            if indent_char is None:
                indent_char = source[i]

        result = []
        for line in source.split("\n"):
            result.append(line[i:])
        return "\n".join(result)

    def check_parameters(self, args: List[ast.arg]):
        expect = ["self", "path", "value", "errors"]
        parameters = [arg.arg for arg in args]

        if len(parameters) != 4:
            raise CompilerError(f"Declared {len(parameters)} parameters instead of 4")
        elif parameters != expect:
            raise CompilerError(f"Declared {parameters} parameters instead of {expect}")

    def to_python_code(self, value: Any) -> str:
        none_type = type(None)
        value_type = type(value)
        if value_type in {list, tuple, set}:
            brackets = {list: ("[", "]"), tuple: ("(", ")"), set: ("{", "}")}
            result = []
            for item in value:
                result.append(self.to_python_code(item))
            return brackets[value_type][0] + ", ".join(result) + brackets[value_type][1]
        elif value_type == dict:
            result = []
            for k, v in value.items():
                result.append(f"{self.to_python_code(k)}: {self.to_python_code(v)}")
            result = ", ".join(result)
            return f"{{{result}}}"
        elif value_type in {bool, int, float, none_type}:
            return str(value)
        elif value_type == str:
            return f'"{value}"'
        elif isinstance(value, type):
            return value.__name__
        elif isinstance(value, Iterable):
            return self.to_python_code(list(value))
        elif isinstance(value, Program):
            return f"program_{id(value)}"
        elif isinstance(value, Keyword):
            return self.to_python_code({"name": value.name, "value": value.value})
        elif isinstance(value, re.Pattern):
            return str(value)
        else:
            raise CompilerError(f"Can't convert instance of '{value_type}' to python code")

    def replace_vars(self, ast_obj: Union[ast.AST, List[ast.AST]], keyword: Keyword) -> Any:
        if type(ast_obj) == ast.Name and ast_obj.id == "self":
            return ast.Name(id=f"k{id(keyword)}", ctx=ast.Load())
        elif type(ast_obj) == ast.Attribute and type(ast_obj.value) == ast.Name:
            if ast_obj.value.id == "self":
                return ast.Name(id=f"k{id(keyword)}_{ast_obj.attr}", ctx=ast.Load())
        elif type(ast_obj) == list:
            for i, _ast_obj in enumerate(ast_obj):
                ast_obj[i] = self.replace_vars(_ast_obj, keyword)
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                setattr(ast_obj, field, self.replace_vars(getattr(ast_obj, field), keyword))
        return ast_obj

    def replace_return_stmt(self, ast_obj: Union[ast.AST, List[ast.AST]]) -> Any:
        flag = False
        if type(ast_obj) == ast.Return:
            return True, ast.Raise(
                exc=ast.Call(func=ast.Name(id="ReturnStmt", ctx=ast.Load()), args=[], keywords=[])
            )
        elif type(ast_obj) == list:
            for i, _ast_obj in enumerate(ast_obj):
                new_flag, new_ast_obj = self.replace_return_stmt(_ast_obj)
                flag = flag or new_flag
                ast_obj[i] = new_ast_obj
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                new_flag, new_ast_obj = self.replace_return_stmt(getattr(ast_obj, field))
                flag = flag or new_flag
                setattr(ast_obj, field, new_ast_obj)
        return flag, ast_obj

    def compile_fn(self, fn: Callable, keyword: Keyword) -> List[ast.AST]:
        ast_function = self.to_ast(fn)
        self.check_parameters(ast_function.args.args)

        ast_function.body = self.replace_vars(ast_function.body, keyword)

        flag, ast_function.body = self.replace_return_stmt(ast_function.body)
        if flag:
            ast_function.body = [ast.Try(
                body=ast_function.body,
                handlers=[
                    ast.ExceptHandler(
                        type=ast.Name(id="ReturnStmt", ctx=ast.Load()),
                        body=[ast.Pass()]
                    )
                ],
                orelse=[],
                finalbody=[]
            )]

        return ast_function.body

    def find_and_compile_programs(self, value: Any) -> str:
        result = []
        if isinstance(value, (list, set, tuple)):
            for item in value:
                item = self.find_and_compile_programs(item)
                if item:
                    result.append(item)
            return "\n\n".join(result)
        elif isinstance(value, dict):
            for item in value.values():
                item = self.find_and_compile_programs(item)
                if item:
                    result.append(item)
            return "\n\n".join(result)
        elif isinstance(value, Program):
            _, code = self._run(value)
            return code
        else:
            return ""

    def _find_keyword_attrs(self, ast_obj: Union[ast.AST, List[ast.AST]], keyword: Keyword) -> dict:
        result = {}
        if type(ast_obj) == ast.Attribute and type(ast_obj.value) == ast.Name:
            if ast_obj.value.id == "self":
                result[f"k{id(keyword)}_{ast_obj.attr}"] = getattr(keyword, ast_obj.attr)
        elif type(ast_obj) == list:
            for _ast_obj in ast_obj:
                result.update(self._find_keyword_attrs(_ast_obj, keyword))
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                result.update(self._find_keyword_attrs(getattr(ast_obj, field), keyword))
        return result

    def find_keyword_attrs(self, program: Program) -> dict:
        result = {}
        for fn, keyword in program._general:
            result[f"k{id(keyword)}"] = keyword
            ast_function = self.to_ast(fn)
            self.check_parameters(ast_function.args.args)
            result.update(self._find_keyword_attrs(ast_function, keyword))

        for _, keywords in program._type_specific.items():
            for fn, keyword in keywords:
                result[f"k{id(keyword)}"] = keyword
                ast_function = self.to_ast(fn)
                self.check_parameters(ast_function.args.args)
                result.update(self._find_keyword_attrs(ast_function, keyword))
        return result

    def ast_body(self, program: Program) -> List[ast.AST]:
        result: List[ast.AST] = []

        for fn, keyword in program._general:
            result.extend(self.compile_fn(fn, keyword))

        append = result.append
        for t, keywords in program._type_specific.items():
            type_specific_result: List[ast.AST] = []
            for fn, keyword in keywords:
                type_specific_result.extend(self.compile_fn(fn, keyword))

            orelse = []
            append(ast.If(
                test=ast.Compare(
                    left=ast.Call(
                        func=ast.Name(id="type", ctx=ast.Load()),
                        args=[ast.Name(id="value", ctx=ast.Load())],
                        keywords=[]
                    ),
                    ops=[ast.Eq()],
                    comparators=[ast.Name(id=self.to_python_code(t), ctx=ast.Load())]
                ),
                body=type_specific_result,
                orelse=orelse
            ))
            append = orelse.append

        return result

    def count_type_calling(self, ast_obj: Union[ast.AST, List[ast.AST]]) -> int:
        result = 0
        if type(ast_obj) == ast.Call and type(ast_obj.func) == ast.Name and ast_obj.func.id == "type":
            if len(ast_obj.args or []) == 1 and \
                    type(ast_obj.args[0]) == ast.Name and \
                    ast_obj.args[0].id == "value" and \
                    not ast_obj.keywords:
                result += 1
        elif type(ast_obj) == list:
            for i, _ast_obj in enumerate(ast_obj):
                result += self.count_type_calling(_ast_obj)
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                result += self.count_type_calling(getattr(ast_obj, field))
        return result

    def replace_type_calling(self, ast_obj: Union[ast.AST, List[ast.AST]], var_name: str) -> Union[ast.AST, List[ast.AST]]:
        if type(ast_obj) == ast.Call and type(ast_obj.func) == ast.Name and ast_obj.func.id == "type":
            if len(ast_obj.args or []) == 1 and \
                    type(ast_obj.args[0]) == ast.Name and \
                    ast_obj.args[0].id == "value" and \
                    not ast_obj.keywords:
                return ast.Name(id=var_name, ctx=ast.Load())
        elif type(ast_obj) == list:
            for i, _ast_obj in enumerate(ast_obj):
                ast_obj[i] = self.replace_type_calling(_ast_obj, var_name)
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                setattr(ast_obj, field, self.replace_type_calling(getattr(ast_obj, field), var_name))
        return ast_obj

    def optimize_type_calling(self, body: List[ast.AST], program_id: int) -> List[ast.AST]:
        var_name = f"value_type_{program_id}"
        if self.count_type_calling(body) > 1:
            body = self.replace_type_calling(body, var_name)
            body.insert(
                0,
                ast.Assign(
                    targets=[ast.Name(id=var_name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id="type", ctx=ast.Load()),
                        args=[ast.Name(id="value", ctx=ast.Load())],
                        keywords=[]
                    ),
                    lineno=0
                )
            )
        return body

    def compute_attr(self, python_value: str) -> ast.AST:
        code = self.to_python_code(python_value)
        ast_obj = ast.parse(code)
        return ast_obj.body[0].value

    def optimize_vars(self, ast_obj: Union[ast.AST, List[ast.AST]], attributes: dict, replaced: dict) -> Union[ast.AST, List[ast.AST]]:
        if type(ast_obj) == ast.Subscript and type(ast_obj.value) == ast.Name and ast_obj.value.id in attributes:
            if type(ast_obj.slice) == ast.Constant and ast_obj.slice.value in attributes[ast_obj.value.id]:
                replaced[ast_obj.value.id][ast_obj.slice.value] = True
                return self.compute_attr(attributes[ast_obj.value.id][ast_obj.slice.value])
        elif type(ast_obj) == ast.Name and ast_obj.id in attributes:
            replaced[ast_obj.id] = True
            return self.compute_attr(attributes[ast_obj.id])
        elif type(ast_obj) == list:
            for i, _ast_obj in enumerate(ast_obj):
                ast_obj[i] = self.optimize_vars(_ast_obj, attributes, replaced)
        elif isinstance(ast_obj, ast.AST):
            for field in ast_obj._fields or []:
                setattr(ast_obj, field, self.optimize_vars(getattr(ast_obj, field), attributes, replaced))
        return ast_obj

    def remove_unused_attrs(self, attributes: dict, unused: dict):
        for k0, v in unused.items():
            if type(v) == dict:
                for k1 in v.keys():
                    del attributes[k0][k1]
                if not attributes[k0]:
                    del attributes[k0]
            else:
                del attributes[k0]

    def optimize(self, body: List[ast.AST], attributes: dict, program: Program) -> List[ast.AST]:
        body = self.optimize_type_calling(body, id(program))
        replaced = defaultdict(dict)
        body = self.optimize_vars(body, attributes, replaced)
        self.remove_unused_attrs(attributes, replaced)
        return body

    def ast_init_variables(self) -> List[ast.Assign]:
        return [
            ast.Assign(
                targets=[ast.Name(id="path", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
                lineno=None
            ),
            ast.Assign(
                targets=[ast.Name(id="errors", ctx=ast.Store())],
                value=ast.List(elts=[], ctx=ast.Load()),
                lineno=None
            )
        ]

    def ast_function(self, name_postfix: str, body: List[ast.AST],  is_entry_point: bool) -> Tuple[str, ast.FunctionDef]:
        if is_entry_point:
            args = [ast.arg("value")]
            body = self.ast_init_variables() + body
        else:
            args = [ast.arg("path"), ast.arg("value"), ast.arg("errors")]

        name = f"program_{name_postfix}"
        return name, ast.FunctionDef(
            name=name,
            args=ast.arguments(
                posonlyargs=[],
                args=args,
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[]
            ),
            body=body + [ast.Return(value=ast.Name(id="errors", ctx=ast.Load()))],
            decorator_list=[],
            lineno=0
        )

    def _run(self, program: Program, is_entry_point: bool = False) -> Tuple[str, str]:
        body = self.ast_body(program)
        attributes = self.find_keyword_attrs(program)
        programs = self.find_and_compile_programs(attributes)
        body = self.optimize(body, attributes, program)

        compiled_attrs = []
        for key, value in attributes.items():
            compiled_attrs.append(f"{key} = {self.to_python_code(value)}")
        compiled_attrs = "\n".join(compiled_attrs)

        fn_name, code = self.ast_function(str(id(program)), body, is_entry_point)

        code = [programs, compiled_attrs, ast.unparse(code)]

        return fn_name, "\n\n".join((item for item in code if item))

    def run(self) -> Tuple[str, Callable]:
        self._init()

        fn_name, code = self._run(self.program, True)

        code = f"{BEFORE_FUNCTION_CODE}\n\n\n{code}"
        state = {}
        exec(code, state)
        return code, state[fn_name]
