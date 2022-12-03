from typing import List


class SchemaError(Exception):
    def __init__(self, path: List[str], msg: str):
        super().__init__(f"'{'.'.join(str(p) for p in path)}' - {str(msg)}")
        self.msg = msg
        self.path = path

    def __repr__(self):
        return f"'{'.'.join(str(p) for p in self.path)}' - {str(self.msg)}"


class CompilerError(Exception):
    pass


class ValidationError(Exception):
    def __init__(self, errors):
        """
        errors = [
            {
                "path": List[Union[str, int]],
                "errors": [
                    {
                        "keyword": str
                        "path": List[Union[str, int]],
                        "value": JSON
                    }
                ]
            }
        ]
        """
        self.errors = errors
