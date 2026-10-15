import unittest

from chat_export.chat_export import MessageParser


class AndroidExportTest(unittest.TestCase):
    def test_german_export_detects_format_and_messages(self):
        chat_content = "\n".join([
            "13.03.24, 10:15 - Nachrichten und Anrufe sind Ende-zu-Ende-verschlüsselt.",
            "13.03.24, 10:16 - Tom: Hallo",
            "13.03.24, 10:17 - Fred: Hoi",
            "zweite Zeile",
        ])

        parser = MessageParser(is_ios=False)
        chat, filtered_count, total_count = parser.parse_messages(chat_content)

        self.assertEqual(parser.message_date_format, "%d.%m.%y")
        self.assertEqual(chat.senders, ["Fred", "Tom"])
        self.assertEqual(filtered_count, 3)
        self.assertEqual(total_count, 3)
        self.assertEqual([m.sender for m in chat.messages], ["WhatsApp", "Tom", "Fred"])
        self.assertEqual(chat.messages[2].content, "Hoi $NEWLINE$ zweite Zeile")
        self.assertEqual(chat.messages[1].formatted_timestamp, "Wed, 13.03.24, 10:16")

    def test_us_export_with_am_pm(self):
        chat_content = "\n".join([
            "3/13/24, 10:15 PM - Alice: Hi",
            "3/14/24, 8:05 AM - Bob: Hey",
        ])

        parser = MessageParser(is_ios=False)
        chat, _, _ = parser.parse_messages(chat_content)

        self.assertEqual(parser.message_date_format, "%m/%d/%y")
        self.assertEqual([m.timestamp for m in chat.messages], ["3/13/24, 10:15 PM", "3/14/24, 8:05 AM"])


class IOSExportTest(unittest.TestCase):
    def test_export_with_left_to_right_marks(self):
        chat_content = "\n".join([
            "\u200E[13.03.24, 10:15:01] Tom: Hallo",
            "\u200E[13.03.24, 10:16:02] Fred: \u200E<Anhang: 00000001-PHOTO-2024-03-13-10-16-02.jpg>",
        ])

        attachment = "00000001-PHOTO-2024-03-13-10-16-02.jpg"
        parser = MessageParser(is_ios=True, has_media=True, attachments_in_zip={attachment})
        chat, filtered_count, total_count = parser.parse_messages(chat_content)

        self.assertEqual(chat.senders, ["Fred", "Tom"])
        self.assertEqual(total_count, 2)
        self.assertEqual(filtered_count, 2)
        self.assertEqual(chat.messages[0].timestamp, "13.03.24, 10:15:01")
        self.assertEqual(chat.messages[1].attachment_name, attachment)
        self.assertEqual(chat.messages[1].cleaned_content, "")


class SenderNormalizationTest(unittest.TestCase):
    def test_zero_width_chars_inside_names_are_marked(self):
        chat_content = "13.03.24, 10:16 - T\u200Bom: Hallo"

        parser = MessageParser(is_ios=False)

        self.assertEqual(parser.get_senders(chat_content), ["T:ZWSP:om"])

    def test_bidi_controls_are_removed_from_names(self):
        chat_content = "13.03.24, 10:16 - \u200Fسارة\u200F: مرحبا"

        parser = MessageParser(is_ios=False)

        self.assertEqual(parser.get_senders(chat_content), ["سارة"])


if __name__ == "__main__":
    unittest.main()
