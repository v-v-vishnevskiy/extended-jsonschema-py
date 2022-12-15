from extendedjsonschema.utils import PATH


class Error(Exception):
    pass


class SchemaError(Error):
    def __init__(self, path: PATH, msg: str):
        super().__init__(f"'{'.'.join(str(p) for p in path)}' - {str(msg)}")
        self.msg = msg
        self.path = path

    def __repr__(self):
        return f"'{'.'.join(str(p) for p in self.path)}' - {str(self.msg)}"


class CompilerError(Error):
    pass


class OptimizerError(Error):
    pass
