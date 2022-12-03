from typing import Type

from extendedjsonschema.compiler import Compiler
from extendedjsonschema.errors import SchemaError
from extendedjsonschema.schema import Schema
from extendedjsonschema.schemas.draft_04.schema import Schema as SchemaDraft04


class Validator:
    def __init__(self, schema_definition: dict):
        self.schemas = {
            "http://json-schema.org/schema#": SchemaDraft04,
            "http://json-schema.org/draft-04/schema#": SchemaDraft04
        }
        schema_cls = self._schema(schema_definition.get("$schema", "http://json-schema.org/draft-04/schema#"))
        compiler = Compiler(schema_cls().compile(schema_definition))

        self._code, self.run = compiler.run()

    def _schema(self, dialect: str) -> Type[Schema]:
        try:
            return self.schemas[dialect]
        except KeyError:
            raise SchemaError(["$schema"], f"Invalid dialect (a version of JSON Schema): {dialect}")

    def __repr__(self):
        return self._code
