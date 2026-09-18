import unittest

from chat_export.chat_export import MessageParser


class ArabicLocaleExportTest(unittest.TestCase):
    def test_android_export_with_arabic_digits_and_time_markers(self):
        chat_content = "\n".join([
            "٢٤\u200f/٤\u200f/٢٠٢٢، ٢:٠٧ م - عمار لبنان: السلام",
            "٢٤\u200f/٤\u200f/٢٠٢٢، ٢:٠٨ م - الحمد الله: اهلين",
        ])

        parser = MessageParser()
        senders = parser.get_senders(chat_content)
        chat, filtered_count, total_count = parser.parse_messages(chat_content)

        self.assertEqual(senders, ["الحمد الله", "عمار لبنان"])
        self.assertEqual(filtered_count, 2)
        self.assertEqual(total_count, 2)
        self.assertEqual([message.sender for message in chat.messages], ["عمار لبنان", "الحمد الله"])
        self.assertEqual([message.content for message in chat.messages], ["السلام", "اهلين"])


if __name__ == "__main__":
    unittest.main()
