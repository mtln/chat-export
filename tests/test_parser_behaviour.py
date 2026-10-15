import unittest
from datetime import date

from chat_export.chat_export import DateRange, MessageParser

from tests.helpers import (
    ANDROID_MEDIA,
    IOS_MEDIA,
    android_chat_text,
    ios_chat_text,
    parse,
)


class MultiLineMessageTest(unittest.TestCase):
    def test_continuation_lines_are_joined_with_marker(self):
        chat, _, _ = parse("\n".join([
            "05.02.24, 09:04 - Mira Cole: Looks tasty",
            "second line",
            "third line",
        ]))

        self.assertEqual(len(chat.messages), 1)
        self.assertEqual(chat.messages[0].content, "Looks tasty $NEWLINE$ second line $NEWLINE$ third line")
        self.assertEqual(chat.messages[0].cleaned_content, "Looks tasty<br>second line<br>third line")

    def test_blank_line_inside_message_is_kept(self):
        chat, _, _ = parse("\n".join([
            "05.02.24, 09:04 - Mira Cole: paragraph one",
            "",
            "paragraph two",
        ]))

        self.assertEqual(chat.messages[0].cleaned_content, "paragraph one<br><br>paragraph two")

    def test_text_before_first_message_is_dropped(self):
        chat, _, total = parse("\n".join([
            "stray header line",
            "",
            "05.02.24, 09:04 - Mira Cole: real message",
        ]))

        self.assertEqual(total, 1)
        self.assertEqual([m.content for m in chat.messages], ["real message"])

    def test_continuation_line_that_looks_like_a_date_is_still_text(self):
        chat, _, _ = parse("\n".join([
            "05.02.24, 09:04 - Mira Cole: reminder",
            "31.12.2024 is the deadline",
        ]))

        self.assertEqual(len(chat.messages), 1)
        self.assertIn("31.12.2024 is the deadline", chat.messages[0].cleaned_content)

    def test_windows_line_endings_do_not_break_sender_detection(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: Hello\r\n05.02.24, 09:02 - Jonas Berg: Hey")

        self.assertEqual(chat.senders, ["Jonas Berg", "Lena Voss"])
        self.assertEqual([m.cleaned_content.strip() for m in chat.messages], ["Hello", "Hey"])

    def test_trailing_newline_at_end_of_file_does_not_add_line_break(self):
        # Exports end with a newline; the empty final line is not part of the last message.
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: Hello\n05.02.24, 09:02 - Jonas Berg: Bye\n")

        self.assertEqual(chat.messages[-1].content, "Bye")
        self.assertEqual(chat.messages[-1].cleaned_content, "Bye")

    def test_trailing_crlf_at_end_of_file_does_not_add_line_break(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: Hello\r\n05.02.24, 09:02 - Jonas Berg: Bye\r\n")

        self.assertEqual(chat.messages[-1].cleaned_content, "Bye")
        self.assertNotIn("<br>", chat.messages[-1].cleaned_content)

    def test_multiple_trailing_blank_lines_are_dropped(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: Hello\n\n   \n\t\n")

        self.assertEqual(chat.messages[-1].content, "Hello")

    def test_blank_lines_before_next_message_are_dropped(self):
        chat, _, _ = parse("\n".join([
            "05.02.24, 09:01 - Lena Voss: Hello",
            "",
            "",
            "05.02.24, 09:02 - Jonas Berg: Bye",
        ]))

        self.assertEqual([m.content for m in chat.messages], ["Hello", "Bye"])

    def test_multi_line_message_keeps_inner_blank_but_not_trailing_blank(self):
        chat, _, _ = parse("\n".join([
            "05.02.24, 09:01 - Lena Voss: one",
            "",
            "three",
            "",
            "05.02.24, 09:02 - Jonas Berg: Bye",
        ]))

        self.assertEqual(chat.messages[0].cleaned_content, "one<br><br>three")

    def test_message_with_only_blank_continuation_lines(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: \n\n")

        self.assertEqual(chat.messages[0].content, "")
        self.assertEqual(chat.messages[0].cleaned_content, "[call (attempt)]")

    def test_join_message_lines_helper(self):
        parser = MessageParser()

        self.assertEqual(parser._join_message_lines(["head"]), "head")
        self.assertEqual(parser._join_message_lines(["head", "a", "b"]), "head $NEWLINE$ a $NEWLINE$ b")
        self.assertEqual(parser._join_message_lines(["head", "a", "", " "]), "head $NEWLINE$ a")
        self.assertEqual(parser._join_message_lines(["head", "", "b"]), "head $NEWLINE$  $NEWLINE$ b")
        self.assertEqual(parser._join_message_lines(["head", ""]), "head")


class SystemMessageTest(unittest.TestCase):
    def test_android_system_message_gets_whatsapp_sender(self):
        chat, filtered, total = parse("\n".join([
            "05.02.24, 09:00 - Messages and calls are end-to-end encrypted.",
            "05.02.24, 09:01 - Lena Voss: hi",
        ]))

        self.assertEqual(total, 2)
        self.assertEqual(filtered, 2)
        self.assertEqual(chat.messages[0].sender, "WhatsApp")
        self.assertEqual(chat.messages[0].content, "Messages and calls are end-to-end encrypted.")

    def test_system_sender_is_not_a_participant(self):
        chat, _, _ = parse("\n".join([
            "05.02.24, 09:00 - Lena Voss created group \"Lunch Club\"",
            "05.02.24, 09:00 - Lena Voss added Jonas Berg",
            "05.02.24, 09:01 - Lena Voss: hi",
        ]))

        self.assertEqual(chat.senders, ["Lena Voss"])
        self.assertEqual([m.sender for m in chat.messages], ["WhatsApp", "WhatsApp", "Lena Voss"])

    def test_system_message_has_whatsapp_color(self):
        chat, _, _ = parse("\n".join([
            "05.02.24, 09:00 - Lena Voss added Jonas Berg",
            "05.02.24, 09:01 - Lena Voss: hi",
        ]))

        self.assertEqual(chat.sender_color_map["WhatsApp"], "#20c063")

    def test_ios_system_message_without_sender(self):
        chat, _, _ = parse("\n".join([
            "[05.02.24, 09:00:00] Lena Voss added Jonas Berg",
            "[05.02.24, 09:01:00] Lena Voss: hi",
        ]), is_ios=True)

        self.assertEqual([m.sender for m in chat.messages], ["WhatsApp", "Lena Voss"])

    def test_chat_with_only_system_messages_cannot_be_parsed(self):
        # Date format detection needs at least one line with a sender.
        with self.assertRaises(ValueError):
            parse("05.02.24, 09:00 - Lena Voss added Jonas Berg")


class MessageIdsAndCountsTest(unittest.TestCase):
    def test_ids_are_sequential_from_one(self):
        chat, _, _ = parse(android_chat_text())

        self.assertEqual([m.id for m in chat.messages], list(range(1, len(chat.messages) + 1)))

    def test_fixture_counts(self):
        chat, filtered, total = parse(android_chat_text())

        self.assertEqual(total, 11)
        self.assertEqual(filtered, 11)
        self.assertEqual(len(chat.messages), 11)

    def test_empty_chat_text_raises(self):
        with self.assertRaises(ValueError):
            parse("")


class DateFilteringTest(unittest.TestCase):
    def test_range_limits_messages_and_reports_counts(self):
        date_range = DateRange(from_date=date(2024, 2, 6), until_date=date(2024, 2, 7))

        chat, filtered, total = parse(android_chat_text(), date_range=date_range)

        self.assertEqual(total, 11)
        self.assertEqual(filtered, 4)
        self.assertEqual(len(chat.messages), 4)
        self.assertTrue(all(date(2024, 2, 6) <= m.parsed_date <= date(2024, 2, 7) for m in chat.messages))

    def test_ids_are_renumbered_after_filtering(self):
        date_range = DateRange(from_date=date(2024, 2, 8))

        chat, _, _ = parse(android_chat_text(), date_range=date_range)

        self.assertEqual([m.id for m in chat.messages], [1, 2])

    def test_continuation_lines_of_filtered_message_are_dropped(self):
        # Mira's multi-line message is on 05.02.; the range starts one day later.
        date_range = DateRange(from_date=date(2024, 2, 6))

        chat, _, _ = parse(android_chat_text(), date_range=date_range)

        joined = " ".join(m.content for m in chat.messages)
        self.assertNotIn("second line of Mira's message", joined)
        self.assertNotIn("third line", joined)

    def test_system_messages_are_filtered_too(self):
        date_range = DateRange(from_date=date(2024, 2, 6))

        chat, _, _ = parse(android_chat_text(), date_range=date_range)

        self.assertNotIn("WhatsApp", [m.sender for m in chat.messages])

    def test_range_without_matches_yields_no_messages(self):
        date_range = DateRange(from_date=date(2030, 1, 1))

        chat, filtered, total = parse(android_chat_text(), date_range=date_range)

        self.assertEqual(filtered, 0)
        self.assertEqual(total, 11)
        self.assertEqual(chat.messages, [])

    def test_unfiltered_range_object_keeps_everything(self):
        chat, filtered, total = parse(android_chat_text(), date_range=DateRange())

        self.assertEqual(filtered, total)
        self.assertIs(chat.date_range.is_filtered(), False)

    def test_date_range_is_attached_to_chat(self):
        date_range = DateRange(from_date=date(2024, 2, 6))

        chat, _, _ = parse(android_chat_text(), date_range=date_range)

        self.assertIs(chat.date_range, date_range)

    def test_senders_list_is_not_reduced_by_filtering(self):
        # The participant list is taken from the whole chat so the user can
        # always pick their own name, even if they did not write in the range.
        date_range = DateRange(from_date=date(2024, 2, 8))

        chat, _, _ = parse(android_chat_text(), date_range=date_range)

        self.assertEqual(chat.senders, ["Jonas Berg", "Lena Voss", "Mira Cole"])


class TimestampVariantsTest(unittest.TestCase):
    def test_android_24h_with_seconds(self):
        chat, _, _ = parse("13.03.24, 10:15:30 - Lena Voss: hi")

        self.assertEqual(chat.messages[0].timestamp, "13.03.24, 10:15:30")

    def test_android_am_pm_with_dots(self):
        chat, _, _ = parse("3/13/24, 10:15 p.m. - Lena Voss: hi")

        self.assertEqual(chat.messages[0].timestamp, "3/13/24, 10:15 p.m.")
        self.assertEqual(chat.messages[0].content, "hi")

    def test_android_lowercase_am_pm(self):
        chat, _, _ = parse("3/13/24, 10:15 pm - Lena Voss: hi")

        self.assertEqual(chat.messages[0].timestamp, "3/13/24, 10:15 pm")

    def test_android_narrow_no_break_space_before_am_pm(self):
        chat, _, _ = parse("3/13/24, 10:15 PM - Lena Voss: hi")

        self.assertEqual(chat.messages[0].sender, "Lena Voss")
        self.assertEqual(chat.messages[0].parsed_date, date(2024, 3, 13))

    def test_ios_brackets_are_not_part_of_timestamp(self):
        chat, _, _ = parse("[3/13/24, 10:15:01 PM] Lena Voss: hi", is_ios=True)

        self.assertEqual(chat.messages[0].timestamp, "3/13/24, 10:15:01 PM")
        self.assertEqual(chat.messages[0].formatted_timestamp, "Wed, 3/13/24, 10:15:01 PM")

    def test_indonesian_dot_time_separator(self):
        chat, _, _ = parse("30/08/25 18.00 - Budi Santoso: halo")

        self.assertEqual(chat.messages[0].sender, "Budi Santoso")
        self.assertEqual(chat.messages[0].parsed_date, date(2025, 8, 30))

    def test_arabic_am_pm_marker(self):
        chat, _, _ = parse("٢٤/٤/٢٠٢٢، ٢:٠٧ م - سلمى: مرحبا")

        self.assertEqual(chat.messages[0].timestamp, "24/4/2022, 2:07 م")
        self.assertEqual(chat.messages[0].parsed_date, date(2022, 4, 24))

    def test_persian_digits_are_normalized(self):
        chat, _, _ = parse("۲۴/۴/۲۰۲۲، ۲:۰۷ م - نازنین: سلام")

        self.assertEqual(chat.messages[0].timestamp, "24/4/2022, 2:07 م")
        self.assertEqual(chat.messages[0].sender, "نازنین")


class SenderHandlingTest(unittest.TestCase):
    def test_senders_are_unique_and_sorted(self):
        chat, _, _ = parse("\n".join([
            "05.02.24, 09:01 - Mira Cole: a",
            "05.02.24, 09:02 - Jonas Berg: b",
            "05.02.24, 09:03 - Mira Cole: c",
            "05.02.24, 09:04 - Lena Voss: d",
        ]))

        self.assertEqual(chat.senders, ["Jonas Berg", "Lena Voss", "Mira Cole"])

    def test_get_senders_matches_parsed_senders(self):
        parser = MessageParser()
        text = android_chat_text()

        chat, _, _ = parser.parse_messages(text)

        self.assertEqual(parser.get_senders(text), chat.senders)

    def test_phone_number_sender(self):
        chat, _, _ = parse("05.02.24, 09:01 - +1 555 010 0199: who is this?")

        self.assertEqual(chat.senders, ["+1 555 010 0199"])

    def test_sender_with_emoji_zwj_sequence_is_marked(self):
        # A ZWJ inside a name would be invisible in the participant list, so it
        # is replaced by a visible marker.
        chat, _, _ = parse("05.02.24, 09:01 - Sam 👨‍💻: hi")

        self.assertEqual(chat.senders, ["Sam 👨:ZWJ:💻"])
        self.assertEqual(chat.messages[0].sender, "Sam 👨:ZWJ:💻")

    def test_bom_around_sender_is_trimmed(self):
        chat, _, _ = parse("05.02.24, 09:01 - ﻿Lena Voss﻿: hi")

        self.assertEqual(chat.senders, ["Lena Voss"])

    def test_sender_with_colon_in_name(self):
        # The pattern stops at the first ": " so a name may not contain that
        # sequence, but a plain colon is fine.
        chat, _, _ = parse("05.02.24, 09:01 - Lena V:oss: hi")

        self.assertEqual(chat.messages[0].sender, "Lena V:oss")

    def test_content_containing_colon_space_is_preserved(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: note: bring cake")

        self.assertEqual(chat.messages[0].sender, "Lena Voss")
        self.assertEqual(chat.messages[0].content, "note: bring cake")


class NormalizationHelpersTest(unittest.TestCase):
    def test_normalize_is_idempotent(self):
        raw = "‎[٢٤/٤/٢٠٢٢، ٢:٠٧ م] ‫سلمى‬: مرحبا"

        once = MessageParser.normalize_locale_markers(raw)
        twice = MessageParser.normalize_locale_markers(once)

        self.assertEqual(once, twice)
        self.assertEqual(once, "[24/4/2022, 2:07 م] سلمى: مرحبا")

    def test_all_bidi_controls_are_removed(self):
        controls = "‎‏‪‫‬‭‮⁦⁧⁨⁩"

        self.assertEqual(MessageParser.normalize_locale_markers(f"a{controls}b"), "ab")

    def test_safe_zero_widths_are_not_removed_by_normalize(self):
        self.assertEqual(MessageParser.normalize_locale_markers("a​b"), "a​b")

    def test_trim_zero_widths_only_touches_ends(self):
        self.assertEqual(MessageParser.trim_zero_widths("​﻿ Lena‍Voss ‌"), "Lena‍Voss")

    def test_trim_zero_widths_plain_text(self):
        self.assertEqual(MessageParser.trim_zero_widths("  Lena  "), "Lena")

    def test_mark_invisible_chars(self):
        self.assertEqual(
            MessageParser.mark_invisible_chars("a​b‌c‍d﻿e"),
            "a:ZWSP:b:ZWNJ:c:ZWJ:d:BOM:e",
        )

    def test_mark_invisible_chars_leaves_visible_text_alone(self):
        self.assertEqual(MessageParser.mark_invisible_chars("Lena Voss"), "Lena Voss")


class ColorMapTest(unittest.TestCase):
    OTHERS = [
        "#f0e6ff", "#fff3e6", "#e6fff0", "#ffe6e6", "#e6f3ff", "#fff0f0", "#e6ffe6",
        "#f2e6ff", "#fff5e6", "#e6ffff", "#ffe6f0", "#f0ffe6", "#e6e6ff", "#ffe6cc", "#e6fff9",
    ]

    def test_own_name_gets_whatsapp_green(self):
        color_map = MessageParser()._generate_color_map(["Jonas Berg", "Lena Voss"], "Lena Voss")

        self.assertEqual(color_map["Lena Voss"], "#d9fdd3")

    def test_first_other_sender_is_white(self):
        color_map = MessageParser()._generate_color_map(["Jonas Berg", "Lena Voss"], "Lena Voss")

        self.assertEqual(color_map["Jonas Berg"], "#ffffff")

    def test_whatsapp_always_present(self):
        color_map = MessageParser()._generate_color_map(["Jonas Berg"], "Jonas Berg")

        self.assertEqual(color_map["WhatsApp"], "#20c063")

    def test_remaining_senders_get_distinct_colors(self):
        senders = ["Jonas Berg", "Lena Voss", "Mira Cole", "Priya Nair", "Tariq Haddad"]

        color_map = MessageParser()._generate_color_map(senders, "Lena Voss")

        self.assertEqual(color_map["Jonas Berg"], "#ffffff")
        self.assertEqual(color_map["Mira Cole"], self.OTHERS[0])
        self.assertEqual(color_map["Priya Nair"], self.OTHERS[1])
        self.assertEqual(color_map["Tariq Haddad"], self.OTHERS[2])

    def test_colors_wrap_around_for_large_groups(self):
        senders = [f"Participant {i:02d}" for i in range(1, 19)]

        color_map = MessageParser()._generate_color_map(senders, "Own")

        self.assertEqual(color_map["Participant 01"], "#ffffff")
        self.assertEqual(color_map["Participant 02"], self.OTHERS[0])
        self.assertEqual(color_map["Participant 16"], self.OTHERS[14])
        self.assertEqual(color_map["Participant 17"], self.OTHERS[0])
        self.assertEqual(color_map["Participant 18"], self.OTHERS[1])

    def test_color_map_is_stored_on_chat(self):
        chat, _, _ = parse(android_chat_text(), own_name="Mira Cole")

        self.assertEqual(chat.sender_color_map["Mira Cole"], "#d9fdd3")
        self.assertEqual(chat.sender_color_map["Jonas Berg"], "#ffffff")
        self.assertEqual(chat.sender_color_map["Lena Voss"], self.OTHERS[0])
        self.assertEqual(chat.sender_color_map["WhatsApp"], "#20c063")


class ChatMetadataTest(unittest.TestCase):
    def test_chat_name_and_own_name_propagate(self):
        chat, _, _ = parse(android_chat_text(), chat_name="Lunch Club.zip", own_name="Lena Voss")

        self.assertEqual(chat.name, "Lunch Club.zip")
        self.assertEqual(chat.own_name, "Lena Voss")

    def test_platform_and_media_flags_propagate(self):
        chat, _, _ = parse(ios_chat_text(), is_ios=True, has_media=True, attachments=IOS_MEDIA)

        self.assertTrue(chat.is_ios)
        self.assertTrue(chat.has_media)
        self.assertIsInstance(chat.attachments_in_zip, frozenset)
        self.assertEqual(chat.attachments_in_zip, frozenset(IOS_MEDIA))
        self.assertEqual(chat.newline_marker, " $NEWLINE$ ")

    def test_android_fixture_attachments_are_detected(self):
        chat, _, _ = parse(android_chat_text(), has_media=True, attachments=ANDROID_MEDIA)

        attached = [m.attachment_name for m in chat.messages if m.has_attachment]
        self.assertEqual(attached, ["IMG-20240205-WA0001.jpg", "VID-20240206-WA0002.mp4", "agenda.pdf"])

    def test_ios_fixture_attachments_are_detected_despite_marks(self):
        chat, _, _ = parse(ios_chat_text(), is_ios=True, has_media=True, attachments=IOS_MEDIA)

        attached = [m.attachment_name for m in chat.messages if m.has_attachment]
        self.assertEqual(attached, list(IOS_MEDIA))
        for message in chat.messages:
            self.assertNotIn("‎", message.content)
            self.assertNotIn("‎", message.cleaned_content)

    def test_parser_without_attachment_set_defaults_to_empty(self):
        parser = MessageParser()

        self.assertEqual(parser.attachments_in_zip, set())
        self.assertFalse(parser.has_media)
        self.assertFalse(parser.is_ios)


if __name__ == "__main__":
    unittest.main()
