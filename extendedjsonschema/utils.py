from dataclasses import dataclass
from typing import Callable, List, Union

JSON = Union[bool, int, float, str, list, dict, None]


@dataclass
class Error:
    path: List[Union[str, int]]
    keyword: "Keyword"


RULE = Callable[[JSON], List[Error]]
