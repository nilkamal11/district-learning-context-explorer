import pytest

from district_context.utils import normalize_district_id


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("10002", "0010002"), (10002, "0010002"), ("0010002", "0010002"), ("10002.0", "0010002")],
)
def test_normalize_district_id_preserves_seven_character_contract(raw, expected):
    assert normalize_district_id(raw) == expected


@pytest.mark.parametrize("raw", ["abc", "12345678", ""])
def test_normalize_district_id_rejects_invalid_values(raw):
    with pytest.raises(ValueError):
        normalize_district_id(raw)
