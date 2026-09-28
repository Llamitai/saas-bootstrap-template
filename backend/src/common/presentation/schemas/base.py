"""OpenAPI documentation models for responses rendered by ApiJSONResponse.

Endpoints keep returning ApiJSONResponse, so FastAPI never validates or re-serializes
through these models: they only describe the wire format (camelCase keys, envelope).
"""

import functools
import operator
from types import GenericAlias, UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, create_model
from pydantic.alias_generators import to_camel


class ApiSchema(BaseModel):
    """Documents a camelCase JSON object; fields keep snake_case names in Python."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


@functools.cache
def camel_schema(model: type[BaseModel]) -> type[ApiSchema]:
    """Document `model.model_dump()` as rendered on the wire: every key present, camelCase.

    Used where an endpoint still returns a domain model dump instead of a presenter.
    Nested models are converted recursively and named `<Model>Model`.
    """
    fields: dict[str, Any] = {name: (_camelize(info.annotation), ...) for name, info in model.model_fields.items()}
    return create_model(f"{model.__name__}Model", __base__=ApiSchema, __module__=__name__, **fields)


def _camelize(annotation: Any) -> Any:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return camel_schema(annotation)
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    args = tuple(_camelize(arg) for arg in get_args(annotation))
    if origin in (Union, UnionType):
        return functools.reduce(operator.or_, args)
    if origin is list:
        return GenericAlias(list, args)
    if origin is dict:
        return GenericAlias(dict, args)
    return annotation
