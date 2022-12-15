import re

from collections.abc import Iterable
from typing import Any, Union

from extendedjsonschema.errors import CompilerError


class DataIndex:
    def __init__(self, value: Union[int, str]):
        self.value = value

    def __repr__(self):
        return f"{self.__class__.__name__}(value={self.value})"


class Const(DataIndex):
    pass


class Variable(DataIndex):
    pass


def is_equal(t1, t2, data1, data2):
    if t1 != t2:
        return False

    if t1 not in {list, dict}:
        if data1 != data2:
            return False
    else:
        if t1 == list:
            if len(data1) != len(data2):
                return False
            else:
                for i, item1 in enumerate(data1):
                    if not is_equal(type(item1), type(data2[i]), item1, data2[i]):
                        return False
        else:  # dict
            if set(data1.keys()) != set(data2.keys()):
                return False
            else:
                for k, value in data1.items():
                    if not is_equal(type(value), type(data2[k]), value, data2[k]):
                        return False
    return True


def non_unique_items(value: list) -> set:
    result = set()
    n = len(value)
    m = n - 1
    if n > 1:
        i = 0
        while i < m:
            type_i = type(value[i])
            j = i + 1
            while j < n:
                if j not in result:
                    if is_equal(type_i, type(value[j]), value[i], value[j]):
                        result.add(j)
                j += 1
            i += 1
    return result


def add_indent(code: str, i: int = 1) -> str:
    result = []
    if i < 0:
        i = 0
    s = "    " * i
    for line in code.split("\n"):
        result.append(f"{s}{line}")
    return "\n".join(result)


def to_python_code(value: Any) -> str:
    value_type = type(value)
    if value_type in {list, tuple, set}:
        brackets = {list: ("[", "]"), tuple: ("(", ")"), set: ("{", "}")}
        result = []
        for item in value:
            result.append(to_python_code(item))
        return brackets[value_type][0] + ", ".join(result) + brackets[value_type][1]
    elif value_type == dict:
        result = []
        for k, v in value.items():
            result.append(f"{to_python_code(k)}: {to_python_code(v)}")
        result = ", ".join(result)
        return f"{{{result}}}"
    elif value_type in {bool, int, float, type(None)}:
        return str(value)
    elif value_type == str:
        return f'"{value}"'
    elif isinstance(value, type):
        return value.__name__
    elif isinstance(value, Iterable):
        return to_python_code(list(value))
    elif isinstance(value, re.Pattern):
        return str(value)
    elif isinstance(value, Const):
        return to_python_code(value.value)
    elif isinstance(value, Variable):
        return value.value
    else:
        raise CompilerError(f"Can't convert instance of '{value_type}' to python code")
