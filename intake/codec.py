import json
import re
from decimal import Decimal
from fractions import Fraction


class PackageFormatError(ValueError):
    pass


_INTEGER = re.compile(r'(?:0|-?[1-9][0-9]*)')


def encode_fraction(value: Fraction) -> list[str]:
    if not isinstance(value, Fraction):
        raise PackageFormatError('a probability must be a Fraction')
    return [str(Decimal(value.numerator)), str(Decimal(value.denominator))]


def decode_fraction(value: object) -> Fraction:
    if not isinstance(value, list) or len(value) != 2:
        raise PackageFormatError('a fraction must contain two integer strings')
    numerator, denominator = value
    if any(not isinstance(part, str) or _INTEGER.fullmatch(part) is None for part in value):
        raise PackageFormatError('invalid integer string in fraction')
    n = int(Decimal(numerator))
    d = int(Decimal(denominator))
    if d <= 0:
        raise PackageFormatError('a fraction must have a positive denominator')
    reduced = Fraction(n, d)
    if (reduced.numerator, reduced.denominator) != (n, d):
        raise PackageFormatError('a fraction must be in lowest terms')
    return reduced


def encode_body(body: dict) -> bytes:
    if not isinstance(body, dict):
        raise PackageFormatError('package body must be an object')
    try:
        return json.dumps(body, ensure_ascii=True, allow_nan=False, sort_keys=True,
                          separators=(',', ':')).encode('ascii')
    except (TypeError, ValueError, RecursionError) as exc:
        raise PackageFormatError('package body cannot be encoded') from exc


def decode_body(data: bytes) -> dict:
    if not isinstance(data, bytes):
        raise PackageFormatError('package body must be bytes')
    try:
        body = json.loads(data)
    except (ValueError, RecursionError) as exc:
        raise PackageFormatError('package body is not valid JSON') from exc
    if encode_body(body) != data:
        raise PackageFormatError('package body is not canonically encoded')
    return body
