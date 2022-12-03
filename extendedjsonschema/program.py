from typing import Dict, List, Tuple

from extendedjsonschema.keyword import Keyword
from extendedjsonschema.utils import ERRORS, JSON, PATH, RULE


class Program:
    def __init__(self, general: List[Tuple[RULE, Keyword]] = None,
                 type_specific: Dict[type, List[Tuple[RULE, Keyword]]] = None, field: str = ""):
        self.field = field
        self._general = general or []
        self._type_specific = type_specific or {}
        self._has_programs = bool(self._general) or bool(self._type_specific)

    def __bool__(self) -> bool:
        return self._has_programs

    def __call__(self, path: PATH, value: JSON, errors: ERRORS):
        for fn, keyword in self._general + self._type_specific.get(type(value), []):
            fn(path, value, errors)
