import unittest

from chat_export.chat_export import MessageParser


class AndroidDateFormatDetectionTest(unittest.TestCase):
    def detect(self, *lines):
        return MessageParser(is_ios=False).get_date_format("\n".join(lines))

    def test_german_two_digit_year(self):
        self.assertEqual(self.detect("13.03.24, 10:15 - Lena Voss: hi"), "%d.%m.%y")

    def test_german_four_digit_year(self):
        self.assertEqual(self.detect("13.03.2024, 10:15 - Lena Voss: hi"), "%d.%m.%Y")

    def test_us_two_digit_year(self):
        self.assertEqual(self.detect("3/13/24, 10:15 PM - Lena Voss: hi"), "%m/%d/%y")

    def test_us_four_digit_year(self):
        self.assertEqual(self.detect("3/13/2024, 10:15 PM - Lena Voss: hi"), "%m/%d/%Y")

    def test_year_first_iso_style(self):
        self.assertEqual(self.detect("2024-03-13, 10:15 - Lena Voss: hi"), "%Y-%m-%d")

    def test_day_first_slash_format(self):
        self.assertEqual(self.detect("13/03/2024, 10:15 - Lena Voss: hi"), "%d/%m/%Y")

    def test_indonesian_without_comma_and_dot_time(self):
        self.assertEqual(self.detect("30/08/25 18.00 - Budi Santoso: halo"), "%d/%m/%y")

    def test_ambiguous_dates_default_to_day_first(self):
        # 03.04 could be March 4th or April 3rd; the tool assumes day first.
        self.assertEqual(self.detect("03.04.24, 10:15 - Lena Voss: hi"), "%d.%m.%y")
        self.assertEqual(self.detect("3/4/24, 10:15 AM - Lena Voss: hi"), "%d/%m/%y")

    def test_later_line_disambiguates_day_first(self):
        fmt = self.detect(
            "03.04.24, 10:15 - Lena Voss: hi",
            "25.04.24, 10:16 - Jonas Berg: hey",
        )

        self.assertEqual(fmt, "%d.%m.%y")

    def test_later_line_disambiguates_month_first(self):
        fmt = self.detect(
            "3/4/24, 10:15 AM - Lena Voss: hi",
            "4/25/24, 10:16 AM - Jonas Berg: hey",
        )

        self.assertEqual(fmt, "%m/%d/%y")

    def test_first_decisive_line_wins(self):
        fmt = self.detect(
            "3/4/24, 10:15 AM - Lena Voss: hi",
            "4/25/24, 10:16 AM - Jonas Berg: month first",
            "25/4/24, 10:17 AM - Mira Cole: this contradiction is never reached",
        )

        self.assertEqual(fmt, "%m/%d/%y")

    def test_system_lines_before_first_message_are_skipped(self):
        fmt = self.detect(
            "",
            "13.03.24, 10:14 - Messages and calls are end-to-end encrypted.",
            "13.03.24, 10:15 - Lena Voss: hi",
        )

        self.assertEqual(fmt, "%d.%m.%y")

    def test_continuation_lines_are_ignored(self):
        fmt = self.detect(
            "13.03.24, 10:15 - Lena Voss: hi",
            "12/31/2020 is not a timestamp, just text",
        )

        self.assertEqual(fmt, "%d.%m.%y")

    def test_arabic_digits_are_normalized_before_detection(self):
        fmt = self.detect("٢٤‏/٤‏/٢٠٢٢، ٢:٠٧ م - سلمى: مرحبا")

        self.assertEqual(fmt, "%d/%m/%Y")

    def test_no_message_line_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.detect("just some notes", "and nothing else")

        self.assertIn("Could not determine the date format", str(ctx.exception))
        self.assertIn("just some notes", str(ctx.exception))

    def test_empty_content_raises(self):
        with self.assertRaises(ValueError):
            self.detect("")

    def test_only_system_messages_raises(self):
        with self.assertRaises(ValueError):
            self.detect("13.03.24, 10:14 - Messages and calls are end-to-end encrypted.")

    def test_ios_lines_do_not_match_android_parser(self):
        with self.assertRaises(ValueError):
            self.detect("[13.03.24, 10:15:01] Lena Voss: hi")


class IOSDateFormatDetectionTest(unittest.TestCase):
    def detect(self, *lines):
        return MessageParser(is_ios=True).get_date_format("\n".join(lines))

    def test_german_with_seconds(self):
        self.assertEqual(self.detect("[13.03.24, 10:15:01] Lena Voss: hi"), "%d.%m.%y")

    def test_us_with_am_pm(self):
        self.assertEqual(self.detect("[3/13/24, 10:15:01 PM] Lena Voss: hi"), "%m/%d/%y")

    def test_four_digit_year(self):
        self.assertEqual(self.detect("[13.03.2024, 10:15:01] Lena Voss: hi"), "%d.%m.%Y")

    def test_leading_left_to_right_mark(self):
        self.assertEqual(self.detect("‎[13.03.24, 10:15:01] Lena Voss: ‎hi"), "%d.%m.%y")

    def test_android_lines_do_not_match_ios_parser(self):
        with self.assertRaises(ValueError):
            self.detect("13.03.24, 10:15 - Lena Voss: hi")


class ParseMessagesSetsDateFormatTest(unittest.TestCase):
    def test_parser_attribute_is_updated(self):
        parser = MessageParser()
        self.assertEqual(parser.message_date_format, "%d.%m.%y")

        parser.parse_messages("3/13/24, 10:15 PM - Lena Voss: hi")

        self.assertEqual(parser.message_date_format, "%m/%d/%y")

    def test_chat_carries_detected_format(self):
        chat, _, _ = MessageParser().parse_messages("2024-03-13, 10:15 - Lena Voss: hi")

        self.assertEqual(chat.message_date_format, "%Y-%m-%d")
        self.assertEqual(chat.messages[0].formatted_timestamp, "Wed, 2024-03-13, 10:15")


if __name__ == "__main__":
    unittest.main()
