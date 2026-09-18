import re
import unittest
from pathlib import Path

import chat_export
from chat_export import chat_export as module


PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


class VersionTest(unittest.TestCase):
    def test_hardcoded_version_matches_pyproject(self):
        match = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(encoding="utf-8"), re.MULTILINE)

        self.assertIsNotNone(match, "pyproject.toml has no version line")
        self.assertEqual(module.VERSION, match.group(1))

    def test_dunder_version_looks_like_a_version(self):
        self.assertRegex(module.__version__, r"^\d+\.\d+\.\d+")

    def test_package_reexports_version(self):
        self.assertEqual(chat_export.__version__, module.__version__)


class PublicApiTest(unittest.TestCase):
    def test_all_names_are_importable(self):
        for name in chat_export.__all__:
            with self.subTest(name=name):
                self.assertTrue(hasattr(chat_export, name))
                self.assertIs(getattr(chat_export, name), getattr(module, name))

    def test_expected_public_names(self):
        self.assertEqual(
            set(chat_export.__all__),
            {"ChatExport", "Message", "Chat", "HTMLRenderer", "MessageParser", "DateRange", "__version__"},
        )

    def test_console_script_entry_point_exists(self):
        self.assertTrue(callable(module.main))

    def test_donate_link_is_https(self):
        self.assertTrue(module.donate_link.startswith("https://"))


if __name__ == "__main__":
    unittest.main()
