from usdata._grib import _time


def test_grib_times_carry_the_reference_seconds() -> None:
    assert _time(20240506, 2000, 41) == "2024-05-06T20:00:41+00:00"
    assert _time(20240506, 2000) == "2024-05-06T20:00:00+00:00"
    assert _time(None, 2000, 41) is None
