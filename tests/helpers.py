"""Shared helpers for building fictional WhatsApp export fixtures.

Everything in here is synthetic. Names, phone numbers, message texts and
media bytes are invented for the tests and do not come from real chats.

This module is deliberately not named ``test_*`` so the unittest discovery
does not try to run it as a test module.
"""

import contextlib
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from chat_export.chat_export import Chat, DateRange, Message, MessageParser


# A tiny but valid 1x1 PNG so "image" attachments are real image bytes.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c636000010000050001a5f645400000000049454e44ae426082"
)

# Some invented binary payloads for non-image media types.
FAKE_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32
FAKE_OPUS = b"OggS" + b"\x00" * 40
FAKE_PDF = b"%PDF-1.4\n%fake\n%%EOF\n"


ANDROID_CHAT_LINES = [
    "05.02.24, 09:00 - Messages and calls are end-to-end encrypted. No one outside of this chat can read them.",
    "05.02.24, 09:01 - Lena Voss: Good morning everyone",
    "05.02.24, 09:02 - Jonas Berg: Morning! Coffee later?",
    "05.02.24, 09:03 - Lena Voss: IMG-20240205-WA0001.jpg (file attached)",
    "05.02.24, 09:04 - Mira Cole: Looks tasty",
    "second line of Mira's message",
    "third line",
    "06.02.24, 18:30 - Jonas Berg: VID-20240206-WA0002.mp4 (file attached)",
    "06.02.24, 18:31 - Mira Cole: Check https://example.org/menu?day=tue before we go",
    "07.02.24, 07:15 - Lena Voss: null",
    "07.02.24, 07:16 - Jonas Berg: Missed your call, sorry!",
    "08.02.24, 12:00 - Mira Cole: agenda.pdf (file attached)",
    "08.02.24, 12:01 - Lena Voss: <Media omitted>",
]

ANDROID_MEDIA = {
    "IMG-20240205-WA0001.jpg": TINY_PNG,
    "VID-20240206-WA0002.mp4": FAKE_MP4,
    "agenda.pdf": FAKE_PDF,
}

IOS_CHAT_LINES = [
    "‎[05.02.24, 09:00:00] Tariq Haddad: ‎Messages and calls are end-to-end encrypted.",
    "[05.02.24, 09:01:10] Tariq Haddad: Hey Priya, are we still on for Friday?",
    "[05.02.24, 09:02:20] Priya Nair: Yes! Bringing the board games",
    "‎[05.02.24, 09:03:30] Priya Nair: ‎<attached: 00000003-PHOTO-2024-02-05-09-03-30.jpg>",
    "‎[06.02.24, 20:15:00] Tariq Haddad: ‎<attached: 00000004-AUDIO-2024-02-06-20-15-00.opus>",
    "[06.02.24, 20:16:00] Priya Nair: Great song",
    "and a second line",
]

IOS_MEDIA = {
    "00000003-PHOTO-2024-02-05-09-03-30.jpg": TINY_PNG,
    "00000004-AUDIO-2024-02-06-20-15-00.opus": FAKE_OPUS,
}


def android_chat_text():
    return "\n".join(ANDROID_CHAT_LINES)


def ios_chat_text():
    return "\n".join(IOS_CHAT_LINES)


def write_zip(zip_path, chat_filename, chat_text, media=None):
    """Write a WhatsApp-style export ZIP and return its path as a string."""
    zip_path = Path(zip_path)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(chat_filename, chat_text.encode("utf-8"))
        for name, data in (media or {}).items():
            zf.writestr(name, data)
    return str(zip_path)


def make_android_zip(directory, stem="WhatsApp Chat with Lunch Club", chat_text=None, media=None):
    """Android exports name the chat file after the ZIP stem."""
    if chat_text is None:
        chat_text = android_chat_text()
    if media is None:
        media = ANDROID_MEDIA
    return write_zip(Path(directory, stem + ".zip"), stem + ".txt", chat_text, media)


def make_ios_zip(directory, stem="WhatsApp Chat - Tariq Haddad", chat_text=None, media=None):
    """iOS exports always use ``_chat.txt`` as the chat file name."""
    if chat_text is None:
        chat_text = ios_chat_text()
    if media is None:
        media = IOS_MEDIA
    return write_zip(Path(directory, stem + ".zip"), "_chat.txt", chat_text, media)


def make_chat(**overrides):
    """Build a bare Chat object with sensible defaults for unit tests."""
    values = dict(
        name="Fixture Chat",
        is_ios=False,
        has_media=False,
        attachments_in_zip=frozenset(),
        message_date_format="%d.%m.%y",
        newline_marker=" $NEWLINE$ ",
        messages=[],
        senders=[],
        date_range=None,
        sender_color_map={},
        own_name="",
    )
    values.update(overrides)
    return Chat(**values)


def make_message(chat=None, id=1, timestamp="05.02.24, 09:01", sender="Lena Voss", content="Hello"):
    """Create a Message through the same factory the parser uses."""
    if chat is None:
        chat = make_chat()
    return Message.create_with_context(id=id, timestamp=timestamp, sender=sender, content=content, chat=chat)


def parse(chat_text, is_ios=False, has_media=False, attachments=None, **kwargs):
    """Parse chat text and return (chat, filtered_count, total_count)."""
    parser = MessageParser(is_ios=is_ios, has_media=has_media, attachments_in_zip=set(attachments or ()))
    return parser.parse_messages(chat_text, **kwargs)


@contextlib.contextmanager
def quiet():
    """Silence stdout for code paths that print progress messages."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield


class TempDirTestCase(unittest.TestCase):
    """Base class that gives every test a fresh temporary directory.

    ``self.tmp`` is a Path to the directory. Use ``self.chdir_tmp()`` for
    code paths that write relative to the current working directory.
    """

    def setUp(self):
        super().setUp()
        self._tmp_ctx = tempfile.TemporaryDirectory(prefix="chat_export_test_")
        self.tmp = Path(self._tmp_ctx.name).resolve()
        self.addCleanup(self._tmp_ctx.cleanup)

    def chdir_tmp(self):
        previous = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, previous)
        return self.tmp

    def read_text(self, path):
        return Path(path).read_text(encoding="utf-8")
