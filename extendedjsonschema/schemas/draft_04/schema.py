import logging
from collections import defaultdict
from typing import Dict, List, Set, Type, Union

from extendedjsonschema.schema import Schema as BaseSchema
from extendedjsonschema.schema import Program
from extendedjsonschema.errors import SchemaError
from extendedjsonschema.keyword import Keyword
from extendedjsonschema.schemas.draft_04.keywords import (
    AdditionalItems,
    AdditionalProperties,
    AllOf,
    AnyOf,
    Enum,
    ExclusiveMaximum,
    ExclusiveMinimum,
    Format,
    Items,
    Maximum,
    MaxItems,
    MaxLength,
    MaxProperties,
    Minimum,
    MinItems,
    MinLength,
    MinProperties,
    MultipleOf,
    Not,
    OneOf,
    Pattern,
    PatternProperties,
    Properties,
    Required,
    Type,
    UniqueItems,
)

logger = logging.getLogger(__name__)


class Schema(BaseSchema):
    def __init__(self):
        self.keywords: Dict[str, Type[Keyword]] = {
            # General
            Enum.name: Enum,
            Type.name: Type,
            # Schema Composition
            AllOf.name: AllOf,
            AnyOf.name: AnyOf,
            OneOf.name: OneOf,
            Not.name: Not,
            # Array
            Items.name: Items,
            AdditionalItems.name: AdditionalItems,
            MinItems.name: MinItems,
            MaxItems.name: MaxItems,
            UniqueItems.name: UniqueItems,
            # Integer, Number
            Minimum.name: Minimum,
            Maximum.name: Maximum,
            MultipleOf.name: MultipleOf,
            ExclusiveMinimum.name: ExclusiveMinimum,
            ExclusiveMaximum.name: ExclusiveMaximum,
            # Object
            Properties.name: Properties,
            PatternProperties.name: PatternProperties,
            AdditionalProperties.name: AdditionalProperties,
            Required.name: Required,
            MinProperties.name: MinProperties,
            MaxProperties.name: MaxProperties,
            # String
            MinLength.name: MinLength,
            MaxLength.name: MaxLength,
            Format.name: Format,
            Pattern.name: Pattern
        }
        self.type_keyword = Type

    def _type_definition(self, rules: Dict[str, Keyword]) -> Set:
        if "type" in rules:
            if type(rules["type"].value) != list:
                return {rules["type"].value}
            else:
                return set(rules["type"].value)
        else:
            return set()

    def _delete_unused_keywords(self, rules: Dict[str, Keyword], path: List[Union[str, int]]):
        type_definition = self._type_definition(rules)
        if type_definition:
            for key in list(rules.keys()):
                rule = rules[key]
                if rule.type:
                    types = set(rule.type) if type(rule.type) == tuple else {rule.type}
                    if not types & type_definition:
                        logger.warning(f"`{'.'.join((str(p) for p in path + [rule.name]))}` keyword will never be used")
                        del rules[key]

    def _compile(self, rules: Dict[str, Keyword], field: str) -> Program:
        type_definition = self._type_definition(rules)
        general_rules = []
        type_specific_rules = defaultdict(list)
        for rule in rules.values():
            program = rule.compile()
            if program:
                if not rule.type:
                    general_rules.append((program, rule))
                else:
                    for t in (rule.type if type(rule.type) == tuple else [rule.type]):
                        if not type_definition or (type_definition and t in type_definition):
                            type_specific_rules[self.type_keyword.valid_types[t]].append((program, rule))

        return Program(general_rules, type_specific_rules, field)

    def compile(self, schema: dict, path: List[Union[str, int]] = None) -> Program:
        if type(schema) != dict:
            raise SchemaError([], "JSON Schema must be an object")

        if schema == {}:
            return Program()

        path = path or []

        rules: Dict[str, Keyword] = {}
        for key, value in schema.items():
            if key in self.keywords:
                rules[key] = self.keywords[key](value, self, path + [key], rules)

        for rule in rules.values():
            rule.validate()

        self._delete_unused_keywords(rules, path)

        return self._compile(rules, path[-1] if path else "")
