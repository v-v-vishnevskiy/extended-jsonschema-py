import logging
import re
from typing import List

from extendedjsonschema.errors import SchemaError
from extendedjsonschema.keyword import Keyword
from extendedjsonschema.tools import add_indent, non_unique_items


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

    def code(self, t) -> str:
        return f"""
if type({{data}}) != {t}:
    {{error}}
"""

    def code_list(self) -> str:
        return f"""
if type({{data}}) not in {{value}}:
    {{error}}
"""

    def compile(self) -> str:
        if type(self.value) == str:
            return self.code(self.valid_types[self.value].__name__)
        else:
            if len(self.value) == 1:
                return self.code(self.valid_types[self.value[0]].__name__)
            else:
                self.set_variable("value", {self.valid_types[t] for t in self.value})
                return self.code_list()


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

    def compile(self) -> str:
        self.import_module("extendedjsonschema.tools", "is_equal")
        self.set_variable("value", [(type(item), item) for item in self.value])
        enum_type = f"enum_type_{id(self)}"
        enum_data = f"enum_data_{id(self)}"
        return f"""
for {enum_type}, {enum_data} in {{value}}:
    if is_equal(type({{data}}), {enum_type}, {{data}}, {enum_data}):
        break
else:
    {{error}}
"""


# schema composition
class AllOf(Keyword):
    name = "allOf"

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if not self.schema.is_schema(item):
                raise SchemaError(self.path + [i], "It must be a JSON Schema object")

    def compile(self) -> str:
        programs = []
        for i, schema in enumerate(self.value):
            code = self.schema.program(schema, self.path + [i]).compile()
            if code:
                programs.append(code)
            else:
                logging.warning(f"Validation against subschema '{self.path + [i]}' is always true")
        return "\n".join(programs)


class AnyOf(Keyword):
    name = "anyOf"

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if not self.schema.is_schema(item):
                raise SchemaError(self.path + [i], "It must be a JSON Schema object")

    def compile(self) -> str:
        programs = []
        result = []
        has_errors = f"has_errors_{id(self)}"

        for i, schema in enumerate(self.value):
            code = self.schema.program(schema, self.path + [i]).compile(error=f"{has_errors} = True")
            if not code:
                logging.warning(f"Validation against subschema '{self.path + [i]}' is always true")
                return ""
            programs.append(code)

        j = 0
        for i, code in enumerate(programs):
            result.append(add_indent(f"# {i}", j))
            result.append(add_indent(f"{has_errors} = False", j))
            result.append(add_indent(code, j))
            result.append(add_indent(f"if {has_errors}:", j))
            j += 1
        if result:
            result.append(add_indent("{error}", j))

        return "\n".join(result)


class OneOf(Keyword):
    name = "oneOf"

    def validate(self):
        if type(self.value) != list:
            raise SchemaError(self.path, "It must be an array")
        for i, item in enumerate(self.value):
            if not self.schema.is_schema(item):
                raise SchemaError(self.path + [i], "It must be a JSON Schema object")

    def compile(self) -> str:
        programs = []
        n_successes = f"n_successes_{id(self)}"
        success = f"success_{id(self)}"

        for i, schema in enumerate(self.value):
            code = self.schema.program(schema, self.path + [i]).compile(error=f"{success} = 0")
            programs.append(code)
            if not code:
                logging.warning(f"Validation against subschema '{self.path + [i]}' is always true")

        result = [f"{n_successes} = 0"]
        for i, code in enumerate(programs):
            if i > 0:
                result.append(add_indent(f"if {n_successes} < 2:", i - 1))
            result.append(add_indent(f"# {i}", i))
            result.append(add_indent(f"{success} = 1", i))
            result.append(add_indent(code, i))
        if result:
            result.append(f"if {n_successes} != 1:")
            result.append(add_indent("{error}"))

        return "\n".join(result)


class Not(Keyword):
    name = "not"

    def validate(self):
        if not self.schema.is_schema(self.value):
            raise SchemaError(self.path, "It must be a JSON Schema object")

    def compile(self) -> str:
        success = f"success_{id(self)}"
        code = self.schema.program(self.value).compile(error=f"{success} = False")
        if not code:
            logging.warning(f"Validation against subschema '{self.path}' is always true")
            return "{error}"
        else:
            return "\n".join([
                f"{success} = True",
                code,
                f"if {success} is True:",
                add_indent("{error}")
            ])


# Array
class Items(Keyword):
    name = "items"
    type = "array"

    def validate(self):
        if not self.schema.is_schema(self.value) or type(self.value) != list:
            raise SchemaError(self.path, "It must be a JSON Schema object or an array")
        if type(self.value) == list:
            for i, item in enumerate(self.value):
                if not self.schema.is_schema(item):
                    raise SchemaError(self.path + [i], "It must be a JSON Schema object")

    def code_list(self, program) -> str:
        data = f"data_{id(self)}"
        code = program.compile(data=data)
        if code:
            return f"""
for i_{id(self)}, {data} in enumerate({{data}}):
{add_indent(code)}
"""
        else:
            return ""

    def code_tuple(self, programs: list) -> str:
        data_len = f"data_len_{id(self)}"
        result = [f"{data_len} = len({{data}})"]
        for i, p in enumerate(programs):
            code = p.compile(data_slice=i)
            if code:
                result.append(f"if {data_len} > {i}:")
                result.append(add_indent(code))
        return "\n".join(result)

    def compile(self) -> str:
        if type(self.value) == list:
            return self.code_tuple([self.schema.program(item, self.path + [i]) for i, item in enumerate(self.value)])
        else:
            return self.code_list(self.schema.program(self.value))


class AdditionalItems(Keyword):
    name = "additionalItems"
    type = "array"

    def validate(self):
        if not self.schema.is_schema(self.value) or type(self.value) != bool:
            raise SchemaError(self.path, "It must be a boolean or a JSON Schema object")

    def code_false(self, items_tuple_programs: int) -> str:
        return f"""
if len({{data}}) > {items_tuple_programs}:
    for i_{id(self)} in range({items_tuple_programs}, len({{data}})):
        {{error}}
"""

    def code(self, items_tuple_programs: int, program) -> str:
        data_slice = f"i_{id(self)}"
        code = program.compile(data_slice=data_slice)
        if code:
            return f"""
if len({{data}}) > {items_tuple_programs}:
    for {data_slice} in range({items_tuple_programs}, len({{data}})):
{add_indent(code, 2)}
"""
        else:
            return ""

    def compile(self) -> str:
        items_tuple_programs = 0
        if "items" in self.rules:
            if type(self.rules["items"].value) == dict:
                return ""
            elif type(self.rules["items"].value) == list:
                items_tuple_programs = len(self.rules["items"].value)

        if self.value is True:
            return ""
        elif self.value is False:
            return self.code_false(items_tuple_programs)
        else:
            program = self.schema.program(self.value)
            return self.code(items_tuple_programs, program)


class MinItems(Keyword):
    name = "minItems"
    type = "array"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")

    def compile(self) -> str:
        return f"""
if len({{data}}) < {self.value}:
    {{error}}
"""


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

    def compile(self) -> str:
        return f"""
if len({{data}}) > {self.value}:
    {{error}}
"""


class UniqueItems(Keyword):
    name = "uniqueItems"
    type = "array"

    def validate(self):
        if type(self.value) != bool:
            raise SchemaError(self.path, "It must be a boolean")

    def compile(self) -> str:
        if self.value:
            self.import_module("extendedjsonschema.tools", "non_unique_items")
            return f"""
for i_{id(self)} in sorted(non_unique_items({{data}})):
    {{error}}
"""
        else:
            return ""


# Number and Integer
class MultipleOf(Keyword):
    name = "multipleOf"
    type = "integer", "number"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be strictly greater than 0")

    def compile(self) -> str:
        return f"""
if {{data}} % {self.value} != 0:
    {{error}}
"""


class Minimum(Keyword):
    name = "minimum"
    type = "integer", "number"

    def validate(self):
        if type(self.value) not in {int, float}:
            raise SchemaError(self.path, "It must be an integer or a number")

    def code_strict(self) -> str:
        return f"""
if {{data}} <= {self.value}:
    {{error}}
"""

    def code(self) -> str:
        return f"""
if {{data}} < {self.value}:
    {{error}}
"""

    def compile(self) -> str:
        if "exclusiveMinimum" in self.rules and self.rules["exclusiveMinimum"].value is True:
            return self.code_strict()
        else:
            return self.code()


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

    def code_strict(self) -> str:
        return f"""
if {{data}} >= {self.value}:
    {{error}}
"""

    def code(self) -> str:
        return f"""
if {{data}} > {self.value}:
    {{error}}
"""

    def compile(self) -> str:
        if "exclusiveMaximum" in self.rules and self.rules["exclusiveMaximum"].value is True:
            return self.code_strict()
        else:
            return self.code()


class ExclusiveMinimum(Keyword):
    name = "exclusiveMinimum"
    type = "integer", "number"

    def validate(self):
        if type(self.value) != bool:
            raise SchemaError(self.path, "It must be a boolean")

    def compile(self) -> str:
        return ""


class ExclusiveMaximum(Keyword):
    name = "exclusiveMaximum"
    type = "integer", "number"

    def validate(self):
        if type(self.value) != bool:
            raise SchemaError(self.path, "It must be a boolean")

    def compile(self) -> str:
        return ""


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
                if not self.schema.is_schema(value):
                    raise SchemaError(self.path + [key], "It must be a JSON Schema object")

    def compile(self) -> str:
        programs = {}
        for prop, schema in self.value.items():
            code = self.schema.program(schema, self.path + [prop]).compile(data_slice=prop)
            if code:
                programs[prop] = code

        result = []
        for prop, code in programs.items():
            result.append(f"""if "{prop}" in {{data}}:""")
            result.append(add_indent(code))
        return "\n".join(result)


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
            if not self.schema.is_schema(value):
                raise SchemaError(self.path + [key], "It must be a JSON Schema object")
            try:
                re.compile(key)
            except re.error:
                raise SchemaError(self.path, "It must be an object, where each key is a valid regular expression")

    def code(self, codes: List[str]) -> str:
        prop = f"prop_{id(self)}"
        data = f"data_{id(self)}"

        result = [f"for {prop}, {data} in {{data}}.items():"]
        for i, code in enumerate(codes):
            result.append(add_indent(f"if {{pattern_{i}}}.match({prop}):", 1))
            result.append(add_indent(code, 2))

        return "\n".join(result)

    def code_with_properties(self, codes: List[str]) -> str:
        prop = f"prop_{id(self)}"
        data = f"data_{id(self)}"

        result = [f"for {prop}, {data} in {{data}}.items():"]
        for i, code in enumerate(codes):
            result.append(add_indent(f"if {prop} not in {{properties}}:"))
            result.append(add_indent(f"if {{pattern_{i}}}.match({prop}):", 2))
            result.append(add_indent(code, 3))

        return "\n".join(result)

    def compile(self) -> str:
        self.import_package("re")

        programs = []
        for i, pattern in enumerate(self.value.keys()):
            self.set_variable(f"pattern_{i}", re.compile(pattern))
            program = self.schema.program(self.value[pattern], self.path + [pattern])
            programs.append(program.compile(data=f"data_{id(self)}"))

        if "properties" in self.rules:
            self.set_variable("properties", set(self.rules["properties"].value.keys()))
            return self.code_with_properties(programs)
        else:
            return self.code(programs)


class AdditionalProperties(Keyword):
    name = "additionalProperties"
    type = "object"

    def validate(self):
        if type(self.value) not in {bool, dict}:
            raise SchemaError(self.path, "It must be a boolean or a JSON Schema object")

    def code_false(self) -> str:
        return f"""
for prop_{id(self)} in {{data}}.keys():
    if prop_{id(self)} in {{properties}}:
        continue

    for pp_{id(self)} in {{pattern_properties}}:
        if pp_{id(self)}.match(prop_{id(self)}):
            break
    else:
        {{error}}
"""

    def code(self, code: str) -> str:
        return f"""
for prop_{id(self)}, data_{id(self)} in {{data}}.items():
{add_indent(code)}
"""

    def code_with_properties(self, code: str) -> str:
        return f"""
for prop_{id(self)}, data_{id(self)} in {{data}}.items():
    if prop_{id(self)} not in {{properties}}:
{add_indent(code, 2)}
"""

    def code_with_pp(self, code: str) -> str:
        return f"""
for prop_{id(self)}, data_{id(self)} in {{data}}.items():
    for pattern_{id(self)} in {{pattern_properties}}:
        if pattern_{id(self)}.match(prop_{id(self)}):
            break
    else:
{add_indent(code, 2)}
"""

    def code_with_properties_and_pp(self, code: str) -> str:
        return f"""
for prop_{id(self)}, data_{id(self)} in {{data}}.items():
    if prop_{id(self)} not in {{properties}}:
        for pattern_{id(self)} in {{pattern_properties}}:
            if pattern_{id(self)}.match(prop_{id(self)}):
                break
        else:
{add_indent(code, 3)}
"""

    def compile(self) -> str:
        properties = set()
        pattern_properties = []

        if self.value is True:
            return ""
        else:
            if "properties" in self.rules:
                properties = set(self.rules["properties"].value.keys())

            if "patternProperties" in self.rules:
                for regexp_property in self.rules["patternProperties"].value.keys():
                    pattern_properties.append(re.compile(regexp_property))

            if self.value is False:
                self.set_variable("properties", properties)
                self.set_variable("pattern_properties", pattern_properties)
                return self.code_false()
            else:
                code = self.schema.program(self.value).compile(data=f"data_{id(self)}")
                if not code:
                    return ""

            if properties and pattern_properties:
                self.set_variable("properties", properties)
                self.set_variable("pattern_properties", pattern_properties)
                return self.code_with_properties_and_pp(code)
            elif properties:
                self.set_variable("properties", properties)
                return self.code_with_properties(code)
            elif pattern_properties:
                self.set_variable("pattern_properties", pattern_properties)
                return self.code_with_pp(code)
            else:
                return self.code(code)


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

    def compile(self) -> str:
        if self.value:
            self.set_variable("value", self.value)
            return f"""
for field_{id(self)} in {{value}}:
    if field_{id(self)} not in {{data}}:
        {{error}}
"""
        else:
            return ""


class MinProperties(Keyword):
    name = "minProperties"
    type = "object"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")

    def compile(self) -> str:
        if self.value == 0:
            return ""
        else:
            return f"""
if len({{data}}.keys()) < {self.value}:
    {{error}}
"""


class MaxProperties(Keyword):
    name = "maxProperties"
    type = "object"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")
        elif "minProperties" in self.rules:
            self.rules["minProperties"].validate()
            if self.value < self.rules["minProperties"].value:
                raise SchemaError(self.path, "It must be greater or equal to `minProperties`")

    def compile(self) -> str:
        return f"""
if len({{data}}.keys()) > {self.value}:
    {{error}}
"""


# String
class MinLength(Keyword):
    name = "minLength"
    type = "string"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")

    def compile(self) -> str:
        if self.value == 0:
            return ""
        else:
            return f"""
if len({{data}}) < {self.value}:
    {{error}}
"""


class MaxLength(Keyword):
    name = "maxLength"
    type = "string"

    def validate(self):
        if type(self.value) != int:
            raise SchemaError(self.path, "It must be an integer")
        elif self.value < 0:
            raise SchemaError(self.path, "It must be a non-negative integer")
        elif "minLength" in self.rules:
            self.rules["minLength"].validate()
            if self.value < self.rules["minLength"].value:
                raise SchemaError(self.path, "It must be greater or equal to `minLength`")

    def code(self) -> str:
        return f"""
if len(value) > {self.value}:
    {{error}}
"""

    def compile(self) -> str:
        return self.code()


class Pattern(Keyword):
    name = "pattern"
    type = "string"

    def validate(self):
        try:
            re.compile(self.value)
        except re.error:
            raise SchemaError(self.path, "Invalid regular expression")

    def compile(self) -> str:
        self.import_package("re")
        self.set_variable("pattern", re.compile(self.value))
        return f"""
if not {{pattern}}.match({{data}}):
    {{error}}
"""


class Format(Keyword):
    name = "format"
    type = "string"
    valid_formats = {"date-time", "email", "hostname", "ipv4", "ipv6", "uri"}

    def validate(self):
        if self.value not in self.valid_formats:
            raise SchemaError(self.path, f"Invalid format: {self.value}")

    def _code_datetime(self) -> str:
        return """
if not {datetime}.match({value}):
    {error}
"""

    def _code_email(self) -> str:
        name = f"name_{id(self)}"
        domain = f"domain_{id(self)}"
        return f"""
try:
    {name}, {domain} = {{value}}.split("@", 1)
    if not {name} or not {domain} or {{bad_email_name}}.match({name}) or {{bad_email_domain}}.match({domain}):
        {{error}}
except ValueError:
    {{error}}
"""

    def _code_hostname(self) -> str:
        return """
if not {value} or {bad_hostname}.match({value}):
    {error}
"""

    def _code_ipv4(self) -> str:
        parts = f"parts_{id(self)}"
        part = f"part_{id(self)}"
        return f"""
{parts} = {{value}}.split(".")

if len({parts}) == 4:
    for {part} in {parts}:
        try:
            if len({part}) == 0 or ({part}[0] == "0" and len({part}) > 1) or not (-1 < int({part}) < 256):
                {{error}}
                break
        except ValueError:
            {{error}}
            break
else:
    {{error}}
"""

    def _code_ipv6(self) -> str:
        parts = f"parts_{id(self)}"
        part = f"part_{id(self)}"
        empty_parts = f"empty_parts_{id(self)}"
        return f"""
{parts} = {{value}}.split(":")

if len({parts}) < 9:
    {empty_parts} = 0
    for {part} in {parts}:
        if not {part}:
            {empty_parts} += 1
            continue
        try:
            if (len({part}) > 1 and {part}[0] == "0") or not (-1 < int({part}, 16) < 65536):
                {{error}}
                break
        except ValueError:
            {{error}}
            break

    if {empty_parts} > 3 or {empty_parts} > 1 and len({parts}) > 4:
        {{error}}
else:
    {{error}}
"""

    def _code_uri(self) -> str:
        scheme = f"scheme_{id(self)}"
        hier_part = f"hier_part_{id(self)}"
        return f"""
try:
    {scheme}, {hier_part} = {{value}}.split(":", 1)
    if {scheme} and {hier_part} and not {{bad_uri_scheme}}.match({scheme}):
        # Authority part
        if {hier_part}.startswith("//"):
            pass
        else:
            {{error}}
    else:
        {{error}}
except ValueError:
    {{error}}
"""

    def compile(self) -> str:
        if self.value == "date-time":
            self.import_package("re")
            self.set_variable(
                "datetime",
                re.compile(r"^\d{4}-[01]\d-[0-3]\d(t|T)[0-2]\d:[0-5]\d:[0-5]\d(?:\.\d+)?(?:[+-][0-2]\d:[0-5]\d|[+-][0-2]\d[0-5]\d|z|Z)\Z")
            )
            return self._code_datetime()
        elif self.value == "email":
            self.import_package("re")
            self.set_variable(
                "bad_email_name",
                re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9._+-])+|([._\-+]{2,})|([^a-zA-Z0-9]$){1}")
            )
            self.set_variable(
                "bad_email_domain",
                re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9.-]+)|([.-]{2,})|([a-zA-Z0-9-]){65,}|([^a-zA-Z0-9.]$){1}")
            )
            return self._code_email()
        elif self.value == "hostname":
            self.import_package("re")
            self.set_variable(
                "bad_hostname",
                re.compile(r"(^[^a-zA-Z0-9]){1}|([^a-zA-Z0-9.-]+)|([.-]{2,})|([a-zA-Z0-9-]){65,}|([^a-zA-Z0-9.]$){1}")
            )
            return self._code_hostname()
        elif self.value == "ipv4":
            return self._code_ipv4()
        elif self.value == "ipv6":
            return self._code_ipv6()
        elif self.value == "uri":
            self.import_package("re")
            self.set_variable("bad_uri_scheme", re.compile(r"(^[^a-zA-Z]){1}|([^a-zA-Z0-9.+-])+"))
            return self._code_uri()
        else:
            SchemaError(self.path, f"Invalid format: {self.value}")
