from collections import defaultdict
from typing import Type

from extendedjsonschema.schema import Schema
from extendedjsonschema.errors import SchemaError, ValidationError
from extendedjsonschema.schemas.draft_04.schema import Schema as SchemaDraft04
from extendedjsonschema.utils import JSON


class Validator:
    def __init__(self, schema_definition: dict):
        self.schemas = {
            "http://json-schema.org/schema#": SchemaDraft04,
            "http://json-schema.org/draft-04/schema#": SchemaDraft04
        }
        schema_cls = self._schema(schema_definition.get("$schema", "http://json-schema.org/draft-04/schema#"))

        self._program = schema_cls().compile(schema_definition)

    def _schema(self, dialect: str) -> Type[Schema]:
        try:
            return self.schemas[dialect]
        except KeyError:
            raise SchemaError(["$schema"], f"Invalid dialect (a version of JSON Schema): {dialect}")

    def __call__(self, data: JSON):
        errors = []
        self._program.run([], data, errors)
        if errors:
            # TODO: This is very slow code. Need to improve
            e = defaultdict(list)
            for error in errors:
                e[tuple(error.path)].append({"keyword": error.keyword.name, "value": error.keyword.value})
            raise ValidationError([{"path": list(path), "errors": err} for path, err in e.items()])

    def __repr__(self):
        return str(self._program)
