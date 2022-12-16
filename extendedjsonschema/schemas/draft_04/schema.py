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
    Dependencies,
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
from extendedjsonschema.utils import JSON, PATH

logger = logging.getLogger(__name__)


class Schema(BaseSchema):
    def __init__(self):
        super().__init__()
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
            Dependencies.name: Dependencies,
            # String
            MinLength.name: MinLength,
            MaxLength.name: MaxLength,
            Format.name: Format,
            Pattern.name: Pattern
        }
        self.type_keyword = Type

    @staticmethod
    def is_schema(value: JSON):
        return isinstance(value, dict)

    def _type_definition(self, keywords: Dict[str, Keyword]) -> Set:
        if "type" in keywords:
            if type(keywords["type"].value) != list:
                return {keywords["type"].value}
            else:
                return set(keywords["type"].value)
        else:
            return set()

    def _delete_unused_keywords(self, keywords: Dict[str, Keyword], path: List[Union[str, int]]):
        type_definition = self._type_definition(keywords)
        if type_definition:
            for key in list(keywords.keys()):
                rule = keywords[key]
                if rule.type:
                    types = set(rule.type) if type(rule.type) == tuple else {rule.type}
                    if not types & type_definition:
                        logger.warning(f"`{'.'.join((str(p) for p in path + [rule.name]))}` keyword will never be used")
                        del keywords[key]

    def _program(self, keywords: Dict[str, Keyword], field: str) -> Program:
        type_definition = self._type_definition(keywords)
        general_rules: List[Keyword] = []
        type_specific_rules: Dict[type: List[Keyword]] = defaultdict(list)
        for keyword in keywords.values():
            if not keyword.type:
                general_rules.append(keyword)
            else:
                for t in (keyword.type if type(keyword.type) == tuple else [keyword.type]):
                    if not type_definition or t in type_definition:
                        type_specific_rules[self.type_keyword.valid_types[t]].append(keyword)

        return Program(self, general_rules, type_specific_rules, field)

    def program(self, schema: dict, path: PATH = None) -> Program:
        if not self.is_schema(schema):
            raise SchemaError([], "Invalid JSON Schema")

        if schema == {}:
            return Program(self)

        path = path or []

        keywords: Dict[str, Keyword] = {}
        for key, value in schema.items():
            if key in self.keywords:
                keywords[key] = self.keywords[key](value, self, path + [key], keywords)

        for keyword in keywords.values():
            keyword.validate()

        self._delete_unused_keywords(keywords, path)

        return self._program(keywords, path[-1] if path else "")
