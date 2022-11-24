from collections import defaultdict
from typing import Optional

from extendedjsonschema.compiler import Compiler
from extendedjsonschema.errors import SchemaError, ValidationError
from extendedjsonschema.schemas.draft_04.compiler import Compiler as CompilerDraft04
from extendedjsonschema.utils import JSON


class Validator:
    def __init__(self, schema: dict, compiler: Optional[Compiler] = None):
        self.schema = schema
        self.compilers = {
            "http://json-schema.org/schema#": CompilerDraft04,
            "http://json-schema.org/draft-04/schema#": CompilerDraft04
        }
        if not compiler:
            compiler = self._compiler(schema.get("$schema", "http://json-schema.org/draft-04/schema#"))

        self._program = compiler.run(schema)

    def _compiler(self, dialect: str) -> Compiler:
        try:
            return self.compilers[dialect]()
        except KeyError:
            raise SchemaError(["$schema"], f"Invalid dialect (a version of JSON Schema): {dialect}")

    def __call__(self, data: JSON):
        errors = self._program.run(data)
        if errors:
            e = defaultdict(list)
            for error in errors:
                e[tuple(error.path)].append({"keyword": error.keyword.name, "value": error.keyword.value})
            raise ValidationError([{"path": list(path), "errors": err} for path, err in e.items()])

    def __repr__(self):
        return str(self._program)
