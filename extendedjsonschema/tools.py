from typing import Union


gen = {list: lambda data: enumerate(data), dict: lambda data: data.items()}


def is_equal(t1, t2, data1: Union[list, dict], data2: Union[list, dict]) -> bool:
    if t1 != t2:
        return False

    if t1 not in {list, dict}:
        if data1 != data2:
            return False
    else:
        if t1 == list:
            if len(data1) != len(data2):
                return False
        else:  # dict
            if set(data1.keys()) != set(data2.keys()):
                return False

        for i, item1 in gen[t1](data1):
            if not is_equal(type(item1), type(data2[i]), item1, data2[i]):
                return False
    return True


def non_unique_items(value: list) -> set:
    result = set()
    n = len(value)
    m = n - 1
    if n > 1:
        i = 0
        while i < m:
            type_i = type(value[i])
            j = i + 1
            while j < n:
                if j not in result:
                    if is_equal(type_i, type(value[j]), value[i], value[j]):
                        result.add(j)
                j += 1
            i += 1
    return result
