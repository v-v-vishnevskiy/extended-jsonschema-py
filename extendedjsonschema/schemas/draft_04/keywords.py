import re
from typing import Dict, List, Union

from extendedjsonschema.schema import Schema
from extendedjsonschema.errors import SchemaError
from extendedjsonschema.keyword import Keyword
from extendedjsonschema.utils import JSON, RULE, Error


# General
class Type(Keyword):
    __slots__ = "_compiled_value"
    name = "type"
    valid_types = {
        "array": list,
        "boolean": bool,
        "integer": int,
        "null": type(None),
        "number": float,
        "object": dict,
        "string": str
    }

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._compiled_value = None

    def validate(self):
        valid_types = set(self.valid_types.keys())

        if type(self.value) == str:
            if self.value not in self.valid_types:
                raise SchemaError(self.path, f"Invalid type. Possible types: {', '.join(sorted(valid_types))}")
        elif type(self.value) == list:
            if len(self.value) == 0:
                raise SchemaError(self.path, "It must be an non-empty array of strings")
            elif len(list(filter(lambda x: type(x) != str or len(x) == 0, self.value))) > 0:
                raise SchemaError(self.path, "It must be an array, where each element is a non-empty string")
            elif len(self.value) != len(set(self.value)):
                raise SchemaError(self.path, "It must be an array of strings, where each element is unique")
            elif (set(self.value) & valid_types) != set(self.value):
                raise SchemaError(self.path, f"Invalid types. Possible types: {', '.join(sorted(valid_types))}")
        else:
            raise SchemaError(self.path, "The value of this keyword must be either a string or an array of strings")

    def program(self, path: List[Union[str, int]], value: JSON, errors: List[Error]):
        if type(value) != self._compiled_value:
            errors.append(Error(path, self))

    def program_list(self, path: List[Union[str, int]], value: JSON, errors: List[Error]):
        if type(value) not in self._compiled_value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        if type(self.value) == str:
            self._compiled_value = self.valid_types[self.value]
            return self.program
        else:
            self._compiled_value = {self.valid_types[t] for t in self.value}
            return self.program_list


class Enum(Keyword):
    __slots__ = "_enum_values"
    name = "enum"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._enum_values = set()

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        elif len(self.value) == 0:
            raise SchemaError(self.path, "It must be an array with at least one element")
        elif len(self.value) != len(set(self.value)):
            raise SchemaError(self.path, "It must be an array, where each element is unique")
        # TODO: check intersection of `type` and `enum` values

    def program(self, path: List[Union[str, int]], value: JSON, errors: List[Error]):
        if value not in self._enum_values:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        self._enum_values = set(self.value)
        return self.program


class AllOf(Keyword):
    __slots__ = "_programs"
    name = "allOf"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._programs = []

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if type(item) != dict:
                raise SchemaError(self.path + [i], "It must be an object")

    def program(self, path: List[Union[str, int]], value: JSON, errors: List[Error]):
        for p in self._programs:
            p.run(path, value, errors)

    def compile(self) -> Union[None, RULE]:
        for item in self.value:
            self._programs.append(self.schema.compile(item))
        return self.program

    def to_string(self, depth: int = 0, indent: int = 2):
        programs = "\n".join([
            f"{' ' * (depth + 1) * indent}{i}:\n{p.to_string(depth + 2, indent)}"
            for i, p in enumerate(self._programs)
        ])
        return f"{' ' * depth * indent}{self.name}:\n{programs}"


class AnyOf(Keyword):
    __slots__ = "_programs"
    name = "anyOf"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._programs = []

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if type(item) != dict:
                raise SchemaError(self.path + [i], "It must be an object")

    def program(self, path: List[Union[str, int]], value: JSON, errors: List[Error]):
        errs = []
        for p in self._programs:
            e = []
            p.run(path, value, e)
            if not e:
                return
            else:
                errs.extend(e)
        errors.extend(errs)

    def compile(self) -> Union[None, RULE]:
        for item in self.value:
            self._programs.append(self.schema.compile(item))
        return self.program

    def to_string(self, depth: int = 0, indent: int = 2):
        programs = "\n".join([
            f"{' ' * (depth + 1) * indent}{i}:\n{p.to_string(depth + 2, indent)}"
            for i, p in enumerate(self._programs)
        ])
        return f"{' ' * depth * indent}{self.name}:\n{programs}"


class OneOf(Keyword):
    __slots__ = "_programs"
    name = "oneOf"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._programs = []

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if type(item) != dict:
                raise SchemaError(self.path + [i], "It must be an object")

    def program(self, path: List[Union[str, int]], value: JSON, errors: List[Error]):
        n_successes = 0
        for p in self._programs:
            e = []
            p.run(path, value, e)
            if not e:
                n_successes += 1
        if n_successes != 1:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        for item in self.value:
            self._programs.append(self.schema.compile(item))
        return self.program

    def to_string(self, depth: int = 0, indent: int = 2):
        programs = "\n".join([
            f"{' ' * (depth + 1) * indent}{i}:\n{p.to_string(depth + 2, indent)}"
            for i, p in enumerate(self._programs)
        ])
        return f"{' ' * depth * indent}{self.name}:\n{programs}"


# schema composition
class Not(Keyword):
    __slots__ = "_program"
    name = "not"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._program = None

    def validate(self):
        if type(self.value) != dict:
            raise SchemaError(self.path, "It must be an object")

    def compile(self) -> Union[None, RULE]:
        self._program = self.schema.compile(self.value)
        return self._program.run

    def to_string(self, depth: int = 0, indent: int = 2):
        return f"{' ' * depth*indent}{self.name}:\n{self._program.to_string(depth + 1, indent)}"


# Array
class Items(Keyword):
    __slots__ = "_program_list", "_program_tuple"
    name = "items"
    type = "array"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._program_list = None
        self._program_tuple = []

    def validate(self):
        if type(self.value) not in {dict, list}:
            raise SchemaError(self.path, "It must be an object or an array")
        if type(self.value) == list:
            for i, item in enumerate(self.value):
                if type(item) != dict:
                    raise SchemaError(self.path + [i], "It must be an object")

    def program_list(self, path: List[Union[str, int]], value: List[JSON], errors: List[Error]):
        for i, item in enumerate(value):
            self._program_list.run(path + [i], item, errors)

    def program_tuple(self, path: List[Union[str, int]], value: List[JSON], errors: List[Error]):
        i = 0
        n = min(len(self._program_tuple), len(value))
        while i < n:
            self._program_tuple[i].run(path + [i], value[i], errors)
            i += 1

    def compile(self) -> Union[None, RULE]:
        if type(self.value) == dict:
            self._program_list = self.schema.compile(self.value)
            return self.program_list
        else:
            self._program_tuple = [self.schema.compile(item) for item in self.value]
            return self.program_tuple

    def to_string(self, depth: int = 0, indent: int = 2):
        if type(self.value) == dict:
            return f"{' ' * depth * indent}{self.name}:\n{self._program_list.to_string(depth + 1, indent)}"
        else:
            programs = "\n".join([
                f"{' ' * (depth + 1) * indent}{i}:\n{p.to_string(depth + 2, indent)}"
                for i, p in enumerate(self._program_tuple)
            ])
            return f"{' ' * depth * indent}{self.name}:\n{programs}"


class AdditionalItems(Keyword):
    __slots__ = "_program", "_items_tuple_programs"
    name = "additionalItems"
    type = "array"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._program = None
        self._items_tuple_programs = 0

    def validate(self):
        if type(self.value) not in {bool, dict}:
            raise SchemaError(self.path, "It must be a boolean or an object")

    def false_program(self, path: List[Union[str, int]], value: list, errors: List[Error]):
        if len(value) > self._items_tuple_programs:
            for i in range(self._items_tuple_programs, len(value)):
                errors.append(Error(path + [i], self))

    def program(self, path: List[Union[str, int]], value: list, errors: List[Error]):
        if len(value) > self._items_tuple_programs:
            for i in range(self._items_tuple_programs, len(value)):
                self._program.run(path + [i], value[i], errors)

    def compile(self) -> Union[None, RULE]:
        if "items" in self.rules and type(self.rules["items"].value) == list:
            self._items_tuple_programs = len(self.rules["items"].value)

        if self.value is True:
            return None
        elif self.value is False:
            return self.false_program
        else:
            self._program = self.schema.compile(self.value)
            if self._program:
                return self.program
            else:
                return None

    def to_string(self, depth: int = 0, indent: int = 2):
        if type(self.value) == bool:
            return super().to_string(depth, indent)
        else:
            return f"{' ' * depth * indent}{self.name}:\n{self._program.to_string(depth + 1, indent)}"


class MinItems(Keyword):
    name = "minItems"
    type = "array"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")

    def program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        if len(value) < self.value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        return self.program


class MaxItems(Keyword):
    name = "maxItems"
    type = "array"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")
        elif "minItems" in self.rules:
            self.rules["minItems"].validate()
            if self.value < self.rules["minItems"].value:
                raise SchemaError(self.path, "It must be greater or equal to `minItems`")

    def program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        if len(value) > self.value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        return self.program


class UniqueItems(Keyword):
    __slots__ = "_gen"
    name = "uniqueItems"
    type = "array"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._gen = {list: lambda data: enumerate(data), dict: lambda data: data.items()}

    def validate(self):
        if type(self.value) != bool:
            raise SchemaError(self.path, "It must be a boolean")

    def _is_equal(self, t1, t2, data1: Union[list, dict], data2: Union[list, dict]) -> bool:
        if t1 != t2:
            return False

        if t1 not in {list, dict}:
            if data1 != data2:
                return False
        else:
            if t1 == list:
                if len(data1) != len(data2):
                    return False
            else:  # dict
                if set(data1.keys()) != set(data2.keys()):
                    return False

            for i, item1 in self._gen[t1](data1):
                if not self._is_equal(type(item1), type(data2[i]), item1, data2[i]):
                    return False
        return True

    def program(self, path: List[Union[str, int]], value: List[JSON], errors: List[Error]):
        non_unique_indexes = set()
        n = len(value)
        m = n - 1
        if n > 1:
            i = 0
            while i < m:
                type_i = type(value[i])
                j = i + 1
                while j < n:
                    if j not in non_unique_indexes:
                        if self._is_equal(type_i, type(value[j]), value[i], value[j]):
                            non_unique_indexes.add(j)
                    j += 1
                i += 1
        for i in sorted(non_unique_indexes):
            errors.append(Error(path + [i], self))

    def compile(self) -> Union[None, RULE]:
        if self.value:
            return self.program
        else:
            return None


# Number and Integer
class MultipleOf(Keyword):
    name = "multipleOf"
    type = "integer", "number"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be strictly greater than 0")

    def program(self, path: List[Union[str, int]], value: Union[int, float], errors: List[Error]):
        if value % self.value != 0:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        return self.program


class Minimum(Keyword):
    name = "minimum"
    type = "integer", "number"

    def validate(self):
        if type(self.value) not in {int, float}:
            raise SchemaError(self.path, "It must be an integer or a number")

    def program_strict(self, path: List[Union[str, int]], value: Union[int, float], errors: List[Error]):
        if value <= self.value:
            return errors.append(Error(path, self))

    def program(self, path: List[Union[str, int]], value: Union[int, float], errors: List[Error]):
        if value < self.value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        if "exclusiveMinimum" in self.rules and self.rules["exclusiveMinimum"].value is True:
            return self.program_strict
        else:
            return self.program


class Maximum(Keyword):
    name = "maximum"
    type = "integer", "number"

    def validate(self):
        if type(self.value) not in {int, float}:
            raise SchemaError(self.path, "It must be an integer or a number")
        elif "minimum" in self.rules:
            self.rules["minimum"].validate()
            if self.value < self.rules["minimum"].value:
                raise SchemaError(self.path, "It must be greater or equal to `minimum`")

    def program_strict(self, path: List[Union[str, int]], value: Union[int, float], errors: List[Error]):
        if value >= self.value:
            errors.append(Error(path, self))

    def program(self, path: List[Union[str, int]], value: Union[int, float], errors: List[Error]):
        if value > self.value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        if "exclusiveMaximum" in self.rules and self.rules["exclusiveMaximum"].value is True:
            return self.program_strict
        else:
            return self.program


class ExclusiveMinimum(Keyword):
    name = "exclusiveMinimum"
    type = "integer", "number"

    def validate(self):
        if type(self.value) != bool:
            raise SchemaError(self.path, "It must be a boolean")

    def compile(self) -> Union[None, RULE]:
        return None


class ExclusiveMaximum(Keyword):
    name = "exclusiveMaximum"
    type = "integer", "number"

    def validate(self):
        if type(self.value) != bool:
            raise SchemaError(self.path, "It must be a boolean")

    def compile(self) -> Union[None, RULE]:
        return None


# Object
class Properties(Keyword):
    __slots__ = "_programs"
    name = "properties"
    type = "object"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._programs = {}

    def validate(self):
        if type(self.value) != dict:
            raise SchemaError(self.path, "It must be an object")
        elif len(self.value.keys()) == 0:
            raise SchemaError(self.path, "It must be an object with at least one key-value pair")
        elif len(list(filter(lambda x: type(x) != str or len(x) == 0, self.value.keys()))) > 0:
            raise SchemaError(self.path, "It must be an object, where each key is a non-empty string")
        else:
            for key, value in self.value.items():
                if type(value) != dict:
                    raise SchemaError(self.path + [key], "It must be an object")

    def program(self, path: List[Union[str, int]], value: dict, errors: List[Error]):
        for k, v in value.items():
            if k not in self._programs:
                continue
            self._programs[k].run(path + [k], v, errors)

    def compile(self) -> Union[None, RULE]:
        for k, v in self.value.items():
            self._programs[k] = self.schema.compile(v, self.path + [k])
        return self.program

    def to_string(self, depth: int = 0, indent: int = 2):
        programs = "\n".join(p.to_string(depth + 1, indent) for p in self._programs.values())
        return f"{' ' * depth*indent}{self.name}:\n{programs}"


class PatternProperties(Keyword):
    __slots__ = "_programs", "_properties"
    name = "patternProperties"
    type = "object"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._programs = {}
        self._properties = set()

    def validate(self):
        if type(self.value) != dict:
            raise SchemaError(self.path, "It must be an object")

        if len(self.value.keys()) == 0:
            raise SchemaError(self.path, "It must be an object with at least one key-value pair")

        if len(list(filter(lambda x: type(x) != str or len(x) == 0, self.value.keys()))) > 0:
            raise SchemaError(self.path, "It must be an object, where each key is a non-empty string")

        for key, value in self.value.items():
            if type(value) != dict:
                raise SchemaError(self.path + [key], "It must be an object")
            try:
                re.compile(key)
            except re.error:
                raise SchemaError(self.path, "It must be an object, where each key is a valid regular expression")

    def program(self, path: List[Union[str, int]], value: dict, errors: List[Error]):
        for k, v in value.items():
            if k in self._properties:
                # we should check this field in the 'properties' keyword, so skip it
                continue

            for re_prog, prog in self._programs.values():
                if re_prog(k):
                    prog.run(path + [k], v, errors)
                    break

    def compile(self) -> Union[None, RULE]:
        if "properties" in self.rules:
            self._properties = set(self.rules.keys())
        for k, v in self.value.items():
            # TODO: use cache for checking regular expressions
            self._programs[k] = (re.compile(k).match, self.schema.compile(v, self.path + [k]))
        return self.program

    def to_string(self, depth: int = 0, indent: int = 2):
        programs = "\n".join(p[1].to_string(depth + 1, indent) for p in self._programs.values())
        return f"{' ' * depth*indent}{self.name}:\n{programs}"


class AdditionalProperties(Keyword):
    __slots__ = "_properties", "_program", "_patternProperties"
    name = "additionalProperties"
    type = "object"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._properties = set()
        self._program = None
        self._patternProperties = []

    def validate(self):
        if type(self.value) not in {bool, dict}:
            raise SchemaError(self.path, "It must be a boolean or an object")

    def false_program(self, path: List[Union[str, int]], value: dict, errors: List[Error]):
        for k in value.keys():
            if k in self._properties:
                continue

            for pp_prog in self._patternProperties:
                # TODO: use cache for checking regular expressions
                if pp_prog(k):
                    break
            else:
                errors.append(Error(path + [k], self))

    def program(self, path: List[Union[str, int]], value: dict, errors: List[Error]):
        for k, v in value.items():
            if k in self._properties:
                # we should check this field in the 'properties' keyword, so skip it
                continue

            pp_found = False
            for pp_prog in self._patternProperties:
                # TODO: use cache for checking regular expressions
                if pp_prog(k):
                    pp_found = True
                    break
            if pp_found:
                # we should check this field in the 'patternProperties' keyword, so skip it
                continue

            self._program.run(path + [k], v, errors)

    def compile(self) -> Union[None, RULE]:
        if self.value is True:
            return None
        else:
            if "properties" in self.rules:
                self._properties = set(self.rules["properties"].value.keys())

            if "patternProperties" in self.rules:
                for regexp_property in self.rules["patternProperties"].value.keys():
                    self._patternProperties.append(re.compile(regexp_property).match)

            if self.value is False:
                return self.false_program
            else:
                self._program = self.schema.compile(self.value)
                if self._program:
                    return self.program
                else:
                    return None

    def to_string(self, depth: int = 0, indent: int = 2):
        if type(self.value) == bool:
            return super().to_string(depth, indent)
        else:
            return f"{' ' * depth*indent}{self.name}:\n{self._program.to_string(depth + 1, indent)}"


class Required(Keyword):
    name = "required"
    type = "object"

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        elif len(list(filter(lambda x: type(x) != str or len(x) == 0, self.value))) > 0:
            raise SchemaError(self.path, "It must be an array, where each element is a non-empty string")
        elif len(self.value) != len(set(self.value)):
            raise SchemaError(self.path, "It must be an array of strings, where each element is unique")

    def program(self, path: List[Union[str, int]], value: dict, errors: List[Error]):
        for field in self.value:
            if field not in value:
                errors.append(Error(path + [field], self))

    def compile(self) -> Union[None, RULE]:
        if self.value:
            return self.program
        else:
            return None


class MinProperties(Keyword):
    name = "minProperties"
    type = "object"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")

    def program(self, path: List[Union[str, int]], value: dict, errors: List[Error]):
        if len(value.keys()) < self.value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        if self.value == 0:
            return None
        else:
            return self.program


class MaxProperties(Keyword):
    name = "maxProperties"
    type = "object"

    def validate(self):
        if type(self.value) == int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")
        elif "minProperties" in self.rules:
            self.rules["minProperties"].validate()
            if self.value < self.rules["minProperties"].value:
                raise SchemaError(self.path, "It must be greater or equal to `minProperties`")

    def program(self, path: List[Union[str, int]], value: dict, errors: List[Error]):
        if len(value.keys()) > self.value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        return self.program


# String
class MinLength(Keyword):
    name = "minLength"
    type = "string"

    def validate(self):
        if type(self.value) == int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")

    def program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        if len(value) < self.value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        if self.value == 0:
            return None
        else:
            return self.program


class MaxLength(Keyword):
    name = "maxLength"
    type = "string"

    def validate(self):
        if type(self.value) == int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")
        elif "minLength" in self.rules:
            self.rules["minLength"].validate()
            if self.value < self.rules["minLength"].value:
                raise SchemaError(self.path, "It must be greater or equal to `minLength`")

    def program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        if len(value) > self.value:
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        return self.program


class Pattern(Keyword):
    __slots__ = "_prog"
    name = "pattern"
    type = "string"

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self._prog = None

    def validate(self):
        try:
            re.compile(self.value)
        except re.error:
            raise SchemaError(self.path, "Invalid regular expression")

    def program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        if not self._prog.match(value):
            errors.append(Error(path, self))

    def compile(self) -> Union[None, RULE]:
        self._prog = re.compile(self.value)
        return self.program


class Format(Keyword):
    name = "format"
    type = "string"
    _prog_datetime = re.compile(r"^\d{4}-[01]\d-[0-3]\d(t|T)[0-2]\d:[0-5]\d:[0-5]\d(?:\.\d+)?(?:[+-][0-2]\d:[0-5]\d|[+-][0-2]\d[0-5]\d|z|Z)\Z")
    _prog_bad_email_name = re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9._+-])+|([._\-+]{2,})|([^a-zA-Z0-9]$){1}")
    _prog_bad_email_domain = re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9.-]+)|([.-]{2,})|([a-zA-Z0-9-]){65,}|([^a-zA-Z0-9.]$){1}")
    _prog_bad_hostname = re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9.-]+)|([.-]{2,})|([a-zA-Z0-9-]){65,}|([^a-zA-Z0-9.]$){1}")
    _prog_bad_uri_scheme = re.compile(r"(^[^a-zA-Z]){1}|([^a-zA-Z0-9.+-])+")

    def __init__(self, value: JSON, schema: Schema, path: List[Union[str, int]], rules: Dict[str, Keyword]):
        super().__init__(value, schema, path, rules)
        self.valid_formats = {
            "date-time": self._datetime_program,
            "email": self._email_program,
            "hostname": self._hostname_program,
            "ipv4": self._ipv4_program,
            "ipv6": self._ipv6_program,
            "uri": self._uri_program
        }

    def validate(self):
        if self.value not in self.valid_formats:
            raise SchemaError(self.path, f"Invalid format: {self.value}")

    def _datetime_program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        if not self._prog_datetime.match(value):
            errors.append(Error(path, self))

    def _email_program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        try:
            name, domain = value.split("@", 1)
        except ValueError:
            errors.append(Error(path, self))
            return

        if not name or not domain or self._prog_bad_email_name.match(name) or self._prog_bad_email_domain.match(domain):
            errors.append(Error(path, self))

    def _hostname_program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        if not value or self._prog_bad_hostname.match(value):
            errors.append(Error(path, self))

    def _ipv4_program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        parts = value.split(".")

        if len(parts) != 4:
            errors.append(Error(path, self))
            return

        for part in parts:
            try:
                if (part[0] == "0" and len(part) > 1) or not (-1 < int(part) < 256):
                    errors.append(Error(path, self))
                    return
            except ValueError:
                errors.append(Error(path, self))

    def _ipv6_program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        parts = value.split(":")

        if len(parts) > 8:
            errors.append(Error(path, self))
            return

        empty_parts = 0
        for part in parts:
            if not part:
                empty_parts += 1
                continue
            try:
                if (len(part) > 1 and part[0] == "0") or not (-1 < int(part, 16) < 65536):
                    errors.append(Error(path, self))
                    return
            except ValueError:
                errors.append(Error(path, self))
                return

        if empty_parts > 3 or empty_parts > 1 and len(parts) > 4:
            errors.append(Error(path, self))

    def _uri_program(self, path: List[Union[str, int]], value: str, errors: List[Error]):
        try:
            scheme, hier_part = value.split(":", 1)
        except ValueError:
            errors.append(Error(path, self))
            return

        if not scheme or not hier_part or self._prog_bad_uri_scheme.match(scheme):
            errors.append(Error(path, self))
            return

        # Authority part
        if hier_part.startswith("//"):
            pass

    def compile(self) -> Union[None, RULE]:
        return self.valid_formats[self.value]
