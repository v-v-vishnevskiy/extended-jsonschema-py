from typing import Any, Dict, List, Tuple, Union

from extendedjsonschema.schema import Schema
from extendedjsonschema.utils import JSON, RULE


class Keyword:
    __slots__ = "value", "schema", "path", "rules", "property"
    name: str = None
    type: Union[str, Tuple[str, ...]] = None

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, "Keyword"]):
        self.value = value
        self.schema = schema
        self.path = path
        self.rules = rules
        self.property: Dict[str, Any] = {}

    def validate(self) -> None:
        raise NotImplementedError("Please implement this method")

    def compile(self) -> Union[None, RULE]:
        raise NotImplementedError("Please implement this method")

    def __repr__(self):
        return f"{self.name}: {self.value}"
