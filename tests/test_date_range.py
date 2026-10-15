import unittest
from datetime import date

from chat_export.chat_export import DateRange, MessageParser


FORMATS = MessageParser().date_formats


class DateRangeConstructionTest(unittest.TestCase):
    def test_empty_range_is_not_filtered(self):
        date_range = DateRange()

        self.assertFalse(date_range.is_filtered())
        self.assertIsNone(date_range.from_date)
        self.assertIsNone(date_range.until_date)

    def test_from_only_is_filtered(self):
        self.assertTrue(DateRange(from_date=date(2024, 1, 1)).is_filtered())

    def test_until_only_is_filtered(self):
        self.assertTrue(DateRange(until_date=date(2024, 1, 1)).is_filtered())

    def test_from_after_until_raises(self):
        with self.assertRaises(ValueError) as ctx:
            DateRange(from_date=date(2024, 6, 1), until_date=date(2024, 5, 31))

        self.assertIn("'From' date must be before 'until' date", str(ctx.exception))

    def test_same_day_range_is_allowed(self):
        same_day = date(2024, 6, 1)

        date_range = DateRange(from_date=same_day, until_date=same_day)

        self.assertTrue(date_range.contains(same_day))


class DateRangeContainsTest(unittest.TestCase):
    def setUp(self):
        self.date_range = DateRange(from_date=date(2024, 3, 1), until_date=date(2024, 3, 31))

    def test_inside_range(self):
        self.assertTrue(self.date_range.contains(date(2024, 3, 15)))

    def test_boundaries_are_inclusive(self):
        self.assertTrue(self.date_range.contains(date(2024, 3, 1)))
        self.assertTrue(self.date_range.contains(date(2024, 3, 31)))

    def test_before_range(self):
        self.assertFalse(self.date_range.contains(date(2024, 2, 29)))

    def test_after_range(self):
        self.assertFalse(self.date_range.contains(date(2024, 4, 1)))

    def test_unparseable_date_is_kept(self):
        # Messages whose date could not be parsed must never be silently dropped.
        self.assertTrue(self.date_range.contains(None))

    def test_open_ended_from(self):
        date_range = DateRange(from_date=date(2024, 3, 1))

        self.assertTrue(date_range.contains(date(2030, 1, 1)))
        self.assertFalse(date_range.contains(date(2024, 2, 28)))

    def test_open_ended_until(self):
        date_range = DateRange(until_date=date(2024, 3, 31))

        self.assertTrue(date_range.contains(date(1999, 1, 1)))
        self.assertFalse(date_range.contains(date(2024, 4, 1)))

    def test_unbounded_range_contains_everything(self):
        self.assertTrue(DateRange().contains(date(2000, 1, 1)))


class DateRangeFormatTest(unittest.TestCase):
    def test_unfiltered_range_formats_to_none(self):
        self.assertIsNone(DateRange().format_range("%d.%m.%y"))

    def test_both_bounds(self):
        date_range = DateRange(from_date=date(2024, 3, 1), until_date=date(2024, 3, 31))

        self.assertEqual(date_range.format_range("%d.%m.%y"), "Filtered: 01.03.24 to 31.03.24")

    def test_format_follows_chat_date_format(self):
        date_range = DateRange(from_date=date(2024, 3, 1), until_date=date(2024, 3, 31))

        self.assertEqual(date_range.format_range("%m/%d/%Y"), "Filtered: 03/01/2024 to 03/31/2024")

    def test_from_only_uses_end_placeholder(self):
        date_range = DateRange(from_date=date(2024, 3, 1))

        self.assertEqual(date_range.format_range("%d.%m.%y"), "Filtered: 01.03.24 to end")

    def test_until_only_uses_start_placeholder(self):
        date_range = DateRange(until_date=date(2024, 3, 31))

        self.assertEqual(date_range.format_range("%d.%m.%y"), "Filtered: start to 31.03.24")


class ParseDateInputTest(unittest.TestCase):
    def test_empty_input_returns_none(self):
        self.assertIsNone(DateRange.parse_date_input("", FORMATS))
        self.assertIsNone(DateRange.parse_date_input(None, FORMATS))

    def test_german_four_digit_year(self):
        self.assertEqual(DateRange.parse_date_input("24.12.2023", FORMATS), date(2023, 12, 24))

    def test_german_two_digit_year(self):
        self.assertEqual(DateRange.parse_date_input("24.12.23", FORMATS), date(2023, 12, 24))

    def test_us_four_digit_year(self):
        self.assertEqual(DateRange.parse_date_input("12/24/2023", FORMATS), date(2023, 12, 24))

    def test_us_two_digit_year(self):
        self.assertEqual(DateRange.parse_date_input("12/24/23", FORMATS), date(2023, 12, 24))

    def test_day_first_slash_format(self):
        # 24 cannot be a month, so only the DD/MM/YYYY format accepts it.
        self.assertEqual(DateRange.parse_date_input("24/12/2023", FORMATS), date(2023, 12, 24))
        self.assertEqual(DateRange.parse_date_input("24/12/23", FORMATS), date(2023, 12, 24))

    def test_ambiguous_slash_date_prefers_us_format(self):
        # Formats are tried in order, so 03/04 is March 4th, not April 3rd.
        self.assertEqual(DateRange.parse_date_input("03/04/2024", FORMATS), date(2024, 3, 4))

    def test_single_digit_day_and_month_are_accepted(self):
        self.assertEqual(DateRange.parse_date_input("1.2.2024", FORMATS), date(2024, 2, 1))
        self.assertEqual(DateRange.parse_date_input("1/2/2024", FORMATS), date(2024, 1, 2))

    def test_invalid_input_raises_with_help_text(self):
        with self.assertRaises(ValueError) as ctx:
            DateRange.parse_date_input("2024-01-01", FORMATS)

        self.assertIn("DD.MM.YYYY", str(ctx.exception))

    def test_impossible_date_raises(self):
        with self.assertRaises(ValueError):
            DateRange.parse_date_input("31.02.2024", FORMATS)

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            DateRange.parse_date_input("yesterday", FORMATS)


if __name__ == "__main__":
    unittest.main()
