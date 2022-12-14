from collections import defaultdict
from typing import Any, Dict, List, Union

from extendedjsonschema.errors import Error
from extendedjsonschema.program import Program
from extendedjsonschema.tools import to_python_code
from extendedjsonschema.utils import JSON, PATH


class Imports:
    def __init__(self):
        self._packages = set()
        self._modules = defaultdict(set)

    def compile_packages(self) -> str:
        return "\n".join(f"import {package}" for package in sorted(self._packages))

    def compile_modules(self) -> str:
        result = []
        for package, modules in self._modules.items():
            modules = ", ".join(sorted(modules))
            result.append(f"from {package} import {modules}")
        return "\n".join(result)

    def compile_all(self) -> str:
        result = []
        packages = self.compile_packages()
        if packages:
            result.append(packages)
        modules = self.compile_modules()
        if modules:
            result.append(modules)
        return "\n\n".join(result)

    def import_package(self, package: str):
        self._packages.add(package)

    def import_module(self, package: str, module: str):
        self._modules[package].add(module)


class State:
    def __init__(self):
        self._errors = {}
        self._variables = defaultdict(dict)

    def set_error(self, keyword: "Keyword", value: Any):
        self._errors[id(keyword)] = value

    def set_variable(self, keyword: "Keyword", name: str, value: Any):
        if name in {"data", "error"}:
            raise Error(f"The '{name}' variable is defined automatically. You can't define it manually")
        self._variables[id(keyword)][name] = value

    def variables(self, keyword: "Keyword") -> Dict[str, str]:
        keyword_id = id(keyword)
        result = {}
        for name in self._variables[keyword_id].keys():
            result[name] = f"k{keyword_id}_{name}"
        if keyword_id in self._errors:
            result["error"] = f"errors.append(k{id(keyword)}_error)"
        return result

    def compile_variables(self) -> str:
        result = []
        for keyword_id, variables in self._variables.items():
            for name, value in variables.items():
                result.append(f"k{keyword_id}_{name} = {to_python_code(value)}")
        return "\n".join(result)

    def compile_errors(self) -> str:
        result = []
        for keyword_id, value in self._errors.items():
            result.append(f"k{keyword_id}_error = {to_python_code(value)}")
        return "\n".join(result)

    def compile_all(self) -> str:
        result = []
        variables = self.compile_variables()
        if variables:
            result.append(variables)
        errors = self.compile_errors()
        if errors:
            result.append(errors)
        return "\n\n".join(result)


class DataVariable:
    def __init__(self):
        self._stack: List[dict] = []

    def push(self, name: str, ik: Union[int, str, None]) -> str:
        data_slice = [ik] if ik not in {"", None} else []
        if not self._stack or name != self._stack[-1]["name"]:
            new_data_slice = data_slice
        else:
            new_data_slice = self._stack[-1]["ik"][:] + data_slice
        self._stack.append({"name": name, "ik": new_data_slice})
        return name + "".join([f"[{to_python_code(s)}]" for s in self._stack[-1]["ik"]])

    def pop(self):
        self._stack.pop()


class Schema:
    def __init__(self):
        self.imports = Imports()
        self.state = State()
        self.data_variable = DataVariable()

    @staticmethod
    def is_schema(value: JSON):
        raise NotImplementedError("Please implement this method")

    def program(self, schema: dict, path: PATH = None) -> Program:
        raise NotImplementedError("Please implement this method")
