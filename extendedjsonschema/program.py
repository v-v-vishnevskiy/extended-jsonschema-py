from typing import Dict, List, Union

from extendedjsonschema.keyword import Keyword
from extendedjsonschema.tools import add_indent


class Program:
    def __init__(self,
        schema: "Schema",
        general: List[Keyword] = None,
        type_specific: Dict[type, List[Keyword]] = None,
        field: str = ""
    ):
        self._schema = schema
        self.field = field
        self._general = general or []
        self._type_specific = type_specific or {}

    def __bool__(self) -> bool:
        return bool(self._general) or bool(self._type_specific)

    def _compile_keywords(self, keywords: List[Keyword], data: str, error: Union[str, None]) -> List[str]:
        result = []
        for keyword in keywords:
            code = keyword.compile()
            if code:
                if not error:
                    self._schema.state.set_error(
                        keyword,
                        {"keyword": keyword.name, "value": keyword.value}
                    )
                format_data = {"data": data, "error": error, **self._schema.state.variables(keyword)}
                code = code.format(**format_data).strip()
                result.append(f"# {keyword.name}")
                result.append(f"{code}\n")
        return result

    def _body(self, **kwargs) -> str:
        if not self:
            return ""

        error = kwargs.get("error")
        data = self._schema.data_variable.push(kwargs.get("data", "data"), kwargs.get("data_slice"))

        result = self._compile_keywords(self._general, data=data, error=error)

        if_stmt = "if"
        for t, keywords in self._type_specific.items():
            block = self._compile_keywords(keywords, data=data, error=error)
            if block:
                result.append(f"{if_stmt} type({data}) == {t.__name__}:")
                result.append(add_indent("\n".join(block)))
                if_stmt = "elif"

        self._schema.data_variable.pop()

        return "\n".join(result)

    def compile(self, body_only: bool = True, **kwargs) -> str:
        fn_body = self._body(**kwargs)
        if body_only:
            return fn_body
        else:
            if fn_body:
                return "\n\n\n".join(block for block in (
                    self._schema.imports.compile_all(),
                    self._schema.state.compile_all(),
                    "NoneType = type(None)",
                    "\n".join([
                        "def program(data):",
                        "    errors = []",
                        add_indent(fn_body),
                        "    return errors"
                    ])
                ) if block)
            else:
                return "def program(data):\n    return []"
