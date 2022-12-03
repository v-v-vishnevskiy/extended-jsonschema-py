from typing import Callable, Union

JSON = Union[bool, int, float, str, list, dict, None]


RULE = Callable[[JSON], None]
