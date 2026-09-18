import contextlib
import io
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest import mock

from chat_export.chat_export import Chat, ChatExport

from tests.helpers import (
    ANDROID_MEDIA,
    IOS_MEDIA,
    TINY_PNG,
    TempDirTestCase,
    android_chat_text,
    make_android_zip,
    make_ios_zip,
    quiet,
    write_zip,
)


class ConstructorTest(TempDirTestCase):
    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            ChatExport(str(self.tmp / "nope.zip"))

        self.assertIn("Could not find the file", str(ctx.exception))

    def test_non_zip_extension_raises(self):
        text_file = self.tmp / "chat.txt"
        text_file.write_text("05.02.24, 09:01 - Lena Voss: hi", encoding="utf-8")

        with self.assertRaises(ValueError) as ctx:
            ChatExport(str(text_file))

        self.assertIn("is not a zip file", str(ctx.exception))

    def test_uppercase_zip_extension_is_accepted(self):
        zip_path = make_android_zip(self.tmp, stem="Upper")
        renamed = Path(zip_path).with_suffix(".ZIP")
        Path(zip_path).rename(renamed)

        export = ChatExport(str(renamed))

        self.assertEqual(export.zip_path, str(renamed))

    def test_default_output_dir_is_zip_stem_in_cwd(self):
        zip_path = make_android_zip(self.tmp, stem="Lunch Club")

        export = ChatExport(zip_path)

        self.assertEqual(export.output_dir, Path("Lunch Club"))
        self.assertEqual(Path(export.media_dir), Path("Lunch Club", "media"))

    def test_base_output_dir_gets_stem_subfolder(self):
        zip_path = make_android_zip(self.tmp, stem="Lunch Club")

        export = ChatExport(zip_path, base_output_dir=str(self.tmp / "exports"))

        self.assertEqual(export.output_dir, self.tmp / "exports" / "Lunch Club")
        self.assertEqual(Path(export.media_dir), self.tmp / "exports" / "Lunch Club" / "media")

    def test_quoted_base_output_dir_is_unquoted(self):
        zip_path = make_android_zip(self.tmp, stem="Lunch Club")

        export = ChatExport(zip_path, base_output_dir=f'"{self.tmp / "exports"}"')

        self.assertEqual(export.output_dir, self.tmp / "exports" / "Lunch Club")

    def test_embed_mode_writes_directly_into_base_dir(self):
        zip_path = make_android_zip(self.tmp, stem="Lunch Club")

        export = ChatExport(zip_path, base_output_dir=str(self.tmp / "exports"), embed_media=True)

        self.assertEqual(export.output_dir, self.tmp / "exports")

    def test_embed_mode_without_base_dir_uses_cwd(self):
        zip_path = make_android_zip(self.tmp, stem="Lunch Club")

        export = ChatExport(zip_path, embed_media=True)

        self.assertEqual(export.output_dir, Path(""))

    def test_parameters_are_stored(self):
        zip_path = make_android_zip(self.tmp)

        export = ChatExport(zip_path, from_date="01.02.2024", until_date="29.02.2024", participant_name="Lena Voss")

        self.assertEqual(export.from_date, "01.02.2024")
        self.assertEqual(export.until_date, "29.02.2024")
        self.assertEqual(export.participant_name, "Lena Voss")
        self.assertEqual(export.own_name, "Lena Voss")
        self.assertIsNone(export.parser)
        self.assertIsNone(export.renderer)


class ReadChatFromZipTest(TempDirTestCase):
    def test_android_export_is_detected(self):
        export = ChatExport(make_android_zip(self.tmp))

        with quiet():
            content = export._read_chat_from_zip()

        self.assertFalse(export.is_ios)
        self.assertTrue(export.has_media)
        self.assertEqual(export.attachments_in_zip, set(ANDROID_MEDIA))
        self.assertEqual(content, android_chat_text())

    def test_ios_export_is_detected_by_chat_file_name(self):
        export = ChatExport(make_ios_zip(self.tmp))

        with quiet():
            export._read_chat_from_zip()

        self.assertTrue(export.is_ios)
        self.assertEqual(export.attachments_in_zip, set(IOS_MEDIA))

    def test_export_without_media(self):
        export = ChatExport(make_android_zip(self.tmp, media={}))

        with quiet():
            export._read_chat_from_zip()

        self.assertFalse(export.has_media)
        self.assertEqual(export.attachments_in_zip, set())

    def test_chat_file_is_chosen_by_similarity_to_zip_name(self):
        zip_path = write_zip(
            self.tmp / "WhatsApp Chat with Lunch Club.zip",
            "WhatsApp Chat with Lunch Club.txt",
            "05.02.24, 09:01 - Lena Voss: hi",
            {"shopping list.txt": b"eggs", "IMG-1.jpg": TINY_PNG},
        )
        export = ChatExport(zip_path)

        with quiet():
            content = export._read_chat_from_zip()

        self.assertEqual(content, "05.02.24, 09:01 - Lena Voss: hi")
        self.assertEqual(export.attachments_in_zip, {"shopping list.txt", "IMG-1.jpg"})

    def test_chat_file_with_different_name_still_found(self):
        # Renamed zips are common; the only .txt is the chat regardless of name.
        zip_path = write_zip(self.tmp / "renamed.zip", "Chat with Mira Cole.txt", "05.02.24, 09:01 - Mira Cole: hi")
        export = ChatExport(zip_path)

        with quiet():
            content = export._read_chat_from_zip()

        self.assertEqual(content, "05.02.24, 09:01 - Mira Cole: hi")

    def test_zip_without_text_file_raises(self):
        zip_path = str(self.tmp / "nochat.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("IMG-1.jpg", TINY_PNG)
        export = ChatExport(zip_path)

        with self.assertRaises(FileNotFoundError) as ctx, quiet():
            export._read_chat_from_zip()

        self.assertIn("No .txt file found", str(ctx.exception))

    def test_corrupt_zip_raises_value_error(self):
        bad = self.tmp / "broken.zip"
        bad.write_bytes(b"this is definitely not a zip archive")
        export = ChatExport(str(bad))

        with self.assertRaises(ValueError) as ctx, quiet():
            export._read_chat_from_zip()

        self.assertIn("not a valid ZIP file", str(ctx.exception))

    def test_utf8_bom_and_unicode_are_decoded(self):
        zip_path = write_zip(self.tmp / "u.zip", "u.txt", "05.02.24, 09:01 - Élodie Müller: Grüße")
        export = ChatExport(zip_path)

        with quiet():
            content = export._read_chat_from_zip()

        self.assertIn("Élodie Müller: Grüße", content)

    def test_progress_message_mentions_platform_and_media(self):
        export = ChatExport(make_ios_zip(self.tmp))

        with io.StringIO() as out, contextlib.redirect_stdout(out):
            export._read_chat_from_zip()
            printed = out.getvalue()

        self.assertIn("iOS export with media", printed)
        self.assertIn("'_chat.txt'", printed)


class HelperMethodTest(TempDirTestCase):
    def test_most_similar_picks_closest_candidate(self):
        candidates = ["notes.txt", "WhatsApp Chat with Lunch Club.txt", "readme.txt"]

        self.assertEqual(
            ChatExport.most_similar("WhatsApp Chat with Lunch Club.txt", candidates),
            "WhatsApp Chat with Lunch Club.txt",
        )

    def test_most_similar_with_partial_match(self):
        candidates = ["Lunch.txt", "unrelated.txt"]

        self.assertEqual(ChatExport.most_similar("Lunch Club.txt", candidates), "Lunch.txt")

    def test_validate_participant_accepts_known_name(self):
        export = ChatExport(make_android_zip(self.tmp))

        self.assertTrue(export.validate_participant("Lena Voss", ["Jonas Berg", "Lena Voss"]))

    def test_validate_participant_rejects_unknown_name_and_lists_options(self):
        export = ChatExport(make_android_zip(self.tmp))

        with io.StringIO() as out, contextlib.redirect_stdout(out):
            with self.assertRaises(ValueError) as ctx:
                export.validate_participant("lena voss", ["Jonas Berg", "Lena Voss"])
            printed = out.getvalue()

        self.assertIn("'lena voss' not found", str(ctx.exception))
        self.assertIn("Jonas Berg, Lena Voss", str(ctx.exception))
        self.assertIn("1. Jonas Berg", printed)
        self.assertIn("2. Lena Voss", printed)

    def test_parse_date_input_delegates_to_date_range(self):
        export = ChatExport(make_android_zip(self.tmp))

        self.assertEqual(export.parse_date_input("05.02.2024"), date(2024, 2, 5))
        self.assertIsNone(export.parse_date_input(""))

    def test_setup_modular_components(self):
        export = ChatExport(make_android_zip(self.tmp), base_output_dir=str(self.tmp))
        with quiet():
            export._read_chat_from_zip()

        export.setup_modular_components()

        self.assertTrue(export.parser.has_media)
        self.assertFalse(export.parser.is_ios)
        self.assertEqual(export.parser.attachments_in_zip, set(ANDROID_MEDIA))
        self.assertEqual(export.renderer.output_dir, export.output_dir)
        self.assertEqual(export.renderer.zip_path, export.zip_path)


class NonInteractiveAndroidExportTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.zip_path = make_android_zip(self.tmp)
        self.out_base = self.tmp / "out"

    def run_export(self, **kwargs):
        params = dict(participant_name="Lena Voss", base_output_dir=str(self.out_base))
        params.update(kwargs)
        export = ChatExport(self.zip_path, **params)
        with quiet():
            chat = export.process_chat_non_interactive()
        return export, chat

    def test_creates_html_files_and_media_folder(self):
        export, chat = self.run_export()
        out_dir = self.out_base / "WhatsApp Chat with Lunch Club"

        self.assertTrue((out_dir / "chat.html").is_file())
        self.assertTrue((out_dir / "chat_media_linked.html").is_file())
        self.assertEqual(
            {p.name for p in (out_dir / "media").iterdir()},
            set(ANDROID_MEDIA),
        )
        self.assertEqual([p.name for p in export.renderer.get_generated_files()], ["chat.html", "chat_media_linked.html"])

    def test_returns_chat_object(self):
        _, chat = self.run_export()

        self.assertIsInstance(chat, Chat)
        self.assertEqual(chat.name, "WhatsApp Chat with Lunch Club.zip")
        self.assertEqual(chat.own_name, "Lena Voss")
        self.assertEqual(len(chat.messages), 11)

    def test_extracted_media_matches_zip_bytes(self):
        self.run_export()
        media_dir = self.out_base / "WhatsApp Chat with Lunch Club" / "media"

        self.assertEqual((media_dir / "IMG-20240205-WA0001.jpg").read_bytes(), TINY_PNG)

    def test_html_content(self):
        self.run_export()
        html = self.read_text(self.out_base / "WhatsApp Chat with Lunch Club" / "chat.html")

        self.assertIn("<title>WhatsApp Chat with Lunch Club.zip</title>", html)
        self.assertIn('<img class="media" src="./media/IMG-20240205-WA0001.jpg">', html)
        self.assertIn('<a href="./media/agenda.pdf">📎 agenda.pdf</a>', html)
        self.assertIn('<a href="https://example.org/menu?day=tue" target="_blank">', html)
        self.assertIn("[call (attempt)]", html)
        self.assertIn("[Media omitted]", html)
        self.assertIn("Looks tasty<br>second line of Mira's message<br>third line", html)
        self.assertIn('class="message whatsapp', html)
        self.assertEqual(html.count('class="message sent'), 4)

    def test_media_linked_html_has_no_inline_media(self):
        self.run_export()
        html = self.read_text(self.out_base / "WhatsApp Chat with Lunch Club" / "chat_media_linked.html")

        self.assertNotIn("<img", html)
        self.assertNotIn("<video", html)
        self.assertIn('<a href="./media/IMG-20240205-WA0001.jpg">📎 IMG-20240205-WA0001.jpg</a>', html)

    def test_other_participant_as_own_name(self):
        _, chat = self.run_export(participant_name="Jonas Berg")
        html = self.read_text(self.out_base / "WhatsApp Chat with Lunch Club" / "chat.html")

        self.assertEqual(chat.sender_color_map["Jonas Berg"], "#d9fdd3")
        self.assertEqual(html.count('class="message sent'), 3)

    def test_unknown_participant_raises_before_writing(self):
        with self.assertRaises(ValueError):
            self.run_export(participant_name="Nobody Here")

        self.assertFalse(self.out_base.exists())

    def test_date_filter_limits_messages_and_media(self):
        _, chat = self.run_export(from_date="06.02.2024", until_date="07.02.2024")
        out_dir = self.out_base / "WhatsApp Chat with Lunch Club"
        html = self.read_text(out_dir / "chat.html")

        self.assertEqual(len(chat.messages), 4)
        self.assertIn("Filtered: 06.02.24 to 07.02.24", html)
        self.assertEqual({p.name for p in (out_dir / "media").iterdir()}, {"VID-20240206-WA0002.mp4"})

    def test_date_filter_accepts_us_format(self):
        _, chat = self.run_export(from_date="02/08/2024")

        self.assertEqual(len(chat.messages), 2)

    def test_from_date_only(self):
        _, chat = self.run_export(from_date="08.02.2024")

        self.assertEqual([m.parsed_date for m in chat.messages], [date(2024, 2, 8)] * 2)

    def test_until_date_only(self):
        _, chat = self.run_export(until_date="05.02.2024")

        self.assertEqual(len(chat.messages), 5)

    def test_invalid_from_date_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.run_export(from_date="2024-02-06")

        self.assertIn("Invalid from-date format", str(ctx.exception))

    def test_invalid_until_date_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.run_export(until_date="soon")

        self.assertIn("Invalid until-date format", str(ctx.exception))

    def test_reversed_date_range_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.run_export(from_date="07.02.2024", until_date="06.02.2024")

        self.assertIn("'From' date must be before 'until' date", str(ctx.exception))

    def test_empty_date_range_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.run_export(from_date="01.01.2030")

        self.assertIn("No messages found in the specified date range", str(ctx.exception))
        self.assertFalse(self.out_base.exists())

    def test_rerun_replaces_previous_export(self):
        self.run_export()
        out_dir = self.out_base / "WhatsApp Chat with Lunch Club"
        stale = out_dir / "media" / "stale-file.jpg"
        stale.write_bytes(b"old")

        self.run_export(from_date="08.02.2024")

        self.assertFalse(stale.exists())
        self.assertEqual({p.name for p in (out_dir / "media").iterdir()}, {"agenda.pdf"})

    def test_refuses_to_replace_folder_with_foreign_files(self):
        out_dir = self.out_base / "WhatsApp Chat with Lunch Club"
        out_dir.mkdir(parents=True)
        keep = out_dir / "my-thesis.docx"
        keep.write_bytes(b"precious")

        with self.assertRaises(ValueError) as ctx:
            self.run_export()

        self.assertIn("Refusing to delete", str(ctx.exception))
        self.assertTrue(keep.exists())

    def test_refuses_when_output_path_is_a_file(self):
        self.out_base.mkdir()
        (self.out_base / "WhatsApp Chat with Lunch Club").write_text("not a folder", encoding="utf-8")

        with self.assertRaises(ValueError) as ctx:
            self.run_export()

        self.assertIn("already exists", str(ctx.exception))

    def test_existing_empty_output_folder_is_fine(self):
        (self.out_base / "WhatsApp Chat with Lunch Club").mkdir(parents=True)

        self.run_export()

        self.assertTrue((self.out_base / "WhatsApp Chat with Lunch Club" / "chat.html").exists())

    def test_default_output_dir_is_relative_to_cwd(self):
        self.chdir_tmp()
        export = ChatExport(self.zip_path, participant_name="Lena Voss")

        with quiet():
            export.process_chat_non_interactive()

        self.assertTrue((self.tmp / "WhatsApp Chat with Lunch Club" / "chat.html").exists())

    def test_export_ending_with_crlf_newline_renders_last_message_cleanly(self):
        # Real exports end with a newline and iOS ones often use CRLF; neither
        # may leak into the last message as a trailing line break.
        text = android_chat_text().replace("\n", "\r\n") + "\r\n"
        zip_path = make_android_zip(self.tmp, stem="CRLF Export", chat_text=text)
        export = ChatExport(zip_path, participant_name="Lena Voss", base_output_dir=str(self.out_base))

        with quiet():
            chat = export.process_chat_non_interactive()

        html = self.read_text(self.out_base / "CRLF Export" / "chat.html")
        self.assertEqual(chat.messages[-1].cleaned_content, "[Media omitted]")
        self.assertIn('<div class="content">[Media omitted]</div>', html)
        self.assertNotIn("[Media omitted]<br>", html)
        self.assertIn("Looks tasty", html)
        self.assertIn("third line", html)

    def test_zip_without_media_has_no_media_dir(self):
        zip_path = make_android_zip(self.tmp, stem="Text Only", media={})
        export = ChatExport(zip_path, participant_name="Lena Voss", base_output_dir=str(self.out_base))

        with quiet():
            export.process_chat_non_interactive()

        out_dir = self.out_base / "Text Only"
        self.assertTrue((out_dir / "chat.html").exists())
        self.assertFalse((out_dir / "media").exists())
        html = self.read_text(out_dir / "chat.html")
        self.assertIn("IMG-20240205-WA0001.jpg (file attached)", html)


class NonInteractiveEmbedExportTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.zip_path = make_android_zip(self.tmp)
        self.out_base = self.tmp / "out"

    def run_export(self, **kwargs):
        params = dict(participant_name="Lena Voss", base_output_dir=str(self.out_base), embed_media=True)
        params.update(kwargs)
        export = ChatExport(self.zip_path, **params)
        with quiet():
            chat = export.process_chat_non_interactive()
        return export, chat

    def test_single_self_contained_file(self):
        export, _ = self.run_export()

        self.assertEqual({p.name for p in self.out_base.iterdir()}, {"WhatsApp Chat with Lunch Club.html"})
        self.assertEqual(export.renderer.get_generated_files(), [self.out_base / "WhatsApp Chat with Lunch Club.html"])

    def test_media_is_embedded(self):
        self.run_export()
        html = self.read_text(self.out_base / "WhatsApp Chat with Lunch Club.html")

        self.assertIn("data:image/jpeg;base64,", html)
        self.assertIn("data:video/mp4;base64,", html)
        self.assertIn('download="agenda.pdf"', html)
        self.assertNotIn("./media/", html)

    def test_no_media_folder_is_created(self):
        self.run_export()

        self.assertFalse((self.out_base / "media").exists())
        self.assertFalse((self.out_base / "WhatsApp Chat with Lunch Club").exists())

    def test_rerun_overwrites_file_without_complaint(self):
        self.run_export()
        (self.out_base / "unrelated.txt").write_text("keep me", encoding="utf-8")

        self.run_export(from_date="08.02.2024")

        self.assertTrue((self.out_base / "unrelated.txt").exists())
        html = self.read_text(self.out_base / "WhatsApp Chat with Lunch Club.html")
        self.assertIn("Filtered: 08.02.24 to end", html)

    def test_embed_into_cwd_when_no_base_dir(self):
        self.chdir_tmp()
        export = ChatExport(self.zip_path, participant_name="Lena Voss", embed_media=True)

        with quiet():
            export.process_chat_non_interactive()

        self.assertTrue((self.tmp / "WhatsApp Chat with Lunch Club.html").exists())


class NonInteractiveIOSExportTest(TempDirTestCase):
    def test_ios_export_end_to_end(self):
        zip_path = make_ios_zip(self.tmp)
        out_base = self.tmp / "out"
        export = ChatExport(zip_path, participant_name="Priya Nair", base_output_dir=str(out_base))

        with quiet():
            chat = export.process_chat_non_interactive()

        out_dir = out_base / "WhatsApp Chat - Tariq Haddad"
        html = self.read_text(out_dir / "chat.html")
        self.assertTrue(export.is_ios)
        self.assertEqual(chat.senders, ["Priya Nair", "Tariq Haddad"])
        self.assertEqual(len(chat.messages), 6)
        self.assertNotIn("‎", html)
        self.assertIn('<img class="media" src="./media/00000003-PHOTO-2024-02-05-09-03-30.jpg">', html)
        self.assertIn('type="audio/ogg"', html)
        self.assertIn("Great song<br>and a second line", html)
        self.assertEqual({p.name for p in (out_dir / "media").iterdir()}, set(IOS_MEDIA))

    def test_ios_participant_name_with_marks_in_export_still_matches(self):
        text = "\n".join([
            "‎[05.02.24, 09:01:10] ‎Tariq Haddad‎: hi",
            "[05.02.24, 09:02:20] Priya Nair: hello",
        ])
        zip_path = make_ios_zip(self.tmp, chat_text=text, media={})
        export = ChatExport(zip_path, participant_name="Tariq Haddad", base_output_dir=str(self.tmp / "out"))

        with quiet():
            chat = export.process_chat_non_interactive()

        self.assertEqual(chat.messages[0].sender, "Tariq Haddad")


class OutputDirectorySafetyTest(TempDirTestCase):
    def make_export(self, embed_media=False):
        zip_path = make_android_zip(self.tmp, stem="Lunch Club")
        return ChatExport(zip_path, base_output_dir=str(self.tmp / "out"), embed_media=embed_media)

    def test_filesystem_root_is_protected(self):
        root = Path(self.tmp.anchor)

        self.assertTrue(ChatExport._is_protected_path(root))

    def test_home_and_cwd_are_protected(self):
        self.assertTrue(ChatExport._is_protected_path(Path.home()))
        self.assertTrue(ChatExport._is_protected_path(Path.cwd()))
        self.assertTrue(ChatExport._is_protected_path(Path(".")))

    def test_ordinary_folder_is_not_protected(self):
        self.assertFalse(ChatExport._is_protected_path(self.tmp / "somewhere"))
        self.assertFalse(ChatExport._is_protected_path(self.tmp))

    def test_nonexistent_folder_is_not_replaceable(self):
        export = self.make_export()

        self.assertFalse(export._is_replaceable_export_dir(self.tmp / "out" / "Lunch Club", "Lunch Club"))

    def test_name_must_match_zip_stem_exactly(self):
        export = self.make_export()
        folder = self.tmp / "My Lunch Club"
        folder.mkdir()
        (folder / "chat.html").write_text("", encoding="utf-8")

        self.assertFalse(export._is_replaceable_export_dir(folder, "Lunch Club"))

    def test_previous_export_folder_is_replaceable(self):
        export = self.make_export()
        folder = self.tmp / "Lunch Club"
        (folder / "media").mkdir(parents=True)
        (folder / "chat.html").write_text("", encoding="utf-8")
        (folder / "chat_media_linked.html").write_text("", encoding="utf-8")

        self.assertTrue(export._is_replaceable_export_dir(folder, "Lunch Club"))

    def test_os_metadata_files_are_ignored(self):
        export = self.make_export()
        folder = self.tmp / "Lunch Club"
        folder.mkdir()
        (folder / "chat.html").write_text("", encoding="utf-8")
        for name in (".DS_Store", "Thumbs.db", "desktop.ini"):
            (folder / name).write_bytes(b"")

        self.assertTrue(export._is_replaceable_export_dir(folder, "Lunch Club"))

    def test_foreign_file_blocks_replacement(self):
        export = self.make_export()
        folder = self.tmp / "Lunch Club"
        folder.mkdir()
        (folder / "chat.html").write_text("", encoding="utf-8")
        (folder / "photo-backup.jpg").write_bytes(b"")

        self.assertFalse(export._is_replaceable_export_dir(folder, "Lunch Club"))

    def test_file_instead_of_folder_is_not_replaceable(self):
        export = self.make_export()
        path = self.tmp / "Lunch Club"
        path.write_text("", encoding="utf-8")

        self.assertFalse(export._is_replaceable_export_dir(path, "Lunch Club"))

    def test_embed_mode_never_replaces(self):
        export = self.make_export(embed_media=True)
        folder = self.tmp / "Lunch Club"
        folder.mkdir()
        (folder / "chat.html").write_text("", encoding="utf-8")

        self.assertFalse(export._is_replaceable_export_dir(folder, "Lunch Club"))

    def test_protected_folder_is_never_replaced_even_if_it_looks_like_an_export(self):
        export = self.make_export()
        with mock.patch.object(ChatExport, "_is_protected_path", return_value=True):
            folder = self.tmp / "Lunch Club"
            folder.mkdir()
            (folder / "chat.html").write_text("", encoding="utf-8")

            self.assertFalse(export._is_replaceable_export_dir(folder, "Lunch Club"))

    def test_prepare_creates_media_dir_only_when_needed(self):
        export = self.make_export()
        export.has_media = False

        export._prepare_output_directories()

        self.assertTrue(export.output_dir.is_dir())
        self.assertFalse(Path(export.media_dir).exists())

        export.has_media = True
        with quiet():
            export._prepare_output_directories()

        self.assertTrue(Path(export.media_dir).is_dir())

    def test_prepare_refuses_protected_output_dir(self):
        export = self.make_export()
        export.output_dir = self.tmp
        with mock.patch.object(ChatExport, "_is_protected_path", return_value=True):
            with self.assertRaises(ValueError):
                export._prepare_output_directories()


class InteractiveProcessChatTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.zip_path = make_android_zip(self.tmp)
        self.out_base = self.tmp / "out"

    def run_interactive(self, inputs):
        export = ChatExport(self.zip_path, base_output_dir=str(self.out_base))
        with mock.patch("builtins.input", side_effect=inputs), io.StringIO() as out, contextlib.redirect_stdout(out):
            export.process_chat()
            printed = out.getvalue()
        return export, printed

    def test_picks_participant_by_number(self):
        export, printed = self.run_interactive(["", "", "2"])

        self.assertEqual(export.own_name, "Lena Voss")
        self.assertIn("1. Jonas Berg", printed)
        self.assertIn("2. Lena Voss", printed)
        self.assertIn("3. Mira Cole", printed)
        self.assertTrue((self.out_base / "WhatsApp Chat with Lunch Club" / "chat.html").exists())

    def test_invalid_inputs_are_retried(self):
        inputs = [
            "bogus",       # from date: invalid
            "y",           # try again
            "06.02.2024",  # from date: valid
            "",            # until date: skip
            "abc",         # participant: not a number
            "9",           # participant: out of range
            "3",           # participant: Mira Cole
        ]

        export, printed = self.run_interactive(inputs)

        self.assertEqual(export.from_date, date(2024, 2, 6))
        self.assertEqual(export.own_name, "Mira Cole")
        self.assertIn("Please enter a valid number.", printed)
        self.assertIn("Invalid choice", printed)
        self.assertIn("messages match date range filter", printed)

    def test_giving_up_on_bad_date_skips_filter(self):
        export, _ = self.run_interactive(["bogus", "n", "", "1"])

        self.assertIsNone(export.from_date)
        self.assertEqual(export.own_name, "Jonas Berg")

    def test_until_before_from_is_rejected(self):
        export, printed = self.run_interactive(["07.02.2024", "06.02.2024", "y", "08.02.2024", "1"])

        self.assertIn("'From' date must be before 'until' date", printed)
        self.assertEqual(export.until_date, date(2024, 2, 8))


if __name__ == "__main__":
    unittest.main()
