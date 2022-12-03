from extendedjsonschema.program import Program
from extendedjsonschema.utils import PATH


class Schema:
    def compile(self, schema: dict, path: PATH = None) -> Program:
        raise NotImplementedError("Please implement this method")
