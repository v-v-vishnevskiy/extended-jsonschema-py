from typing import List, Union

from extendedjsonschema.program import Program


class Schema:
    def compile(self, schema: dict, path: List[Union[str, int]] = None) -> Program:
        raise NotImplementedError("Please implement this method")
