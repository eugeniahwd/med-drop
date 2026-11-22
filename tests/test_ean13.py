import pytest

from backend import ean13


@pytest.mark.parametrize("first12, expected", [
    ("200000000001", "5"),
    ("200000000099", "2"),
    ("400638133393", "1"),  # contoh umum dari dokumentasi EAN-13
])
def test_check_digit(first12, expected):
    assert ean13.check_digit(first12) == expected


@pytest.mark.parametrize("code, valid, dummy", [
    ("2000000000015", True, True),
    ("2000000000016", False, False),   # digit cek salah
    ("4006381333931", True, False),    # valid tapi bukan awalan dummy
    ("200000000001", False, False),    # kurang satu digit
    ("20000000000A5", False, False),
])
def test_validation(code, valid, dummy):
    assert ean13.is_valid(code) is valid
    assert ean13.is_dummy(code) is dummy


def test_bar_pattern_has_95_modules_and_guards():
    bits = ean13.bar_pattern("2000000000015")
    assert len(bits) == 95
    assert bits[:3] == "101" and bits[45:50] == "01010" and bits[-3:] == "101"


def test_bar_pattern_rejects_invalid_code():
    with pytest.raises(ValueError):
        ean13.bar_pattern("2000000000016")
