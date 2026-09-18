import base64
import contextlib
import io
import tempfile
import unittest
from datetime import date
from pathlib import Path

from chat_export.chat_export import DateRange, HTMLRenderer, Renderer

from tests.helpers import (
    FAKE_PDF,
    TINY_PNG,
    TempDirTestCase,
    make_chat,
    make_message,
    parse,
    quiet,
    write_zip,
)


class RendererBaseClassTest(unittest.TestCase):
    def test_base_methods_are_abstract(self):
        renderer = Renderer(output_dir="out")

        self.assertEqual(renderer.output_dir, "out")
        with self.assertRaises(NotImplementedError):
            renderer.render(None)
        with self.assertRaises(NotImplementedError):
            renderer.get_generated_files()


class RendererSetupTest(unittest.TestCase):
    def test_default_file_names(self):
        renderer = HTMLRenderer(output_dir="out")

        self.assertEqual(renderer.html_filename, "chat.html")
        self.assertEqual(renderer.html_filename_media_linked, "chat_media_linked.html")
        self.assertEqual(renderer.media_path, "./media")
        self.assertFalse(renderer.embed_media)
        self.assertEqual(renderer.attachments_to_extract, set())

    def test_generated_files_without_embedding(self):
        renderer = HTMLRenderer(output_dir="out")

        self.assertEqual(
            renderer.get_generated_files(),
            [Path("out", "chat.html"), Path("out", "chat_media_linked.html")],
        )

    def test_embed_mode_names_file_after_zip(self):
        renderer = HTMLRenderer(output_dir="out", embed_media=True, zip_path="/exports/Lunch Club.zip")

        self.assertEqual(renderer.html_filename, "Lunch Club.html")
        self.assertIsNone(renderer.html_filename_media_linked)
        self.assertEqual(renderer.get_generated_files(), [Path("out", "Lunch Club.html")])


class MimeTypeTest(unittest.TestCase):
    CASES = {
        "photo.jpg": "image/jpeg",
        "photo.jpeg": "image/jpeg",
        "PHOTO.JPG": "image/jpeg",
        "sticker.png": "image/png",
        "anim.gif": "image/gif",
        "pic.webp": "image/webp",
        "clip.mp4": "video/mp4",
        "voice.opus": "audio/ogg",
        "song.mp3": "audio/mpeg",
        "sound.wav": "audio/wav",
        "memo.m4a": "audio/mp4",
        "agenda.pdf": "application/pdf",
        "letter.doc": "application/msword",
        "letter.docx": "application/msword",
        "sheet.xls": "application/vnd.ms-excel",
        "sheet.xlsx": "application/vnd.ms-excel",
        "deck.ppt": "application/vnd.ms-powerpoint",
        "deck.pptx": "application/vnd.ms-powerpoint",
        "notes.txt": "text/plain",
        "notes.rtf": "application/rtf",
        "bundle.zip": "application/zip",
        "bundle.rar": "application/x-rar-compressed",
        "bundle.7z": "application/x-7z-compressed",
        "bundle.tar": "application/x-tar",
        "bundle.gz": "application/gzip",
        "data.csv": "text/csv",
        "data.json": "application/json",
        "data.xml": "application/xml",
        "page.html": "text/html",
        "style.css": "text/css",
        "app.js": "application/javascript",
        "script.py": "text/x-python",
        "Main.java": "text/x-java-source",
        "main.cpp": "text/x-c",
        "main.c": "text/x-c",
        "main.h": "text/x-c",
        "unknown.xyz": "application/octet-stream",
        "no_extension": "application/octet-stream",
    }

    def test_extension_mapping(self):
        renderer = HTMLRenderer(output_dir="out")
        for filename, expected in self.CASES.items():
            with self.subTest(filename=filename):
                self.assertEqual(renderer.get_mime_type(filename), expected)


class MediaElementLinkedTest(unittest.TestCase):
    def setUp(self):
        self.renderer = HTMLRenderer(output_dir="out", has_media=True)

    def test_image(self):
        self.assertEqual(
            self.renderer.render_media_element("pic.jpg"),
            '<img class="media" src="./media/pic.jpg"><br>',
        )

    def test_all_image_extensions_render_as_img(self):
        for name in ("a.jpg", "a.jpeg", "a.png", "a.webp", "a.gif", "A.PNG"):
            with self.subTest(name=name):
                self.assertTrue(self.renderer.render_media_element(name).startswith('<img class="media"'))

    def test_video(self):
        html = self.renderer.render_media_element("clip.mp4")

        self.assertIn('<video class="media" controls>', html)
        self.assertIn('src="./media/clip.mp4" type="video/mp4"', html)

    def test_audio_types(self):
        expected = {
            "voice.opus": "audio/ogg",
            "sound.wav": "audio/wav",
            "song.mp3": "audio/mpeg",
            "memo.m4a": "audio/mp4",
        }
        for name, mime in expected.items():
            with self.subTest(name=name):
                html = self.renderer.render_media_element(name)
                self.assertIn('<audio class="media" controls>', html)
                self.assertIn(f'src="./media/{name}" type="{mime}"', html)

    def test_document_is_a_link(self):
        self.assertEqual(
            self.renderer.render_media_element("agenda.pdf"),
            '<a href="./media/agenda.pdf">📎 agenda.pdf</a><br>',
        )

    def test_media_linked_variant_always_links(self):
        for name in ("pic.jpg", "clip.mp4", "voice.opus", "agenda.pdf"):
            with self.subTest(name=name):
                self.assertEqual(
                    self.renderer.render_media_element(name, is_media_linked=True),
                    f'<a href="./media/{name}">📎 {name}</a><br>',
                )

    def test_custom_media_path(self):
        renderer = HTMLRenderer(output_dir="out", media_path="../assets")

        self.assertEqual(renderer.render_media_element("pic.png"), '<img class="media" src="../assets/pic.png"><br>')


class MediaElementEmbeddedTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.zip_path = write_zip(
            self.tmp / "Lunch Club.zip",
            "Lunch Club.txt",
            "05.02.24, 09:01 - Lena Voss: hi",
            {"pic.jpg": TINY_PNG, "agenda.pdf": FAKE_PDF, "clip.mp4": b"\x00" * 16, "voice.opus": b"OggS"},
        )
        self.renderer = HTMLRenderer(output_dir=str(self.tmp), has_media=True, embed_media=True, zip_path=self.zip_path)

    def test_encode_media_to_base64(self):
        data_uri = self.renderer.encode_media_to_base64("pic.jpg")

        self.assertEqual(data_uri, "data:image/jpeg;base64," + base64.b64encode(TINY_PNG).decode("ascii"))

    def test_encode_missing_file_returns_none_and_warns(self):
        with io.StringIO() as out, contextlib.redirect_stdout(out):
            result = self.renderer.encode_media_to_base64("missing.jpg")
            printed = out.getvalue()

        self.assertIsNone(result)
        self.assertIn("Warning: Could not encode missing.jpg", printed)

    def test_image_is_inlined(self):
        html = self.renderer.render_media_element("pic.jpg")

        self.assertTrue(html.startswith('<img class="media" src="data:image/jpeg;base64,'))
        self.assertIn(base64.b64encode(TINY_PNG).decode("ascii"), html)
        self.assertNotIn("./media/", html)

    def test_video_is_inlined(self):
        html = self.renderer.render_media_element("clip.mp4")

        self.assertIn('<source src="data:video/mp4;base64,', html)

    def test_audio_is_inlined(self):
        html = self.renderer.render_media_element("voice.opus")

        self.assertIn('<source src="data:audio/ogg;base64,', html)
        self.assertIn('type="audio/ogg"', html)

    def test_document_becomes_download_link(self):
        html = self.renderer.render_media_element("agenda.pdf")

        self.assertTrue(html.startswith('<a href="data:application/pdf;base64,'))
        self.assertIn('download="agenda.pdf"', html)
        self.assertIn("📎 agenda.pdf", html)

    def test_missing_file_falls_back_to_file_reference(self):
        with quiet():
            html = self.renderer.render_media_element("missing.jpg")

        self.assertEqual(html, '<img class="media" src="./media/missing.jpg"><br>')

    def test_media_linked_variant_ignores_embedding(self):
        html = self.renderer.render_media_element("pic.jpg", is_media_linked=True)

        self.assertEqual(html, '<a href="./media/pic.jpg">📎 pic.jpg</a><br>')

    def test_embed_without_zip_path_uses_file_reference(self):
        renderer = HTMLRenderer(output_dir="out", embed_media=True, zip_path="ignored.zip")
        renderer.zip_path = None

        self.assertEqual(renderer.render_media_element("pic.jpg"), '<img class="media" src="./media/pic.jpg"><br>')


class RenderMessageTest(unittest.TestCase):
    def setUp(self):
        self.renderer = HTMLRenderer(output_dir="out", has_media=True)
        self.color_map = {"Lena Voss": "#d9fdd3", "Jonas Berg": "#ffffff", "WhatsApp": "#20c063"}

    def render(self, message, own_name="Lena Voss", color_map=None):
        main_f, media_f = io.StringIO(), io.StringIO()
        self.renderer.render_message(message, color_map or self.color_map, own_name, main_f, media_f)
        return main_f.getvalue(), media_f.getvalue()

    def test_own_message_is_sent(self):
        main, media = self.render(make_message(sender="Lena Voss", content="hi", id=3))

        self.assertIn('<div class="message sent clearfix" data-id="3" style="background-color: #d9fdd3;">', main)
        self.assertEqual(main, media)

    def test_other_message_is_received(self):
        main, _ = self.render(make_message(sender="Jonas Berg"))

        self.assertIn('class="message received clearfix"', main)
        self.assertIn("background-color: #ffffff;", main)

    def test_system_message_uses_whatsapp_class(self):
        main, _ = self.render(make_message(sender="WhatsApp", content="Lena Voss added Jonas Berg"))

        self.assertIn('class="message whatsapp clearfix"', main)
        self.assertIn("background-color: #20c063;", main)

    def test_unknown_sender_falls_back_to_white(self):
        main, _ = self.render(make_message(sender="Priya Nair"), color_map={})

        self.assertIn("background-color: #ffffff;", main)

    def test_sender_name_is_escaped(self):
        main, _ = self.render(make_message(sender="Ana & Bo <3", content="hi"))

        self.assertIn('<div class="sender">Ana &amp; Bo &lt;3</div>', main)

    def test_timestamp_and_id_are_shown(self):
        main, _ = self.render(make_message(id=42, timestamp="05.02.24, 09:01"))

        self.assertIn('<span class="timestamp">Mon, 05.02.24, 09:01 (#42)</span>', main)

    def test_content_is_written_once(self):
        main, _ = self.render(make_message(content="unique text"))

        self.assertEqual(main.count("unique text"), 1)
        self.assertIn('<div class="content">unique text</div>', main)

    def test_structure_is_well_nested(self):
        main, _ = self.render(make_message())

        self.assertTrue(main.startswith('\n<div class="message '))
        self.assertTrue(main.endswith("</span></div>"))
        self.assertEqual(main.count("<div"), 3)
        self.assertEqual(main.count("</div>"), 3)

    def test_attachment_is_rendered_differently_per_file(self):
        chat = make_chat(has_media=True, attachments_in_zip=frozenset({"IMG-1.jpg"}))
        message = make_message(chat=chat, content="IMG-1.jpg (file attached)")

        main, media = self.render(message)

        self.assertIn('<img class="media" src="./media/IMG-1.jpg"><br>', main)
        self.assertIn('<a href="./media/IMG-1.jpg">📎 IMG-1.jpg</a><br>', media)
        self.assertNotIn("<img", media)
        self.assertEqual(self.renderer.attachments_to_extract, {"IMG-1.jpg"})

    def test_attachment_with_caption_keeps_caption(self):
        chat = make_chat(has_media=True, attachments_in_zip=frozenset({"IMG-1.jpg"}))
        message = make_message(chat=chat, content="IMG-1.jpg (file attached) $NEWLINE$ the caption")

        main, _ = self.render(message)

        self.assertIn("<img", main)
        self.assertIn("the caption", main)

    def test_attachments_accumulate_across_messages(self):
        chat = make_chat(has_media=True, attachments_in_zip=frozenset({"a.jpg", "b.pdf"}))

        self.render(make_message(chat=chat, content="a.jpg (file attached)"))
        self.render(make_message(chat=chat, content="b.pdf (file attached)"))
        self.render(make_message(chat=chat, content="plain text"))

        self.assertEqual(self.renderer.attachments_to_extract, {"a.jpg", "b.pdf"})

    def test_link_in_content_is_kept_as_anchor(self):
        main, _ = self.render(make_message(content="see https://example.org"))

        self.assertIn('<a href="https://example.org" target="_blank">https://example.org</a>', main)


class RenderDocumentTest(TempDirTestCase):
    def render_chat(self, chat, **renderer_kwargs):
        renderer = HTMLRenderer(output_dir=str(self.tmp), has_media=True, **renderer_kwargs)
        with quiet():
            attachments = renderer.render(chat)
        return renderer, attachments

    def test_writes_both_files(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: hi", chat_name="Lunch.zip")

        renderer, attachments = self.render_chat(chat)

        for path in renderer.get_generated_files():
            self.assertTrue(path.exists(), path)
        self.assertEqual(attachments, set())
        self.assertIs(renderer.chat, chat)

    def test_document_skeleton(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: hi", chat_name="Lunch.zip")

        self.render_chat(chat)
        html = self.read_text(self.tmp / "chat.html")

        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn('<meta charset="utf-8">', html)
        self.assertIn("<title>Lunch.zip</title>", html)
        self.assertIn("<h1>Lunch.zip</h1>", html)
        self.assertIn("<style>", html)
        self.assertIn("chat-export", html)
        self.assertIn("https://chat-export.click", html)
        self.assertTrue(html.rstrip().endswith("</html>"))

    def test_title_is_escaped(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: hi", chat_name='Tom & "Jerry" <3.zip')

        self.render_chat(chat)
        html = self.read_text(self.tmp / "chat.html")

        self.assertIn("<title>Tom &amp; &quot;Jerry&quot; &lt;3.zip</title>", html)
        self.assertIn("<h1>Tom &amp; &quot;Jerry&quot; &lt;3.zip</h1>", html)

    def test_both_files_contain_every_message(self):
        text = "\n".join(f"05.02.24, 09:{i:02d} - Lena Voss: message number {i}" for i in range(12))
        chat, _, _ = parse(text)

        self.render_chat(chat)

        for name in ("chat.html", "chat_media_linked.html"):
            html = self.read_text(self.tmp / name)
            self.assertEqual(html.count('<div class="message '), 12, name)
            self.assertIn("message number 11", html)

    def test_no_date_range_paragraph_when_unfiltered(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: hi")

        self.render_chat(chat)

        self.assertNotIn("Filtered:", self.read_text(self.tmp / "chat.html"))

    def test_date_range_paragraph_when_filtered(self):
        date_range = DateRange(from_date=date(2024, 2, 1), until_date=date(2024, 2, 29))
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: hi", date_range=date_range)

        self.render_chat(chat)
        html = self.read_text(self.tmp / "chat.html")

        self.assertIn("Filtered: 01.02.24 to 29.02.24", html)

    def test_unfiltered_date_range_object_adds_nothing(self):
        chat, _, _ = parse("05.02.24, 09:01 - Lena Voss: hi", date_range=DateRange())

        self.render_chat(chat)

        self.assertNotIn("Filtered:", self.read_text(self.tmp / "chat.html"))

    def test_returns_attachments_to_extract(self):
        chat, _, _ = parse(
            "\n".join([
                "05.02.24, 09:01 - Lena Voss: IMG-1.jpg (file attached)",
                "05.02.24, 09:02 - Lena Voss: note.txt (file attached)",
            ]),
            has_media=True,
            attachments={"IMG-1.jpg", "note.txt", "never-mentioned.jpg"},
        )

        _, attachments = self.render_chat(chat)

        self.assertEqual(attachments, {"IMG-1.jpg", "note.txt"})

    def test_own_messages_are_marked_sent(self):
        chat, _, _ = parse(
            "05.02.24, 09:01 - Lena Voss: mine\n05.02.24, 09:02 - Jonas Berg: theirs",
            own_name="Lena Voss",
        )

        self.render_chat(chat)
        html = self.read_text(self.tmp / "chat.html")

        self.assertEqual(html.count('class="message sent'), 1)
        self.assertEqual(html.count('class="message received'), 1)

    def test_embed_mode_writes_single_file_and_no_temp_leftovers(self):
        zip_path = write_zip(self.tmp / "Lunch Club.zip", "Lunch Club.txt", "x", {"pic.jpg": TINY_PNG})
        chat, _, _ = parse(
            "05.02.24, 09:01 - Lena Voss: pic.jpg (file attached)",
            has_media=True,
            attachments={"pic.jpg"},
        )
        out_dir = self.tmp / "out"
        out_dir.mkdir()
        temp_before = set(Path(tempfile.gettempdir()).glob("chat_export_*.tmp"))

        renderer = HTMLRenderer(output_dir=str(out_dir), has_media=True, embed_media=True, zip_path=zip_path)
        with quiet():
            renderer.render(chat)

        self.assertEqual({p.name for p in out_dir.iterdir()}, {"Lunch Club.html"})
        self.assertEqual(set(Path(tempfile.gettempdir()).glob("chat_export_*.tmp")), temp_before)
        html = self.read_text(out_dir / "Lunch Club.html")
        self.assertIn("data:image/jpeg;base64,", html)
        self.assertNotIn("./media/", html)

    def test_unicode_content_round_trips(self):
        chat, _, _ = parse("05.02.24, 09:01 - Élodie Müller: Grüße aus Zürich 🎉 مرحبا")

        self.render_chat(chat)
        html = self.read_text(self.tmp / "chat.html")

        self.assertIn("Élodie Müller", html)
        self.assertIn("Grüße aus Zürich 🎉 مرحبا", html)


if __name__ == "__main__":
    unittest.main()
