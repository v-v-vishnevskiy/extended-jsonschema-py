from typing import Dict, List, Union

from extendedjsonschema.utils import JSON, RULE, Error


class Program:
    def __init__(self, general: List[RULE] = None, type_specific: Dict[type, List[RULE]] = None, field: str = ""):
        self.field = field
        self._general = general or []
        self._type_specific = type_specific or {}
        self._has_programs = bool(self._general) or bool(self._type_specific)

    def __bool__(self) -> bool:
        return self._has_programs

    def run(self, path: List[Union[str, int]], data: JSON, errors: List[Error]):
        for fn, k in self._general + self._type_specific.get(type(data), []):
            fn(path, data, errors)

    def to_string(self, depth: int = 0, indent: int = 2):
        result = []
        d = 0

        if self.field:
            d += 1
            field = f"'{self.field}'" if self.field else ""
            result.append(f"{' ' * (depth * indent)}{field}:")

        empty = ""
        if not self._has_programs:
            empty = " empty"

        result.append(f"{' ' * ((depth + d) * indent)}Program <{hex(id(self))}>:{empty}")

        if self._general:
            general = "\n".join([f"{keyword.to_string(depth + 2 + d, indent)}" for _, keyword in self._general])
            result.append(f"{' ' * ((depth + 1 + d)*indent)}General:\n{general}")

        if self._type_specific:
            type_specific = []
            for t, keywords in self._type_specific.items():
                type_specific.append(f"{' ' * ((depth + 2 + d)*indent)}{t}")
                for _, keyword in keywords:
                    type_specific.append(f"{keyword.to_string(depth + 3 + d, indent)}")
            type_specific = "\n".join(type_specific)
            result.append(f"{' ' * ((depth + 1 + d)*indent)}Type Specific:\n{type_specific}")

        return "\n".join(result)

    def __repr__(self):
        return self.to_string()


class Compiler:
    def run(self, schema: dict, path: List[Union[str, int]] = None) -> Program:
        raise NotImplementedError("Please implement this method")
