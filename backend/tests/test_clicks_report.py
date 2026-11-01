from datetime import date

from scripts.clicks_report import csv_row, month_days, summarise


def test_month_days_covers_the_whole_month() -> None:
    days = month_days("2026-02", today=date(2026, 12, 1))
    assert days[0] == "2026-02-01" and days[-1] == "2026-02-28" and len(days) == 28


def test_month_days_stops_at_today() -> None:
    assert month_days("2026-11", today=date(2026, 11, 3)) == [
        "2026-11-01",
        "2026-11-02",
        "2026-11-03",
    ]


def test_month_days_handles_december() -> None:
    assert month_days("2026-12", today=date(2027, 1, 5))[-1] == "2026-12-31"


def test_summarise_counts_by_store_country_and_anime() -> None:
    clicks = [
        {"pk": "2026-11-01", "store": "ebay", "country": "SG", "anime_id": "52991"},
        {"pk": "2026-11-01", "store": "cdjapan", "country": "SG", "anime_id": "52991"},
        {"pk": "2026-11-02", "store": "ebay", "country": "MY", "anime_id": "None"},
    ]
    totals = summarise(clicks)
    assert totals["day"] == {"2026-11-01": 2, "2026-11-02": 1}
    assert totals["store"] == {"ebay": 2, "cdjapan": 1}
    assert totals["country"] == {"SG": 2, "MY": 1}
    assert totals["anime"] == {"52991": 2}  # a click without an anime isn't counted here


def test_csv_row_keeps_only_what_was_recorded() -> None:
    row = csv_row(
        {
            "pk": "2026-11-01",
            "sk": "2026-11-01T08:15:00+00:00#ab12cd34",
            "store": "apple",
            "anime_id": "52991",
            "country": "SG",
            "theme_id": "1234",
        }
    )
    assert row == {
        "day": "2026-11-01",
        "time": "2026-11-01T08:15:00+00:00",
        "store": "apple",
        "anime_id": "52991",
        "country": "SG",
        "character_id": "",
        "theme_id": "1234",
    }
