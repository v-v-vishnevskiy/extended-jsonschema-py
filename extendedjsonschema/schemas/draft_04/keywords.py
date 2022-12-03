import re
from typing import List, Union

from extendedjsonschema.errors import SchemaError
from extendedjsonschema.keyword import Keyword
from extendedjsonschema.tools import is_equal, non_unique_items
from extendedjsonschema.utils import ERRORS, JSON, PATH, RULE


# General
class Type(Keyword):
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

    def program(self, path: PATH, value: JSON, errors: ERRORS):
        if type(value) != self.property["compiled_value"]:
            errors.append({"path": path, "keyword": self})

    def program_list(self, path: PATH, value: JSON, errors: ERRORS):
        if type(value) not in self.property["compiled_value"]:
            errors.append({"path": path, "keyword": self})

    def compile(self) -> Union[None, RULE]:
        if type(self.value) == str:
            self.property["compiled_value"] = self.valid_types[self.value]
            return self.program
        else:
            if len(self.value) == 1:
                self.property["compiled_value"] = self.valid_types[self.value[0]]
                return self.program
            else:
                self.property["compiled_value"] = {self.valid_types[t] for t in self.value}
                return self.program_list


class Enum(Keyword):
    name = "enum"

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        elif len(self.value) == 0:
            raise SchemaError(self.path, "It must be an array with at least one element")
        elif non_unique_items(self.value):
            raise SchemaError(self.path, "It must be an array, where each element is unique")
        # TODO: check intersection of `type` and `enum` values

    def program(self, path: PATH, value: JSON, errors: ERRORS):
        for enum_type, enum_value in self.property["enum_compiled"]:
            if is_equal(type(value), enum_type, value, enum_value):
                return
        errors.append({"path": path, "keyword": self})

    def compile(self) -> Union[None, RULE]:
        self.property["enum_compiled"] = []
        for item in self.value:
            self.property["enum_compiled"].append((type(item), item))
        return self.program


# schema composition
class AllOf(Keyword):
    name = "allOf"

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if type(item) != dict:
                raise SchemaError(self.path + [i], "It must be an object")

    def program(self, path: PATH, value: JSON, errors: ERRORS):
        for p in self.property["programs"]:
            p(path, value, errors)

    def compile(self) -> Union[None, RULE]:
        self.property["programs"] = []
        for item in self.value:
            self.property["programs"].append(self.schema.compile(item))
        return self.program


class AnyOf(Keyword):
    name = "anyOf"

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if type(item) != dict:
                raise SchemaError(self.path + [i], "It must be an object")

    def program(self, path: PATH, value: JSON, errors: ERRORS):
        errs = []
        for p in self.property["programs"]:
            e = []
            p(path, value, e)
            if not e:
                return
            else:
                errs.extend(e)
        errors.extend(errs)

    def compile(self) -> Union[None, RULE]:
        self.property["programs"] = []
        for item in self.value:
            self.property["programs"].append(self.schema.compile(item))
        return self.program


class OneOf(Keyword):
    name = "oneOf"

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if type(item) != dict:
                raise SchemaError(self.path + [i], "It must be an object")

    def program(self, path: PATH, value: JSON, errors: ERRORS):
        n_successes = 0
        for p in self.property["programs"]:
            e = []
            p(path, value, e)
            if not e:
                n_successes += 1
        if n_successes != 1:
            errors.append({"path": path, "keyword": self})

    def compile(self) -> Union[None, RULE]:
        self.property["programs"] = []
        for item in self.value:
            self.property["programs"].append(self.schema.compile(item))
        return self.program


class Not(Keyword):
    name = "not"

    def validate(self):
        if type(self.value) != dict:
            raise SchemaError(self.path, "It must be an object")

    def program(self, path: PATH, value: JSON, errors: ERRORS):
        errs = []
        self.property["program"](path, value, errs)
        if not errs:
            errors.append({"path": path, "keyword": self})

    def compile(self) -> Union[None, RULE]:
        self.property["program"] = self.schema.compile(self.value)
        return self.program


# Array
class Items(Keyword):
    name = "items"
    type = "array"

    def validate(self):
        if type(self.value) not in {dict, list}:
            raise SchemaError(self.path, "It must be an object or an array")
        if type(self.value) == list:
            for i, item in enumerate(self.value):
                if type(item) != dict:
                    raise SchemaError(self.path + [i], "It must be an object")

    def program_list(self, path: PATH, value: List[JSON], errors: ERRORS):
        for i, item in enumerate(value):
            self.property["program"](path + [i], item, errors)

    def program_tuple(self, path: PATH, value: List[JSON], errors: ERRORS):
        i = 0
        n = min(self.property["n_programs"], len(value))
        while i < n:
            self.property["programs"][i](path + [i], value[i], errors)
            i += 1

    def compile(self) -> Union[None, RULE]:
        if type(self.value) == dict:
            self.property["program"] = self.schema.compile(self.value)
            return self.program_list
        else:
            self.property["programs"] = [self.schema.compile(item) for item in self.value]
            self.property["n_programs"] = len(self.property["programs"])
            return self.program_tuple


class AdditionalItems(Keyword):
    name = "additionalItems"
    type = "array"

    def validate(self):
        if type(self.value) not in {bool, dict}:
            raise SchemaError(self.path, "It must be a boolean or an object")

    def false_program(self, path: PATH, value: list, errors: ERRORS):
        if len(value) > self.property["items_tuple_programs"]:
            for i in range(self.property["items_tuple_programs"], len(value)):
                errors.append({"path": path + [i], "keyword": self})

    def program(self, path: PATH, value: list, errors: ERRORS):
        if len(value) > self.property["items_tuple_programs"]:
            for i in range(self.property["items_tuple_programs"], len(value)):
                self.property["program"](path + [i], value[i], errors)

    def compile(self) -> Union[None, RULE]:
        self.property["items_tuple_programs"] = 0
        if "items" in self.rules and type(self.rules["items"].value) == list:
            self.property["items_tuple_programs"] = len(self.rules["items"].value)

        if self.value is True:
            return None
        elif self.value is False:
            return self.false_program
        else:
            self.property["program"] = self.schema.compile(self.value)
            if self.property["program"]:
                return self.program
            else:
                return None


class MinItems(Keyword):
    name = "minItems"
    type = "array"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")

    def program(self, path: PATH, value: str, errors: ERRORS):
        if len(value) < self.value:
            errors.append({"path": path, "keyword": self})

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

    def program(self, path: PATH, value: str, errors: ERRORS):
        if len(value) > self.value:
            errors.append({"path": path, "keyword": self})

    def compile(self) -> Union[None, RULE]:
        return self.program


class UniqueItems(Keyword):
    name = "uniqueItems"
    type = "array"

    def validate(self):
        if type(self.value) != bool:
            raise SchemaError(self.path, "It must be a boolean")

    def program(self, path: PATH, value: List[JSON], errors: ERRORS):
        for i in sorted(non_unique_items(value)):
            errors.append({"path": path + [i], "keyword": self})

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

    def program(self, path: PATH, value: Union[int, float], errors: ERRORS):
        if value % self.value != 0:
            errors.append({"path": path, "keyword": self})

    def compile(self) -> Union[None, RULE]:
        return self.program


class Minimum(Keyword):
    name = "minimum"
    type = "integer", "number"

    def validate(self):
        if type(self.value) not in {int, float}:
            raise SchemaError(self.path, "It must be an integer or a number")

    def program_strict(self, path: PATH, value: Union[int, float], errors: ERRORS):
        if value <= self.value:
            return errors.append({"path": path, "keyword": self})

    def program(self, path: PATH, value: Union[int, float], errors: ERRORS):
        if value < self.value:
            errors.append({"path": path, "keyword": self})

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

    def program_strict(self, path: PATH, value: Union[int, float], errors: ERRORS):
        if value >= self.value:
            errors.append({"path": path, "keyword": self})

    def program(self, path: PATH, value: Union[int, float], errors: ERRORS):
        if value > self.value:
            errors.append({"path": path, "keyword": self})

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
    name = "properties"
    type = "object"

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

    def program(self, path: PATH, value: dict, errors: ERRORS):
        keys = set(self.property["programs"].keys())
        for k, v in value.items():
            if k not in keys:
                continue
            self.property["programs"][k](path + [k], v, errors)

    def compile(self) -> Union[None, RULE]:
        self.property["programs"] = {}
        for k, v in self.value.items():
            self.property["programs"][k] = self.schema.compile(v, self.path + [k])
        return self.program


class PatternProperties(Keyword):
    name = "patternProperties"
    type = "object"

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

    def program(self, path: PATH, value: dict, errors: ERRORS):
        for k, v in value.items():
            if k in self.property["properties"]:
                # we should check this field in the 'properties' keyword, so skip it
                continue

            for pattern, prog in self.property["programs"].values():
                if pattern.match(k):
                    prog(path + [k], v, errors)
                    break

    def compile(self) -> Union[None, RULE]:
        self.property["programs"] = {}
        self.property["properties"] = set()
        if "properties" in self.rules:
            self.property["properties"] = set(self.rules.keys())
        for k, v in self.value.items():
            # TODO: use cache for checking regular expressions
            self.property["programs"][k] = (re.compile(k), self.schema.compile(v, self.path + [k]))
        return self.program


class AdditionalProperties(Keyword):
    name = "additionalProperties"
    type = "object"

    def validate(self):
        if type(self.value) not in {bool, dict}:
            raise SchemaError(self.path, "It must be a boolean or an object")

    def false_program(self, path: PATH, value: dict, errors: ERRORS):
        for k in value.keys():
            if k in self.property["properties"]:
                continue

            for pp_prog in self.property["patternProperties"]:
                # TODO: use cache for checking regular expressions
                if pp_prog(k):
                    break
            else:
                errors.append({"path": path + [k], "keyword": self})

    def program(self, path: PATH, value: dict, errors: ERRORS):
        for k, v in value.items():
            if k in self.property["properties"]:
                # we should check this field in the 'properties' keyword, so skip it
                continue

            pp_found = False
            for pattern in self.property["patternProperties"]:
                # TODO: use cache for checking regular expressions
                if pattern.match(k):
                    pp_found = True
                    break
            if pp_found:
                # we should check this field in the 'patternProperties' keyword, so skip it
                continue

            self.property["program"](path + [k], v, errors)

    def compile(self) -> Union[None, RULE]:
        self.property["properties"] = set()
        self.property["patternProperties"] = []

        if self.value is True:
            return None
        else:
            if "properties" in self.rules:
                self.property["properties"] = set(self.rules["properties"].value.keys())

            if "patternProperties" in self.rules:
                for regexp_property in self.rules["patternProperties"].value.keys():
                    self.property["patternProperties"].append(re.compile(regexp_property))

            if self.value is False:
                return self.false_program
            else:
                self.property["program"] = self.schema.compile(self.value)
                if self.property["program"]:
                    return self.program
                else:
                    return None


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

    def program(self, path: PATH, value: dict, errors: ERRORS):
        for field in self.value:
            if field not in value:
                errors.append({"path": path + [field], "keyword": self})

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

    def program(self, path: PATH, value: dict, errors: ERRORS):
        if len(value.keys()) < self.value:
            errors.append({"path": path, "keyword": self})

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

    def program(self, path: PATH, value: dict, errors: ERRORS):
        if len(value.keys()) > self.value:
            errors.append({"path": path, "keyword": self})

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

    def program(self, path: PATH, value: str, errors: ERRORS):
        if len(value) < self.value:
            errors.append({"path": path, "keyword": self})

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

    def program(self, path: PATH, value: str, errors: ERRORS):
        if len(value) > self.value:
            errors.append({"path": path, "keyword": self})

    def compile(self) -> Union[None, RULE]:
        return self.program


class Pattern(Keyword):
    name = "pattern"
    type = "string"

    def validate(self):
        try:
            re.compile(self.value)
        except re.error:
            raise SchemaError(self.path, "Invalid regular expression")

    def program(self, path: PATH, value: str, errors: ERRORS):
        if not self.property["pattern"].match(value):
            errors.append({"path": path, "keyword": self})

    def compile(self) -> Union[None, RULE]:
        self.property["pattern"] = re.compile(self.value)
        return self.program


class Format(Keyword):
    name = "format"
    type = "string"
    valid_formats = {"date-time", "email", "hostname", "ipv4", "ipv6", "uri"}

    def validate(self):
        if self.value not in self.valid_formats:
            raise SchemaError(self.path, f"Invalid format: {self.value}")

    def _datetime_program(self, path: PATH, value: str, errors: ERRORS):
        if not self.property["datetime"].match(value):
            errors.append({"path": path, "keyword": self})

    def _email_program(self, path: PATH, value: str, errors: ERRORS):
        try:
            name, domain = value.split("@", 1)
        except ValueError:
            errors.append({"path": path, "keyword": self})
            return

        if not name or not domain or self.property["bad_email_name"].match(name) or self.property["bad_email_domain"].match(domain):
            errors.append({"path": path, "keyword": self})

    def _hostname_program(self, path: PATH, value: str, errors: ERRORS):
        if not value or self.property["bad_hostname"].match(value):
            errors.append({"path": path, "keyword": self})

    def _ipv4_program(self, path: PATH, value: str, errors: ERRORS):
        parts = value.split(".")

        if len(parts) != 4:
            errors.append({"path": path, "keyword": self})
            return

        for part in parts:
            try:
                if (part[0] == "0" and len(part) > 1) or not (-1 < int(part) < 256):
                    errors.append({"path": path, "keyword": self})
                    return
            except ValueError:
                errors.append({"path": path, "keyword": self})

    def _ipv6_program(self, path: PATH, value: str, errors: ERRORS):
        parts = value.split(":")

        if len(parts) > 8:
            errors.append({"path": path, "keyword": self})
            return

        empty_parts = 0
        for part in parts:
            if not part:
                empty_parts += 1
                continue
            try:
                if (len(part) > 1 and part[0] == "0") or not (-1 < int(part, 16) < 65536):
                    errors.append({"path": path, "keyword": self})
                    return
            except ValueError:
                errors.append({"path": path, "keyword": self})
                return

        if empty_parts > 3 or empty_parts > 1 and len(parts) > 4:
            errors.append({"path": path, "keyword": self})

    def _uri_program(self, path: PATH, value: str, errors: ERRORS):
        try:
            scheme, hier_part = value.split(":", 1)
        except ValueError:
            errors.append({"path": path, "keyword": self})
            return

        if not scheme or not hier_part or self.property["bad_uri_scheme"].match(scheme):
            errors.append({"path": path, "keyword": self})
            return

        # Authority part
        if hier_part.startswith("//"):
            pass

    def compile(self) -> Union[None, RULE]:
        if self.value == "date-time":
            self.property["datetime"] = re.compile(r"^\d{4}-[01]\d-[0-3]\d(t|T)[0-2]\d:[0-5]\d:[0-5]\d(?:\.\d+)?(?:[+-][0-2]\d:[0-5]\d|[+-][0-2]\d[0-5]\d|z|Z)\Z")
            return self._datetime_program
        elif self.value == "email":
            self.property["bad_email_name"] = re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9._+-])+|([._\-+]{2,})|([^a-zA-Z0-9]$){1}")
            self.property["bad_email_domain"] = re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9.-]+)|([.-]{2,})|([a-zA-Z0-9-]){65,}|([^a-zA-Z0-9.]$){1}")
            return self._email_program
        elif self.value == "hostname":
            self.property["bad_hostname"] = re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9.-]+)|([.-]{2,})|([a-zA-Z0-9-]){65,}|([^a-zA-Z0-9.]$){1}")
            return self._hostname_program
        elif self.value == "ipv4":
            return self._ipv4_program
        elif self.value == "ipv6":
            return self._ipv6_program
        elif self.value == "uri":
            self.property["bad_uri_scheme"] = re.compile(r"(^[^a-zA-Z]){1}|([^a-zA-Z0-9.+-])+")
            return self._uri_program
        else:
            SchemaError(self.path, f"Invalid format: {self.value}")
