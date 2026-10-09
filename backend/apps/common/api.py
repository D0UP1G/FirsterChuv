"""Shared API casing and error response conventions."""

import re
from collections.abc import Mapping

from rest_framework.exceptions import ErrorDetail
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from rest_framework.views import exception_handler as drf_exception_handler


def _convert_keys(value, convert):
    if isinstance(value, Mapping):
        return {
            convert(key) if isinstance(key, str) else key: _convert_keys(item, convert)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_convert_keys(item, convert) for item in value]
    if isinstance(value, tuple):
        return [_convert_keys(item, convert) for item in value]
    return value


def _snake_case(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _camel_case(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part[:1].upper() + part[1:] for part in rest)


class CamelCaseJSONParser(JSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        return _convert_keys(super().parse(stream, media_type, parser_context), _snake_case)


class CamelCaseJSONRenderer(JSONRenderer):
    def render(self, data, accepted_media_type=None, renderer_context=None):
        return super().render(_convert_keys(data, _camel_case), accepted_media_type, renderer_context)


def _message_for(detail) -> str:
    if isinstance(detail, Mapping):
        if "detail" in detail:
            return str(detail["detail"])
        first_value = next(iter(detail.values()), None)
        return str(first_value) if first_value is not None else "Request could not be processed."
    if isinstance(detail, list):
        return str(detail[0]) if detail else "Request could not be processed."
    return str(detail)


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    details = response.data
    fields = details if isinstance(details, (dict, list)) and not (isinstance(details, dict) and "detail" in details) else None
    code = getattr(exc, "default_code", "request_error")
    if isinstance(details, ErrorDetail):
        code = details.code
    elif isinstance(details, Mapping) and "detail" in details:
        detail_value = details["detail"]
        code = getattr(detail_value, "code", code)

    request = context.get("request")
    request_id = getattr(request, "request_id", None)
    response.data = {
        "error": {
            "code": str(code),
            "message": _message_for(details),
            "fields": fields,
        },
        "request_id": str(request_id) if request_id else None,
    }
    return response
