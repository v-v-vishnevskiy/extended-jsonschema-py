from collections import defaultdict
from typing import Any, Dict, List, Set, Union

from extendedjsonschema.errors import Error
from extendedjsonschema.program import Program
from extendedjsonschema.tools import to_python_code, DataIndex, Variable
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
        self._code = []
        self._variables = defaultdict(dict)
        self._errors = defaultdict(dict)
        self._used_variables = set()

    def add_code(self, code: str):
        if code not in self._code:
            self._code.append(code)

    def set_variable(self, keyword: "Keyword", name: str, value: Any):
        if name.startswith("data") or name.startswith("error"):
            raise Error(f"The '{name}' variable is defined automatically. You can't define it manually")
        self._variables[id(keyword)][name] = value

    def set_errors(self, keyword: "Keyword", errors: Dict[str, dict]):
        for variable, error in errors.items():
            self._errors[id(keyword)][variable] = error

    def variables(self, keyword: "Keyword", variables: Set[str]) -> Dict[str, str]:
        keyword_id = id(keyword)
        result = {}
        for name in self._variables[keyword_id].keys():
            if name in variables:
                var_name = f"k{keyword_id}_{name}"
                result[name] = var_name
                self._used_variables.add(var_name)
        for variable in self._errors.get(keyword_id, {}).keys():
            if variable in variables:
                var_name = f"k{keyword_id}_{variable}"
                result[variable] = f"errors.append({var_name})"
                self._used_variables.add(var_name)
        return result

    def compile_code(self) -> str:
        return "\n\n".join(self._code)

    def compile_variables(self) -> str:
        result = []
        for keyword_id, variables in self._variables.items():
            for name, value in variables.items():
                var_name = f"k{keyword_id}_{name}"
                if var_name in self._used_variables:
                    result.append(f"{var_name} = {to_python_code(value)}")
        return "\n".join(result)

    def compile_errors(self) -> str:
        result = []
        for keyword_id, errors in self._errors.items():
            for variable, error in errors.items():
                var_name = f"k{keyword_id}_{variable}"
                if var_name in self._used_variables:
                    result.append(f"{var_name} = {to_python_code(error)}")
        return "\n".join(result)

    def compile_all(self) -> str:
        result = []
        code = self.compile_code()
        if code:
            result.append(code)
        variables = self.compile_variables()
        if variables:
            result.append(variables)
        errors = self.compile_errors()
        if errors:
            result.append(errors)
        return "\n\n".join(result)


class DataVariable:
    def __init__(self):
        self._data: List[dict] = [{"name": "data", "path": []}]
        self._path: List[Union[DataIndex, None]] = []

    def push(self, name: Union[str, None], path: Union[DataIndex, None]) -> str:
        if path is not None and not isinstance(path, DataIndex):
            raise ValueError("The value of 'path' parameter must be an instance of subclass of 'DataIndex' class")

        self._path.append(path)

        name = name or self._data[-1]["name"]
        data_path = [path] if path is not None else []

        if name != self._data[-1]["name"]:
            new_data_path = []
        else:
            new_data_path = self._data[-1]["path"][:] + data_path
        self._data.append({"name": name, "path": new_data_path})
        return name + "".join([f"[{to_python_code(s)}]" for s in self._data[-1]["path"]])

    @property
    def path(self) -> List[DataIndex]:
        return [item for item in self._path if item]

    @property
    def path_has_variables(self) -> bool:
        for item in self._path:
            if isinstance(item, Variable):
                return True
        return False

    def pop(self):
        self._data.pop()
        self._path.pop()


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
