from typing import Callable

from extendedjsonschema.errors import SchemaError
from extendedjsonschema.schema import Schema
from extendedjsonschema.schemas.draft_04.schema import Schema as SchemaDraft04


class Validator:
    def __init__(self, schema_definition: dict):
        self._schemas = {
            "http://json-schema.org/schema#": SchemaDraft04,
            "http://json-schema.org/draft-04/schema#": SchemaDraft04
        }
        schema = self._schema(schema_definition.get("$schema", "http://json-schema.org/draft-04/schema#"))
        program = schema.program(schema_definition)
        self.source_code = program.compile(False)
        self.run = self._function()

    def _schema(self, dialect: str) -> Schema:
        try:
            return self._schemas[dialect]()
        except KeyError:
            raise SchemaError(["$schema"], f"Invalid dialect (a version of JSON Schema): {dialect}")

    def _function(self) -> Callable:
        state = {}
        exec(self.source_code, state)
        return state["program"]

    def __repr__(self):
        return self.source_code
