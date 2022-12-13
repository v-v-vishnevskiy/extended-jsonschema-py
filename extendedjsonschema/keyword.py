from typing import Any, Dict, List, Tuple, Union

from extendedjsonschema.utils import JSON


class Keyword:
    name: str = None
    type: Union[str, Tuple[str, ...]] = None

    def __init__(self, value: JSON, schema: "Schema", path: List[Union[str, int]], rules: Dict[str, "Keyword"]):
        self._value = value
        self.schema = schema
        self.path = path
        self.rules = rules

    def set_variable(self, name: str, value: Any):
        self.schema.state.set_variable(self, name, value)

    def import_package(self, package: str):
        self.schema.imports.import_package(package)

    def import_module(self, package: str, module: str):
        self.schema.imports.import_module(package, module)

    @property
    def value(self):
        return self._value

    def validate(self) -> None:
        raise NotImplementedError("Please implement this method")

    def compile(self) -> str:
        raise NotImplementedError("Please implement this method")

    def __repr__(self) -> str:
        return f"{self.name}: {self.value}"
