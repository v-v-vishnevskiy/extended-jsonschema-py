from typing import Dict, List, Tuple, Union

from extendedjsonschema.schema import Schema
from extendedjsonschema.utils import JSON, RULE


class Keyword:
    __slots__ = "value", "schema", "path", "rules"
    name: str = None
    type: Union[str, Tuple[str, ...]] = None

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, "Keyword"]):
        self.value = value
        self.schema = schema
        self.path = path
        self.rules = rules

    def validate(self) -> None:
        raise NotImplementedError("Please implement this method")

    def compile(self) -> Union[None, RULE]:
        raise NotImplementedError("Please implement this method")

    def to_string(self, depth: int = 0, indent: int = 2):
        return f"{' ' * depth*indent}{self.name}: {self.value}"

    def __repr__(self):
        return self.to_string()
