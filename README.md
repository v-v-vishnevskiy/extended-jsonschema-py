# Extended JSON Schema

A fast [JSON Schema](https://json-schema.org/) validator with extensions.

**Warning**: This packages is early stage in active development. **DO NOT use it in production yet**.


## Features

- No any other programming languages like C/C++ or Rust for speedy execution. Just pure Python and a little Cython magic under the hood.

## Installation
`extended-jsonschema` requires Python 3.7+ and is available on PyPI:
```
$ pip install extended-jsonschema
```

[![Downloads](https://static.pepy.tech/badge/extended-jsonschema)](https://pepy.tech/project/extended-jsonschema)
[![Downloads](https://static.pepy.tech/badge/extended-jsonschema/month)](https://pepy.tech/project/extended-jsonschema)
[![Downloads](https://static.pepy.tech/badge/extended-jsonschema/week)](https://pepy.tech/project/extended-jsonschema)

## Basic Usage
```python
from extendedjsonschema import Validator

validator = Validator({"type": "string"})

errors = validator(3.14)
print(errors)

>>> [{'path': [], 'keyword': 'type', 'value': 'string'}]
```

## License
`extendedjsonschema` is offered under the MIT license.