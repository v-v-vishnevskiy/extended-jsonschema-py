# Extended JSON Schema

Fast [JSON Schema](https://json-schema.org/) validator with additional features.

**Warning**: This packages is early stage in active development. **DO NOT use it in production**.


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