import string
from typing import Dict, List, Union

from extendedjsonschema.keyword import Keyword
from extendedjsonschema.tools import add_indent, to_python_code


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
                    if self._schema.data_variable.path_has_variables:
                        error = f"errors.append({to_python_code(keyword.error(self._schema.data_variable.path))})"
                    else:
                        if "error" in {v[1] for v in string.Formatter().parse(code)}:
                            self._schema.state.set_error(keyword, keyword.error(self._schema.data_variable.path))
                format_data = {"data": data, "error": error, **self._schema.state.variables(keyword)}
                code = code.format(**format_data).strip()
                result.append(f"# {keyword.name}")
                result.append(code.replace("{", "{{").replace("}", "}}"))
                result.append("")
        return result[0:-1]

    def _body(self, **kwargs) -> str:
        if not self:
            return ""

        error = kwargs.get("error")
        data = self._schema.data_variable.push(kwargs.get("data"), kwargs.get("data_path"))

        result = self._compile_keywords(self._general, data=data, error=error)

        type_specific_result = []
        if_stmt = "if"
        for t, keywords in self._type_specific.items():
            block = self._compile_keywords(keywords, data=data, error=error)
            if block:
                type_specific_result.append(f"{if_stmt} type({data}) == {t.__name__}:")
                type_specific_result.append(add_indent("\n".join(block)))
                if_stmt = "elif"

        self._schema.data_variable.pop()

        if type_specific_result:
            if result:
                result.append("")
            result.extend(type_specific_result)

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
                    "\n".join([
                        "def program(data):",
                        "    errors = []",
                        "",
                        add_indent(fn_body.replace("{{", "{").replace("}}", "}")),
                        "    return errors"
                    ])
                ) if block)
            else:
                return "def program(data):\n    return []"
