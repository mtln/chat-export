import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

from chat_export import chat_export as module
from chat_export.chat_export import main, open_html_file_in_browser, parse_arguments, parse_path

from tests.helpers import TempDirTestCase, make_android_zip


def run_parser(*argv):
    with mock.patch.object(sys, "argv", ["chat-export", *argv]):
        return parse_arguments()


def run_main(*argv):
    """Run main() with the given argv, returning (exit_code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    exit_code = None
    with mock.patch.object(sys, "argv", ["chat-export", *argv]):
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                main()
            except SystemExit as exc:
                exit_code = exc.code
    return exit_code, out.getvalue(), err.getvalue()


class ParseArgumentsTest(unittest.TestCase):
    def test_defaults(self):
        args = run_parser()

        self.assertFalse(args.non_interactive)
        self.assertIsNone(args.zip_file)
        self.assertIsNone(args.participant)
        self.assertIsNone(args.from_date)
        self.assertIsNone(args.until_date)
        self.assertIsNone(args.output_dir)
        self.assertFalse(args.embed_media)

    def test_short_options(self):
        args = run_parser("-n", "-z", "chat.zip", "-p", "Lena Voss", "-o", "out")

        self.assertTrue(args.non_interactive)
        self.assertEqual(args.zip_file, "chat.zip")
        self.assertEqual(args.participant, "Lena Voss")
        self.assertEqual(args.output_dir, "out")

    def test_long_options(self):
        args = run_parser(
            "--non-interactive",
            "--zip-file", "chat.zip",
            "--participant", "Lena Voss",
            "--from-date", "01.02.2024",
            "--until-date", "29.02.2024",
            "--output-dir", "out",
            "--embed-media",
        )

        self.assertTrue(args.non_interactive)
        self.assertEqual(args.from_date, "01.02.2024")
        self.assertEqual(args.until_date, "29.02.2024")
        self.assertTrue(args.embed_media)

    def test_interactive_mode_accepts_output_options_only(self):
        args = run_parser("--embed-media", "-o", "out")

        self.assertFalse(args.non_interactive)
        self.assertTrue(args.embed_media)
        self.assertEqual(args.output_dir, "out")

    def test_non_interactive_requires_zip_file(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit) as ctx:
                run_parser("-n", "-p", "Lena Voss")

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--zip-file", err.getvalue())

    def test_non_interactive_requires_participant(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit) as ctx:
                run_parser("-n", "-z", "chat.zip")

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn("--participant", err.getvalue())

    def test_unknown_option_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                run_parser("--bogus")

    def test_help_exits_cleanly(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(SystemExit) as ctx:
                run_parser("--help")

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("--embed-media", out.getvalue())
        self.assertIn("--from-date", out.getvalue())


class ParsePathTest(unittest.TestCase):
    def test_double_quotes_are_stripped(self):
        self.assertEqual(parse_path('"/exports/chat.zip"').name, "chat.zip")

    def test_single_quotes_are_stripped(self):
        self.assertEqual(parse_path("'/exports/chat.zip'").name, "chat.zip")

    def test_posix_path(self):
        path = parse_path("/home/lena/exports/chat.zip")

        self.assertIsInstance(path, Path)
        self.assertEqual(path.name, "chat.zip")
        self.assertEqual(path.parts[-2], "exports")

    def test_windows_path(self):
        path = parse_path(r"C:\Users\lena\exports\chat.zip")

        self.assertIsInstance(path, Path)
        self.assertEqual(path.name, "chat.zip")
        self.assertIn("exports", path.parts)

    def test_relative_path(self):
        self.assertEqual(parse_path("exports/chat.zip").parts, ("exports", "chat.zip"))

    @unittest.skipUnless(sys.platform == "win32", "Windows path rendering")
    def test_windows_path_rendering_on_windows(self):
        self.assertEqual(str(parse_path(r'"C:\Users\lena\chat.zip"')), r"C:\Users\lena\chat.zip")


class OpenInBrowserTest(unittest.TestCase):
    def test_opens_file_url(self):
        with mock.patch.object(module.webbrowser, "open") as opened:
            open_html_file_in_browser(Path("some dir") / "chat.html")

        url = opened.call_args[0][0]
        self.assertTrue(url.startswith("file://"))
        self.assertTrue(url.endswith("/some dir/chat.html"))
        self.assertNotIn("\\", url)


class MainNonInteractiveTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.zip_path = make_android_zip(self.tmp)
        self.out_base = self.tmp / "out"

    def test_successful_run(self):
        exit_code, out, _ = run_main("-n", "-z", self.zip_path, "-p", "Lena Voss", "-o", str(self.out_base))

        self.assertIsNone(exit_code)
        self.assertIn("Non-interactive mode", out)
        self.assertIn("Written:", out)
        self.assertIn("chat.html", out)
        self.assertIn("Done.", out)
        self.assertTrue((self.out_base / "WhatsApp Chat with Lunch Club" / "chat.html").exists())

    def test_embed_media_flag(self):
        exit_code, _, _ = run_main("-n", "-z", self.zip_path, "-p", "Lena Voss", "-o", str(self.out_base), "--embed-media")

        self.assertIsNone(exit_code)
        self.assertEqual({p.name for p in self.out_base.iterdir()}, {"WhatsApp Chat with Lunch Club.html"})

    def test_date_filters_are_passed_through(self):
        exit_code, out, _ = run_main(
            "-n", "-z", self.zip_path, "-p", "Lena Voss", "-o", str(self.out_base),
            "--from-date", "06.02.2024", "--until-date", "07.02.2024",
        )

        self.assertIsNone(exit_code)
        self.assertIn("4 of 11 messages match date range filter.", out)

    def test_missing_zip_exits_with_error(self):
        exit_code, out, _ = run_main("-n", "-z", str(self.tmp / "missing.zip"), "-p", "Lena Voss")

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: Could not find the file", out)

    def test_unknown_participant_exits_with_error(self):
        exit_code, out, _ = run_main("-n", "-z", self.zip_path, "-p", "Nobody", "-o", str(self.out_base))

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: Participant 'Nobody' not found", out)
        self.assertIn("1. Jonas Berg", out)

    def test_bad_date_exits_with_error(self):
        exit_code, out, _ = run_main("-n", "-z", self.zip_path, "-p", "Lena Voss", "-o", str(self.out_base), "--from-date", "never")

        self.assertEqual(exit_code, 1)
        self.assertIn("Invalid from-date format", out)

    def test_unexpected_exception_exits_with_traceback(self):
        with mock.patch.object(module.ChatExport, "process_chat_non_interactive", side_effect=RuntimeError("boom")):
            exit_code, out, _ = run_main("-n", "-z", self.zip_path, "-p", "Lena Voss", "-o", str(self.out_base))

        self.assertEqual(exit_code, 1)
        self.assertIn("An unexpected error occurred: boom", out)
        self.assertIn("Traceback", out)


class MainInteractiveTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.zip_path = make_android_zip(self.tmp)
        self.out_base = self.tmp / "out"

    def run_interactive(self, selected_file, inputs, *argv):
        with mock.patch.object(module, "browse_zip_file", return_value=selected_file), \
             mock.patch("builtins.input", side_effect=inputs) as fake_input, \
             mock.patch.object(module.webbrowser, "open") as opened:
            exit_code, out, err = run_main(*argv)
        return exit_code, out, fake_input, opened

    def test_no_file_selected(self):
        exit_code, out, fake_input, opened = self.run_interactive(None, [""])

        self.assertIsNone(exit_code)
        self.assertIn("Welcome to chat-export", out)
        self.assertIn("Error: No file selected.", out)
        self.assertIn("Press enter to exit", out)
        self.assertEqual(fake_input.call_count, 1)
        opened.assert_not_called()

    def test_full_run_without_opening_browser(self):
        inputs = ["", "", "2", "n", "n"]

        exit_code, out, fake_input, opened = self.run_interactive(self.zip_path, inputs, "-o", str(self.out_base))

        self.assertIsNone(exit_code)
        self.assertIn("Written:", out)
        self.assertIn("Done.", out)
        self.assertTrue((self.out_base / "WhatsApp Chat with Lunch Club" / "chat.html").exists())
        self.assertEqual(fake_input.call_count, 5)
        opened.assert_not_called()

    def test_enter_opens_both_files_in_browser(self):
        inputs = ["", "", "1", "", "n"]

        _, _, _, opened = self.run_interactive(self.zip_path, inputs, "-o", str(self.out_base))

        self.assertEqual(opened.call_count, 2)
        urls = [call.args[0] for call in opened.call_args_list]
        self.assertTrue(urls[0].endswith("chat_media_linked.html"))
        self.assertTrue(urls[1].endswith("chat.html"))

    def test_donation_prompt_opens_link(self):
        inputs = ["", "", "1", "n", "y"]

        _, _, _, opened = self.run_interactive(self.zip_path, inputs, "-o", str(self.out_base))

        opened.assert_called_once_with(module.donate_link)

    def test_embed_flag_in_interactive_mode(self):
        inputs = ["", "", "1", "n", "n"]

        _, _, _, _ = self.run_interactive(self.zip_path, inputs, "-o", str(self.out_base), "--embed-media")

        self.assertEqual({p.name for p in self.out_base.iterdir()}, {"WhatsApp Chat with Lunch Club.html"})

    def test_processing_error_waits_for_enter(self):
        bad_zip = self.tmp / "broken.zip"
        bad_zip.write_bytes(b"not a zip")

        exit_code, out, fake_input, _ = self.run_interactive(str(bad_zip), ["", "", ""])

        self.assertIsNone(exit_code)
        self.assertIn("Error:", out)
        self.assertIn("not a valid ZIP file", out)
        self.assertIn("Press enter to exit", out)


class BrowseZipFileFallbackTest(unittest.TestCase):
    def test_prompt_fallback_when_no_dialog_available(self):
        with mock.patch.object(module, "pyobjc_available", False), \
             mock.patch.object(module, "pywin32_available", False), \
             mock.patch.object(module, "check_tkinter_availability", return_value=False), \
             mock.patch("builtins.input", return_value="  /exports/chat.zip  "):
            self.assertEqual(module.browse_zip_file(), "/exports/chat.zip")

    def test_prompt_fallback_empty_input_returns_none(self):
        with mock.patch.object(module, "pyobjc_available", False), \
             mock.patch.object(module, "pywin32_available", False), \
             mock.patch.object(module, "check_tkinter_availability", return_value=False), \
             mock.patch("builtins.input", return_value=""):
            self.assertIsNone(module.browse_zip_file())

    @unittest.skipUnless(sys.platform == "win32", "native Windows picker")
    def test_windows_picker_is_used_when_available(self):
        with mock.patch.object(module, "pywin32_available", True), \
             mock.patch.object(module, "windows_file_picker", return_value="C:/picked.zip") as picker:
            self.assertEqual(module.browse_zip_file(), "C:/picked.zip")
        picker.assert_called_once()

    @unittest.skipUnless(sys.platform == "darwin", "native macOS picker")
    def test_macos_picker_is_used_when_available(self):
        with mock.patch.object(module, "pyobjc_available", True), \
             mock.patch.object(module, "macos_file_picker", return_value="/picked.zip") as picker:
            self.assertEqual(module.browse_zip_file(), "/picked.zip")
        picker.assert_called_once()


if __name__ == "__main__":
    unittest.main()
