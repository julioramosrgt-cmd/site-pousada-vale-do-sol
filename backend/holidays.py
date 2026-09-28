"""Brazilian national holidays (fixed and movable).

Provides `get_brazilian_holidays(year)` returning a set of ISO date strings and
`brazilian_holidays_range(start_year, end_year)` for pre-caching.
Movable holidays are derived from Easter (Gregorian algorithm).
"""
from datetime import date, timedelta
from functools import lru_cache


def _easter_sunday(year: int) -> date:
    """Anonymous Gregorian algorithm for Easter Sunday."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


@lru_cache(maxsize=32)
def get_brazilian_holidays(year: int) -> dict:
    """Return {ISO date string: holiday name} for the given year."""
    easter = _easter_sunday(year)
    holidays: dict[str, str] = {
        f"{year}-01-01": "Confraternização Universal",
        f"{year}-04-21": "Tiradentes",
        f"{year}-05-01": "Dia do Trabalho",
        f"{year}-09-07": "Independência do Brasil",
        f"{year}-10-12": "Nossa Senhora Aparecida",
        f"{year}-11-02": "Finados",
        f"{year}-11-15": "Proclamação da República",
        f"{year}-12-25": "Natal",
    }
    # Consciência Negra — feriado nacional a partir de 2024 (Lei 14.759/2023)
    if year >= 2024:
        holidays[f"{year}-11-20"] = "Consciência Negra"

    # Movable holidays
    carnaval_terca = easter - timedelta(days=47)
    carnaval_segunda = easter - timedelta(days=48)
    sexta_santa = easter - timedelta(days=2)
    corpus_christi = easter + timedelta(days=60)

    holidays[carnaval_segunda.isoformat()] = "Carnaval (Segunda-feira)"
    holidays[carnaval_terca.isoformat()] = "Carnaval (Terça-feira)"
    holidays[sexta_santa.isoformat()] = "Sexta-feira Santa"
    holidays[corpus_christi.isoformat()] = "Corpus Christi"
    return holidays


def brazilian_holidays_range(start_year: int, end_year: int) -> dict:
    out: dict[str, str] = {}
    for y in range(start_year, end_year + 1):
        out.update(get_brazilian_holidays(y))
    return out


def is_brazilian_holiday(d: date) -> tuple[bool, str | None]:
    """Check if a given date is a Brazilian national holiday."""
    holidays = get_brazilian_holidays(d.year)
    name = holidays.get(d.isoformat())
    return (name is not None, name)
