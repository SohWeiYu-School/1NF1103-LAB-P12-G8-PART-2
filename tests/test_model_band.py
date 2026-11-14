"""Band: a money figure at three levels."""

from app.model.band import Band


def test_band_rounds_to_cents_and_defaults_to_zero():
    assert Band().to_dict() == {"cautious": 0.0, "typical": 0.0, "optimistic": 0.0}
    assert Band(1.234, 2.345, 3.456).to_dict() == {"cautious": 1.23, "typical": 2.35, "optimistic": 3.46}


def test_bands_add_level_by_level():
    total = Band(1, 2, 3) + Band(10, 20, 30)
    assert (total.cautious, total.typical, total.optimistic) == (11, 22, 33)


def test_band_scales_by_a_factor():
    assert Band(10, 20, 30) * 0.5 == Band(5, 10, 15)


def test_from_values_puts_the_lowest_first():
    assert Band.from_values([30, 10, 20]) == Band(10, 20, 30)


def test_from_range_reads_an_ai_low_typical_high_range():
    assert Band.from_range({"low": 1, "typical": 2, "high": 3}) == Band(1, 2, 3)


def test_band_survives_a_round_trip_through_a_dict():
    band = Band(1.5, 2.5, 3.5)
    assert Band.from_dict(band.to_dict()) == band


def test_money_in_and_money_out_use_opposite_ends_of_a_range():
    assert Band.MONEY_IN["cautious"] == "low"
    assert Band.MONEY_OUT["cautious"] == "high"


def test_the_dict_helpers_do_the_same_arithmetic_in_the_saved_layout():
    one, two = Band(1, 2, 3).to_dict(), Band(10, 20, 30).to_dict()
    assert Band.add(one, two) == (Band(1, 2, 3) + Band(10, 20, 30)).to_dict()
    assert Band.scale(two, 0.5) == Band(5, 10, 15).to_dict()
    assert Band.zero() == Band().to_dict()
    assert Band.as_dict(1, 2, 3) == one
    assert Band.ordered([3, 1, 2]) == one
    assert Band.from_ai({"low": 1, "typical": 2, "high": 3}) == one
