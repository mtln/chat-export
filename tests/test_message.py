import base64
import dataclasses
import unittest
from datetime import date

from chat_export.chat_export import Message

from tests.helpers import make_chat, make_message


class MessageBasicsTest(unittest.TestCase):
    def test_fields_are_copied_verbatim(self):
        message = make_message(id=7, timestamp="05.02.24, 09:01", sender="Lena Voss", content="Hello")

        self.assertEqual(message.id, 7)
        self.assertEqual(message.timestamp, "05.02.24, 09:01")
        self.assertEqual(message.sender, "Lena Voss")
        self.assertEqual(message.content, "Hello")
        self.assertEqual(message.cleaned_content, "Hello")
        self.assertFalse(message.has_attachment)
        self.assertIsNone(message.attachment_name)

    def test_message_is_immutable(self):
        message = make_message()

        with self.assertRaises(dataclasses.FrozenInstanceError):
            message.content = "changed"

    def test_messages_with_same_values_are_equal(self):
        self.assertEqual(make_message(content="same"), make_message(content="same"))
        self.assertNotEqual(make_message(content="same"), make_message(content="other"))


class MessageDateTest(unittest.TestCase):
    def test_german_timestamp_is_parsed_and_gets_weekday(self):
        message = make_message(timestamp="05.02.24, 09:01")

        self.assertEqual(message.parsed_date, date(2024, 2, 5))
        self.assertEqual(message.formatted_timestamp, "Mon, 05.02.24, 09:01")

    def test_us_timestamp_with_am_pm(self):
        chat = make_chat(message_date_format="%m/%d/%y")

        message = make_message(chat=chat, timestamp="2/5/24, 9:01 AM")

        self.assertEqual(message.parsed_date, date(2024, 2, 5))
        self.assertEqual(message.formatted_timestamp, "Mon, 2/5/24, 9:01 AM")

    def test_four_digit_year(self):
        chat = make_chat(message_date_format="%d.%m.%Y")

        message = make_message(chat=chat, timestamp="29.02.2024, 23:59")

        self.assertEqual(message.parsed_date, date(2024, 2, 29))
        self.assertTrue(message.formatted_timestamp.startswith("Thu, "))

    def test_year_first_format(self):
        chat = make_chat(message_date_format="%Y-%m-%d")

        message = make_message(chat=chat, timestamp="2024-02-05, 09:01")

        self.assertEqual(message.parsed_date, date(2024, 2, 5))

    def test_timestamp_without_comma_and_with_dot_time_separator(self):
        # Indonesian exports look like "05/02/24 09.01".
        chat = make_chat(message_date_format="%d/%m/%y")

        message = make_message(chat=chat, timestamp="05/02/24 09.01")

        self.assertEqual(message.parsed_date, date(2024, 2, 5))
        self.assertEqual(message.formatted_timestamp, "Mon, 05/02/24 09.01")

    def test_timestamp_with_seconds(self):
        message = make_message(timestamp="05.02.24, 09:01:59")

        self.assertEqual(message.parsed_date, date(2024, 2, 5))

    def test_unparseable_timestamp_keeps_original_text(self):
        message = make_message(timestamp="sometime later")

        self.assertIsNone(message.parsed_date)
        self.assertEqual(message.formatted_timestamp, "sometime later")

    def test_timestamp_in_wrong_format_for_chat_is_not_parsed(self):
        chat = make_chat(message_date_format="%m/%d/%y")

        message = make_message(chat=chat, timestamp="05.02.24, 09:01")

        self.assertIsNone(message.parsed_date)
        self.assertEqual(message.formatted_timestamp, "05.02.24, 09:01")


class AndroidAttachmentTest(unittest.TestCase):
    def setUp(self):
        self.attachments = frozenset({"IMG-20240205-WA0001.jpg", "agenda.pdf", "VID-20240206-WA0002.mp4"})
        self.chat = make_chat(is_ios=False, has_media=True, attachments_in_zip=self.attachments)

    def test_english_attachment_marker(self):
        message = make_message(chat=self.chat, content="IMG-20240205-WA0001.jpg (file attached)")

        self.assertTrue(message.has_attachment)
        self.assertEqual(message.attachment_name, "IMG-20240205-WA0001.jpg")
        self.assertEqual(message.cleaned_content, "")

    def test_german_attachment_marker(self):
        message = make_message(chat=self.chat, content="IMG-20240205-WA0001.jpg (Datei angehängt)")

        self.assertEqual(message.attachment_name, "IMG-20240205-WA0001.jpg")
        self.assertEqual(message.cleaned_content, "")

    def test_attachment_with_caption_on_following_line(self):
        content = "IMG-20240205-WA0001.jpg (file attached) $NEWLINE$ Look at this one"

        message = make_message(chat=self.chat, content=content)

        self.assertEqual(message.attachment_name, "IMG-20240205-WA0001.jpg")
        self.assertNotIn("IMG-20240205", message.cleaned_content)
        self.assertNotIn("(file attached)", message.cleaned_content)
        self.assertTrue(message.cleaned_content.endswith("Look at this one"))

    def test_file_size_annotation_is_removed(self):
        message = make_message(chat=self.chat, content="agenda.pdf (file attached) (1,2 MB)")

        self.assertEqual(message.attachment_name, "agenda.pdf")
        self.assertEqual(message.cleaned_content, "")

    def test_attachment_missing_from_zip_is_plain_text(self):
        chat = make_chat(is_ios=False, has_media=True, attachments_in_zip=frozenset())

        message = make_message(chat=chat, content="IMG-20240205-WA0001.jpg (file attached)")

        self.assertFalse(message.has_attachment)
        self.assertIsNone(message.attachment_name)
        self.assertEqual(message.cleaned_content, "IMG-20240205-WA0001.jpg (file attached)")

    def test_media_omitted_placeholder_is_made_visible(self):
        message = make_message(chat=self.chat, content="<Media omitted>")

        self.assertFalse(message.has_attachment)
        self.assertEqual(message.cleaned_content, "[Media omitted]")

    def test_parentheses_in_normal_text_are_not_attachments(self):
        message = make_message(chat=self.chat, content="Meet at the cafe (the one near the park)")

        self.assertFalse(message.has_attachment)
        self.assertEqual(message.cleaned_content, "Meet at the cafe (the one near the park)")

    def test_ios_marker_is_ignored_for_android_chat(self):
        message = make_message(chat=self.chat, content="<attached: agenda.pdf>")

        self.assertFalse(message.has_attachment)
        self.assertEqual(message.cleaned_content, "[attached: agenda.pdf]")


class IOSAttachmentTest(unittest.TestCase):
    def setUp(self):
        self.photo = "00000003-PHOTO-2024-02-05-09-03-30.jpg"
        self.audio = "00000004-AUDIO-2024-02-06-20-15-00.opus"
        self.chat = make_chat(is_ios=True, has_media=True, attachments_in_zip=frozenset({self.photo, self.audio}))

    def test_english_attached_marker(self):
        message = make_message(chat=self.chat, content=f"<attached: {self.photo}>")

        self.assertTrue(message.has_attachment)
        self.assertEqual(message.attachment_name, self.photo)
        self.assertEqual(message.cleaned_content, "")

    def test_german_anhang_marker(self):
        message = make_message(chat=self.chat, content=f"<Anhang: {self.audio}>")

        self.assertEqual(message.attachment_name, self.audio)
        self.assertEqual(message.cleaned_content, "")

    def test_turkish_suffix_marker(self):
        message = make_message(chat=self.chat, content=f"<{self.photo} eklendi>")

        self.assertEqual(message.attachment_name, self.photo)
        self.assertEqual(message.cleaned_content, "")

    def test_attachment_missing_from_zip_is_shown_in_brackets(self):
        chat = make_chat(is_ios=True, has_media=False, attachments_in_zip=frozenset())

        message = make_message(chat=chat, content=f"<attached: {self.photo}>")

        self.assertFalse(message.has_attachment)
        self.assertEqual(message.cleaned_content, f"[attached: {self.photo}]")

    def test_android_marker_is_ignored_for_ios_chat(self):
        message = make_message(chat=self.chat, content=f"{self.photo} (file attached)")

        self.assertFalse(message.has_attachment)

    def test_angle_brackets_in_normal_text(self):
        message = make_message(chat=self.chat, content="3 < 5 > 2")

        self.assertFalse(message.has_attachment)
        self.assertEqual(message.cleaned_content, "3 [ 5 ] 2")


class ContentCleaningTest(unittest.TestCase):
    def test_newline_marker_becomes_br(self):
        message = make_message(content="first $NEWLINE$ second $NEWLINE$ third")

        self.assertEqual(message.cleaned_content, "first<br>second<br>third")

    def test_url_is_wrapped_in_anchor(self):
        message = make_message(content="Check https://example.org/menu?day=tue before we go")

        self.assertEqual(
            message.cleaned_content,
            'Check <a href="https://example.org/menu?day=tue" target="_blank">https://example.org/menu?day=tue</a> before we go',
        )

    def test_http_url_is_wrapped(self):
        message = make_message(content="http://example.net")

        self.assertEqual(message.cleaned_content, '<a href="http://example.net" target="_blank">http://example.net</a>')

    def test_multiple_urls(self):
        message = make_message(content="https://a.example and https://b.example")

        self.assertEqual(message.cleaned_content.count("<a href="), 2)

    def test_url_at_end_of_line_before_newline_marker(self):
        message = make_message(content="see https://a.example $NEWLINE$ next line")

        self.assertIn('<a href="https://a.example" target="_blank">https://a.example</a><br>next line', message.cleaned_content)

    def test_plain_words_are_not_urls(self):
        message = make_message(content="example.org is not linked")

        self.assertNotIn("<a ", message.cleaned_content)

    def test_null_content_is_call_attempt(self):
        message = make_message(content="null")

        self.assertEqual(message.cleaned_content, "[call (attempt)]")

    def test_empty_content_is_call_attempt(self):
        message = make_message(content="")

        self.assertEqual(message.cleaned_content, "[call (attempt)]")

    def test_empty_content_with_attachment_is_not_call_attempt(self):
        chat = make_chat(has_media=True, attachments_in_zip=frozenset({"agenda.pdf"}))

        message = make_message(chat=chat, content="agenda.pdf (file attached)")

        self.assertEqual(message.cleaned_content, "")

    def test_surrounding_whitespace_is_stripped(self):
        message = make_message(content="   padded   ")

        self.assertEqual(message.cleaned_content, "padded")

    def test_ampersand_and_quotes_are_kept(self):
        message = make_message(content='Tom & "Jerry"')

        self.assertEqual(message.cleaned_content, 'Tom & "Jerry"')

    def test_emoji_content_is_preserved(self):
        message = make_message(content="Party 🎉🎂")

        self.assertEqual(message.cleaned_content, "Party 🎉🎂")


class WrapUrlsTest(unittest.TestCase):
    def test_static_helper(self):
        self.assertEqual(
            Message._wrap_urls_with_anchor_tags("go to https://x.example/p"),
            'go to <a href="https://x.example/p" target="_blank">https://x.example/p</a>',
        )

    def test_no_url_unchanged(self):
        self.assertEqual(Message._wrap_urls_with_anchor_tags("nothing here"), "nothing here")


if __name__ == "__main__":
    unittest.main()
