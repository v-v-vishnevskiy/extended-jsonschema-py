from typing import Callable, List, Union

ERRORS = List[dict]
JSON = Union[bool, int, float, str, list, dict, None]
PATH = List[Union[str, int]]
RULE = Callable[[JSON], None]
