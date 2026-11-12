"""Decimal-safe money: stored as integer paise in SQLite, handled as Decimal in Python."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from sqlalchemy import BigInteger
from sqlalchemy.types import TypeDecorator

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(value) -> Decimal:
    """Convert int/str/float/Decimal to a 2dp Decimal (floats go through str to avoid binary artefacts)."""
    if isinstance(value, Decimal):
        d = value
    else:
        try:
            d = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid monetary value: {value!r}") from exc
    if not d.is_finite():
        raise ValueError("Monetary value must be finite")
    return d.quantize(CENT, rounding=ROUND_HALF_UP)


def to_float(value) -> float:
    return float(to_decimal(value))


class Money(TypeDecorator):
    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return int(to_decimal(value).scaleb(2))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(int(value)).scaleb(-2).quantize(CENT)
