from typing import Any, Dict, List, Tuple, Union

from extendedjsonschema.utils import JSON, RULE


class Keyword:
    name: str = None
    type: Union[str, Tuple[str, ...]] = None

    def __init__(self, value: JSON, schema: "Schema", path: List[Union[str, int]], rules: Dict[str, "Keyword"]):
        self.__value = value
        self.schema = schema
        self.path = path
        self.rules = rules
        self.property: Dict[str, Any] = {}

    @property
    def value(self):
        return self.__value

    def validate(self) -> None:
        raise NotImplementedError("Please implement this method")

    def compile(self) -> Union[None, RULE]:
        raise NotImplementedError("Please implement this method")

    def __repr__(self):
        return f"{self.name}: {self.value}"
