import argparse
import difflib
import os
import sys
import time
import traceback
import zipfile
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import re
import shutil
import webbrowser
from pathlib import Path, PureWindowsPath, PurePosixPath
# Attempt to import PyObjC modules for macOS file dialog support
# for this to work, you need to pip install PyObjC
if sys.platform == 'darwin':
    try:
        from AppKit import NSOpenPanel, NSApplication, NSApp
        import objc
        pyobjc_available = True
    except ImportError:
        pyobjc_available = False
else:
    pyobjc_available = False

# Attempt to import pywin32 modules for Windows file dialog support
if sys.platform == 'win32':
    try:
        import win32ui
        import win32con
        pywin32_available = True
    except ImportError:
        pywin32_available = False
else:
    pywin32_available = False


class DateRange:
    def __init__(self, from_date=None, until_date=None):
        self.from_date = from_date
        self.until_date = until_date

        if self.from_date and self.until_date and self.from_date > self.until_date:
            raise ValueError("'From' date must be before 'until' date")

    def contains(self, msg_date):
        """Check if a date falls within this range."""
        if self.from_date and msg_date < self.from_date:
            return False
        if self.until_date and msg_date > self.until_date:
            return False
        return True

    def is_filtered(self):
        """Return True if any filtering is applied."""
        return self.from_date is not None or self.until_date is not None

    def format_range(self, date_format):
        """Return a formatted string representation of the range."""
        if not self.is_filtered():
            return None
        from_str = self.from_date.strftime(date_format) if self.from_date else 'start'
        until_str = self.until_date.strftime(date_format) if self.until_date else 'end'
        return f"Filtered: {from_str} to {until_str}"

    @staticmethod
    def parse_date_input(date_str, date_formats):
        """Parse date string in various formats."""
        if not date_str:
            return None

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError("Invalid date format. Please use DD.MM.YYYY, MM/DD/YYYY, DD.MM.YY, or MM/DD/YY")


@dataclass(frozen=True)
class Chat:
    """Container for chat metadata and messages."""
    # Chat-level metadata
    name: str
    is_ios: bool
    has_media: bool
    attachments_in_zip: frozenset
    message_date_format: str
    newline_marker: str

    # Chat data
    messages: list = field(default_factory=list)
    senders: list = field(default_factory=list)
    date_range: Optional['DateRange'] = None
    sender_color_map: dict = field(default_factory=dict)
    own_name: str = ""


@dataclass(frozen=True)
class Message:
    """Individual message with computed properties using Chat context."""
    timestamp: str
    sender: str
    content: str

    # Computed fields (calculated with Chat context)
    attachment_name: Optional[str] = None
    cleaned_content: str = ""
    parsed_date: Optional[datetime] = None
    formatted_timestamp: str = ""
    has_attachment: bool = False

    @classmethod
    def create_with_context(cls, timestamp: str, sender: str, content: str, chat: 'Chat') -> 'Message':
        """Create a Message with computed properties using Chat context."""
        # Compute attachment name
        attachment_name = cls._extract_attachment_name(content, chat)
        has_attachment = attachment_name is not None

        # Compute cleaned content
        cleaned_content = cls._clean_message_content(content, chat, attachment_name)

        # Compute parsed date
        parsed_date = cls._parse_message_date(timestamp, chat.message_date_format)

        # Compute formatted timestamp
        formatted_timestamp = cls._re_render_with_day_of_week(timestamp, parsed_date)

        return cls(
            timestamp=timestamp,
            sender=sender,
            content=content,
            attachment_name=attachment_name,
            cleaned_content=cleaned_content,
            parsed_date=parsed_date,
            formatted_timestamp=formatted_timestamp,
            has_attachment=has_attachment
        )

    # Attachment patterns as class constants
    ATTACHMENT_PATTERN_ANDROID = r'(.+?\.[a-zA-Z0-9]{0,4}) \(.{1,20} .{1,20}\)'
    ATTACHMENT_PATTERN_IOS = r'<\w{2,20}:\s*([^>]+)>'

    @staticmethod
    def _extract_attachment_name(content: str, chat: 'Chat') -> Optional[str]:
        """Extract attachment filename from message content using various patterns."""
        if chat.is_ios and '<' in content:
            match = re.search(Message.ATTACHMENT_PATTERN_IOS, content)
            if match:
                result = match.group(1) if match.groups() else match.group(0)
                if result in chat.attachments_in_zip:
                    return result
        elif not chat.is_ios and '(' in content:
            match = re.search(Message.ATTACHMENT_PATTERN_ANDROID, content)
            if match:
                result = match.group(1) if match.groups() else match.group(0)
                if result in chat.attachments_in_zip:
                    return result
        return None

    @staticmethod
    def _clean_message_content(content: str, chat: 'Chat', attachment_name: Optional[str]) -> str:
        """Remove attachment markers from message content."""
        cleaned_content = content

        # Remove attachment patterns if media present and attachment found
        if chat.has_media and chat.is_ios and '<' in content and attachment_name is not None:
            cleaned_content = re.sub(Message.ATTACHMENT_PATTERN_IOS, '', cleaned_content)
        elif chat.has_media and not chat.is_ios and '(' in content and attachment_name is not None:
            cleaned_content = re.sub(Message.ATTACHMENT_PATTERN_ANDROID, '', cleaned_content)

        if cleaned_content != content:
            # Clean up any remaining parentheses and extra whitespace
            cleaned_content = re.sub(r'\s*\([^)]+\)\s*$', '', cleaned_content)

        # Make '<medien ausgeschlossen>' visible in html
        cleaned_content = cleaned_content.replace('<', '[').replace('>', ']')
        cleaned_content = Message._wrap_urls_with_anchor_tags(cleaned_content)
        cleaned_content = cleaned_content.replace(chat.newline_marker, '<br>')

        # Handle call attempts
        if cleaned_content == "null":
            cleaned_content = "[call (attempt)]"

        return cleaned_content.strip()

    @staticmethod
    def _parse_message_date(timestamp: str, message_date_format: str) -> Optional[datetime]:
        """Parse the date from a message timestamp."""
        try:
            # Remove time part and any AM/PM indicator
            date_str = re.split(', | ', timestamp.replace('[',''))[0]
            return datetime.strptime(date_str, message_date_format).date()
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _re_render_with_day_of_week(timestamp: str, parsed_date: Optional[datetime]) -> str:
        """Parse the date string and re-render it including the day of week."""
        try:
            if parsed_date:
                day_of_week = parsed_date.strftime('%a')
                return f"{day_of_week}, {timestamp}"
            return timestamp
        except (ValueError, AttributeError):
            return timestamp

    @staticmethod
    def _wrap_urls_with_anchor_tags(text: str) -> str:
        """Wrap URLs in anchor tags."""
        url_pattern = re.compile(r'(https?://[^\s]+)')
        return url_pattern.sub(r'<a href="\1" target="_blank">\1</a>', text)


class Renderer:
    """Base renderer class for message rendering."""

    def __init__(self, output_dir=None):
        self.output_dir = output_dir

    def render(self, chat):
        """Render a Chat object. To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement render method")

    def get_generated_files(self) -> list[Path]:
        """Get the generated files."""
        raise NotImplementedError("Subclasses must implement get_generated_files method")


def macos_file_picker():
    """Present a native macOS file dialog to select a file.
    pip install pyobjc-framework-Cocoa
    for this to work
    """
    # Initialize NSApplication if it hasn't been
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(1)  # NSApplicationActivationPolicyRegular
    
    # Create and configure the panel first
    panel = NSOpenPanel.alloc().init()
    panel.setCanChooseFiles_(True)
    panel.setCanChooseDirectories_(False)
    panel.setAllowsMultipleSelection_(False)
    panel.setTitle_("Select WhatsApp Chat Export ZIP File")
    panel.setPrompt_("Open")
    
    # Set file type filter to only show .zip files
    panel.setAllowedFileTypes_(["zip"])
    
    # Bring app and panel to front
    app.activateIgnoringOtherApps_(True)
    
    # Run the panel
    response = panel.runModal()
    
    # Clean up
    app.setActivationPolicy_(0)  # NSApplicationActivationPolicyRegular
    
    if response == 1:  # NSModalResponseOK
        urls = panel.URLs()
        if urls and len(urls):
            return str(urls[0].path())
    return None

def windows_file_picker():
    """Use the native Windows file picker with pywin32.
    pip install pywin32
    for this to work.
    """
    # Define file filter format: "Description|*.extension|"
    file_filter = "ZIP Files (*.zip)|*.zip|All Files (*.*)|*.*|"

    dlg = win32ui.CreateFileDialog(1, None, None, 0, file_filter)  # Open dialog (1)
    dlg.SetOFNTitle("Select WhatsApp Chat Export ZIP File")
    dlg.SetOFNInitialDir(os.path.expanduser("~"))  # Start in user's home directory

    if dlg.DoModal() == 1:  # If the user selects a file
        return dlg.GetPathName()

    return None



version = "0.9.1"

donate_link = "https://donate.stripe.com/3csfZLaIj5JE6dO4gg"

def parse_path(path_str: str) -> Path:
    """
    Parse a path string safely, handling both Windows and Unix styles.
    Returns a pathlib.Path object normalized to the current OS.
    """
    # Strip quotes from the path string if present
    path_str = path_str.strip('"\'')
    

    # Decide whether it's Windows or Unix style by looking for a drive letter
    if ":" in path_str[:3] or "\\" in path_str:
        # Looks like Windows
        pure = PureWindowsPath(path_str)
    else:
        # Looks like Unix/Posix
        pure = PurePosixPath(path_str)

    # Convert into an OS-specific Path (resolves separators automatically)
    return Path(pure)

def parse_arguments():
    """Parse command line arguments for both interactive and non-interactive modes."""
    parser = argparse.ArgumentParser(
        description='Convert WhatsApp chat exports to HTML format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Interactive mode (default)
  python main.py

  # Non-interactive mode
  python main.py -n -z "chat.zip" -p "John Doe"

  # With date filtering
  python main.py -n -z "chat.zip" -p "John Doe" --from-date "01.01.2024" --until-date "31.12.2024"

  # With custom output directory (creates /tmp/chat/ instead of ./chat/)
  python main.py -n -z "chat.zip" -p "John Doe" -o "/tmp"
        '''
    )

    parser.add_argument('-n', '--non-interactive',
                       action='store_true',
                       help='Run in non-interactive mode (requires -z and -p)')

    parser.add_argument('-z', '--zip-file',
                       type=str,
                       help='Path to WhatsApp chat export ZIP file (required in non-interactive mode)')

    parser.add_argument('-p', '--participant',
                       type=str,
                       help='Name of the participant that represents yourself (required in non-interactive mode)')

    parser.add_argument('--from-date',
                       type=str,
                       help='Start date for filtering messages (optional, formats: DD.MM.YYYY, MM/DD/YYYY, DD.MM.YY, MM/DD/YY)')

    parser.add_argument('--until-date',
                       type=str,
                       help='End date for filtering messages (optional, formats: DD.MM.YYYY, MM/DD/YYYY, DD.MM.YY, MM/DD/YY)')

    parser.add_argument('-o', '--output-dir',
                       type=str,
                       help='Base directory where the ZIP-derived output folder will be created (default: current working directory)')

    args = parser.parse_args()

    # Validate non-interactive mode requirements
    if args.non_interactive:
        if not args.zip_file:
            parser.error("Non-interactive mode requires --zip-file (-z)")
        if not args.participant:
            parser.error("Non-interactive mode requires --participant (-p)")

    return args


class MessageParser:
    """Handles parsing of WhatsApp chat content into Message objects."""

    def __init__(self, is_ios=False, has_media=False, attachments_in_zip=None):
        self.is_ios = is_ios
        self.has_media = has_media
        self.attachments_in_zip = attachments_in_zip or set()

        # Chat patterns for different platforms
        self.chat_patterns = {
            'ios': re.compile(r'\[(\d{1,4}.\d{1,2}.\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\] (.*?): (.*)'),
            'android': re.compile(r'(\d{1,4}.\d{1,2}.\d{2,4},? \d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?) - (.*?): (.*)')
        }
        self.whatsapp_patterns = {
            'ios': re.compile(r'\[(\d{1,4}.\d{1,2}.\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\] (.*)'),
            'android': re.compile(r'(\d{1,4}.\d{1,2}.\d{2,4},? \d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?) - (.*)')
        }

        self.attachment_pattern_android = r'(.+?\.[a-zA-Z0-9]{0,4}) \(.{1,20} .{1,20}\)'
        self.attachment_pattern_ios = r'<\w{2,20}:\s*([^>]+)>'
        self.newline_marker = ' $NEWLINE$ '
        self.message_date_format = "%d.%m.%y"

        self.date_formats = [
            "%d.%m.%Y",  # German format: DD.MM.YYYY
            "%m/%d/%Y",  # US format: MM/DD/YYYY
            "%d.%m.%y",  # German format: DD.MM.YY
            "%m/%d/%y"   # US format: MM/DD/YY
        ]

    def get_date_format(self, chat_content):
        """Determine the date format used in the chat."""
        chat_content = chat_content.replace('‎','')
        first_line = None
        pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
        for line in chat_content.split('\n'):
            if pattern.match(line):
                first_line = line
                break

        if first_line is None:
            raise ValueError(f"Could not determine the date format of the chat: {chat_content.split('\\n')[0]}")

        first_line_date = first_line.split(',')[0].replace('[', '')
        # find first non-digit in the date string
        for char in first_line_date:
            if not char.isdigit():
                deliminator = char
                break

        # year might be in position 0 or 2, i.e. 2018-12-22 vs 22.12.18 vs 22.12.2018
        if len(first_line_date.split(deliminator)[0]) == 4:
            return f'%Y{deliminator}%m{deliminator}%d'
        # year is in position 2
        # check if year is 2 or 4 digits
        year_pattern = '%y' if len(first_line_date.split(deliminator)[2]) == 2 else '%Y'
        # need to find out if month or day comes first.
        day_before_month = True
        for line in chat_content.split('\n'):
            if not pattern.match(line):
                continue
            date_str = re.split(', | ', line.replace('[',''))[0]
            first, second, _ = date_str.split(deliminator)
            # convert to int
            first = int(first)
            second = int(second)
            if first > 12:
                day_before_month = True
                break
            if second > 12:
                day_before_month = False
                break

        if day_before_month:
            return f'%d{deliminator}%m{deliminator}{year_pattern}'
        else:
            return f'%m{deliminator}%d{deliminator}{year_pattern}'

    def _parse_timestamp_date(self, timestamp):
        """Helper method to parse timestamp for date filtering during message processing."""
        try:
            # Remove time part and any AM/PM indicator
            date_str = re.split(', | ', timestamp.replace('[',''))[0]
            return datetime.strptime(date_str, self.message_date_format).date()
        except (ValueError, AttributeError):
            return None

    def get_senders(self, chat_content):
        """Extract all unique senders from chat content."""
        senders = set()
        pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
        for line in chat_content.split('\n'):
            match = pattern.match(line)
            if match:
                sender = match.group(2)
                senders.add(sender)
        return sorted(list(senders))

    def _generate_color_map(self, senders, own_name):
        """Generate color mapping for senders."""
        sender_colors = {
            'own': '#d9fdd3',    # WhatsApp green for own messages
            'default': '#ffffff', # White for the second sender
            'whatsapp': '#20c063',
            # Additional colors for other senders
            'others': [
                '#f0e6ff',  # Light purple
                '#fff3e6',  # Light orange
                '#e6fff0',  # Light mint
                '#ffe6e6',  # Light pink
                '#e6f3ff',  # Light blue
                '#fff0f0',  # Lighter pink
                '#e6ffe6',  # Lighter mint
                '#f2e6ff',  # Lighter purple
                '#fff5e6',  # Peach
                '#e6ffff',  # Light cyan
                '#ffe6f0',  # Rose
                '#f0ffe6',  # Light lime
                '#e6e6ff',  # Lavender
                '#ffe6cc',  # Light apricot
                '#e6fff9'   # Light turquoise
            ]
        }

        color_map = {}

        # Remove own name from senders list for color assignment
        other_senders = [s for s in senders if s != own_name]

        # Assign colors to senders
        color_map[own_name] = sender_colors['own']

        # assign whatsapp color
        color_map['WhatsApp'] = sender_colors['whatsapp']

        # Assign white to the first other sender
        if other_senders:
            color_map[other_senders[0]] = sender_colors['default']

        # Assign different colors to remaining senders
        for i, sender in enumerate(other_senders[1:]):
            color_index = i % len(sender_colors['others'])
            color_map[sender] = sender_colors['others'][color_index]

        return color_map

    def parse_messages(self, chat_content, chat_name="", date_range=None, own_name=""):
        """Parse chat content into a Chat object."""
        # Set the message date format
        self.message_date_format = self.get_date_format(chat_content)

        # Create Chat object with metadata
        chat = Chat(
            name=chat_name,
            is_ios=self.is_ios,
            has_media=self.has_media,
            attachments_in_zip=frozenset(self.attachments_in_zip),
            message_date_format=self.message_date_format,
            newline_marker=self.newline_marker,
            messages=[],
            senders=self.get_senders(chat_content),
            date_range=date_range,
            sender_color_map={},
            own_name=own_name
        )

        # Preprocess the chat content to handle multi-line messages
        processed_content = []
        current_line = []
        filtered_count = 0
        total_count = 0

        for line in chat_content.split('\n'):
            # remove the Left-to-right_marks
            line = line.replace('‎','')
            pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
            wapattern = self.whatsapp_patterns['ios'] if self.is_ios else self.whatsapp_patterns['android']
            match = pattern.match(line)
            wamatch = wapattern.match(line)

            if match or wamatch:
                total_count += 1
                if current_line:
                    processed_content.append(''.join(current_line))

                # Only add messages within date range
                if match:
                    timestamp = match.group(1)
                    if date_range and not date_range.contains(self._parse_timestamp_date(timestamp)):
                        current_line = []
                        continue
                else:
                    timestamp = wamatch.group(1)
                    if date_range and not date_range.contains(self._parse_timestamp_date(timestamp)):
                        current_line = []
                        continue

                filtered_count += 1
                current_line = [line]
            else:
                if current_line:
                    current_line.append(self.newline_marker + line)

        # Don't forget to add the last message
        if current_line:
            processed_content.append(''.join(current_line))

        # Parse each processed line into Message objects
        messages = []
        for line in processed_content:
            pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
            wapattern = self.whatsapp_patterns['ios'] if self.is_ios else self.whatsapp_patterns['android']
            match = pattern.match(line)
            wamatch = wapattern.match(line)

            if match:
                timestamp, sender, content = match.groups()
                messages.append(Message.create_with_context(
                    timestamp=timestamp,
                    sender=sender,
                    content=content,
                    chat=chat
                ))
            elif wamatch:
                timestamp, content = wamatch.groups()
                messages.append(Message.create_with_context(
                    timestamp=timestamp,
                    sender="WhatsApp",
                    content=content,
                    chat=chat
                ))

        # Update chat with messages and color map
        chat.messages.extend(messages)
        chat.sender_color_map.update(self._generate_color_map(chat.senders, own_name))

        return chat, filtered_count, total_count


class HTMLRenderer(Renderer):
    """Renders messages to HTML format."""

    def __init__(self, output_dir, has_media=False):
        super().__init__(output_dir)
        self.has_media = has_media
        self.html_filename = 'chat.html'
        self.html_filename_media_linked = 'chat_media_linked.html'
        self.attachments_to_extract = set()

    def get_generated_files(self) -> list[Path]:
        """Get the generated files."""
        return [Path(self.output_dir, self.html_filename), Path(self.output_dir, self.html_filename_media_linked)]

    def get_css_styles(self):
        """Return the CSS styles for the HTML output."""
        return """body {
            font-family: Arial, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background-color: #e5ddd5;
        }
        .message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 7.5px;
            max-width: 65%;
            position: relative;
            clear: both;
        }
        .message.sent {
            float: right;
            margin-left: 35%;
        }
        .message.received {
            float: left;
            margin-right: 35%;
        }
        .message.whatsapp {
            max-width: 100%
        }
        .media {
            max-width: 100%;
            border-radius: 5px;
            margin: 5px 0;
        }
        .timestamp {
            color: #667781;
            font-size: 0.75em;
            float: right;
            margin-left: 10px;
            margin-top: 5px;
        }
        .sender {
            color: #1f7aad;
            font-size: 0.85em;
            font-weight: bold;
            display: block;
            margin-bottom: 5px;
        }
        .content {
            word-wrap: break-word;
        }
        .clearfix::after {
            content: "";
            clear: both;
            display: table;
        }
        a {
            color: #039be5;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        @media print {
            body {
                background-color: #ffffff;
            }
        }"""

    def get_html_header(self):
        """Generate the HTML header."""
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.chat.name}</title>
    <style>
        {self.get_css_styles()}
    </style>
</head>
<body>
<div class="chat-container">
<h1>{self.chat.name}</h1>"""

    def get_html_footer(self):
        """Generate the HTML footer."""
        return """
</div>
</body>
</html>"""

    def render_media_element(self, attachment_name, is_media_linked=False):
        """Render a media element based on its file extension."""
        media_path = f"./media/{attachment_name}"

        if is_media_linked:
            # Always show as link in media-linked version
            return f'<a href="{media_path}">📎 {attachment_name}</a><br>'

        # Render media inline in main version
        ext = attachment_name.lower()
        if ext.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
            return f'<img class="media" src="{media_path}"><br>'
        elif ext.endswith('.mp4'):
            return f'<video class="media" controls><source src="{media_path}" type="video/mp4"></video><br>'
        elif ext.endswith('.opus'):
            return f'<audio class="media" controls><source src="{media_path}" type="audio/ogg"></audio><br>'
        elif ext.endswith('.wav'):
            return f'<audio class="media" controls><source src="{media_path}" type="audio/wav"></source></audio><br>'
        elif ext.endswith('.mp3'):
            return f'<audio class="media" controls><source src="{media_path}" type="audio/mpeg"></audio><br>'
        elif ext.endswith('.m4a'):
            return f'<audio class="media" controls><source src="{media_path}" type="audio/mp4"></audio><br>'
        else:
            return f'<a href="{media_path}">📎 {attachment_name}</a><br>'

    def render_message(self, message, sender_color_map, own_name, main_f, media_f):
        """Render a single message to both file handles."""
        # Determine message alignment and background color
        is_own_message = message.sender == own_name
        is_wa_message = message.sender == "WhatsApp"
        message_class = "sent" if is_own_message else "received"
        if is_wa_message:
            message_class = 'whatsapp'
        bg_color = sender_color_map.get(message.sender, '#ffffff')

        # Common message structure
        message_start = f'\n<div class="message {message_class} clearfix" style="background-color: {bg_color};">'
        sender_div = f'<div class="sender">{message.sender}</div>'
        content_start = '<div class="content">'
        content_end = '</div>'
        timestamp_span = f'<span class="timestamp">{message.formatted_timestamp}</span>'
        message_end = '</div>'

        # Write message start to both files
        main_f.write(message_start)
        media_f.write(message_start)

        # Write sender to both files
        main_f.write(sender_div)
        media_f.write(sender_div)

        # Write content start to both files
        main_f.write(content_start)
        media_f.write(content_start)

        # Check if the message contains media
        if message.has_attachment:
            attachment_name = message.attachment_name
            self.attachments_to_extract.add(attachment_name)

            # Render media differently for each file
            main_f.write(self.render_media_element(attachment_name, is_media_linked=False))
            media_f.write(self.render_media_element(attachment_name, is_media_linked=True))

        # Add the message content to both files
        cleaned_content = message.cleaned_content
        if cleaned_content:
            main_f.write(f'{cleaned_content}')
            media_f.write(f'{cleaned_content}')

        # Write content end, timestamp, and message end to both files
        main_f.write(content_end)
        media_f.write(content_end)
        main_f.write(timestamp_span)
        media_f.write(timestamp_span)
        main_f.write(message_end)
        media_f.write(message_end)

    def render(self, chat):
        """Render chat to HTML files."""
        print("Writing HTML files...")

        self.chat = chat
        # Prepare file paths
        main_html_path = os.path.join(self.output_dir, self.html_filename)
        media_linked_html_path = os.path.join(self.output_dir, self.html_filename_media_linked)

        # Open both files for writing
        with open(main_html_path, 'w', encoding='utf-8') as main_f, \
             open(media_linked_html_path, 'w', encoding='utf-8') as media_f:
            
            # Write header to both files
            header = self.get_html_header()
            main_f.write(header)
            media_f.write(header)

            # Write date range and attribution to both files
            if chat.date_range and chat.date_range.is_filtered():
                date_range_str = chat.date_range.format_range(chat.message_date_format)
                if date_range_str:
                    date_html = f'<p style="color: #667781;">{date_range_str}</p>'
                    main_f.write(date_html)
                    media_f.write(date_html)

            attribution = '<p style="color: #667781;">This rendering has been created with the free offline tool `chat-export` from https://chat-export.click </p>'
            main_f.write(attribution)
            media_f.write(attribution)

            
            message_count = 0

            for message in chat.messages:
                self.render_message(message, chat.sender_color_map, chat.own_name, main_f, media_f)
                message_count += 1

            

            # Write footer to both files
            footer = self.get_html_footer()
            main_f.write(footer)
            media_f.write(footer)

        return self.attachments_to_extract


class ChatExport:
    def __init__(self, zip_path, from_date=None, until_date=None, participant_name=None, base_output_dir=None):
        # Validate zip file existence
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Could not find the file: {zip_path}\nPlease check if the file path is correct.")

        if not zip_path.lower().endswith('.zip'):
            raise ValueError(f"The file {zip_path} is not a zip file.\nPlease provide a valid WhatsApp chat export zip file.")

        self.zip_path = zip_path

        # Pre-set values for non-interactive mode
        self.from_date = from_date
        self.until_date = until_date
        self.participant_name = participant_name

        # Set up output directory: base_output_dir/zip_filename or just zip_filename
        zip_stem = Path(zip_path).stem
        if base_output_dir:
            # Normalize the base output directory path (handle Windows paths, quotes, etc.)
            normalized_base_dir = parse_path(base_output_dir)
            self.output_dir = os.path.join(normalized_base_dir, zip_stem)
        else:
            self.output_dir = zip_stem
        self.media_dir = os.path.join(self.output_dir, "media")

        self.own_name = participant_name
        self.attachments_in_zip = set()
        self.sender_colors = {
            'own': '#d9fdd3',    # WhatsApp green for own messages
            'default': '#ffffff', # White for the second sender
            'whatsapp': '#20c063',
            # Additional colors for other senders
            'others': [
                '#f0e6ff',  # Light purple
                '#fff3e6',  # Light orange
                '#e6fff0',  # Light mint
                '#ffe6e6',  # Light pink
                '#e6f3ff',  # Light blue
                '#fff0f0',  # Lighter pink
                '#e6ffe6',  # Lighter mint
                '#f2e6ff',  # Lighter purple
                '#fff5e6',  # Peach
                '#e6ffff',  # Light cyan
                '#ffe6f0',  # Rose
                '#f0ffe6',  # Light lime
                '#e6e6ff',  # Lavender
                '#ffe6cc',  # Light apricot
                '#e6fff9'   # Light turquoise
            ]
        }
        self.has_media = False
        self.is_ios = False

        self.date_formats = [
            "%d.%m.%Y",  # German format: DD.MM.YYYY
            "%m/%d/%Y",  # US format: MM/DD/YYYY
            "%d.%m.%y",  # German format: DD.MM.YY
            "%m/%d/%y"   # US format: MM/DD/YY
        ]

        # Initialize modular components (will be set up later after platform detection)
        self.parser = None
        self.renderer = None

    def validate_participant(self, participant_name, senders):
        """Validate that the specified participant exists in the chat.
        If not found, display all participants and raise an error."""
        if participant_name not in senders:
            print(f"\nError: Participant '{participant_name}' not found in the chat.")
            print("\nFound the following participants in the chat:")
            for i, sender in enumerate(senders, 1):
                print(f"{i}. {sender}")
            print("\nPlease use one of the names listed above exactly as shown.")
            raise ValueError(f"Participant '{participant_name}' not found in chat")
        return True

    def parse_date_input(self, date_str):
        """Parse date string in either US or German format."""
        return DateRange.parse_date_input(date_str, self.date_formats)

    def setup_modular_components(self):
        """Initialize the MessageParser and HTMLRenderer components."""
        # Setup parser
        self.parser = MessageParser(
            is_ios=self.is_ios,
            has_media=self.has_media,
            attachments_in_zip=self.attachments_in_zip
        )
        

        # Setup renderer
        self.renderer = HTMLRenderer(
            output_dir=self.output_dir,
            has_media=self.has_media
        )

    @staticmethod
    def most_similar(target: str, candidates: list[str]) -> str:
        """Return the string from candidates most similar to target."""
        return max(candidates, key=lambda c: difflib.SequenceMatcher(None, target, c).ratio())

    def process_chat(self):
        # Ask for optional date range
        print("\nOptional: Enter date range to filter messages")
        print("Supported formats: MM/DD/YYYY, DD.MM.YYYY, MM/DD/YY, DD.MM.YY")
        print("Leave empty to skip")
        while True:
            try:
                from_date_str = input("From date (optional): ").strip()
                self.from_date = self.parse_date_input(from_date_str)
                break
            except ValueError as e:
                print(f"Error: {e}")
                if input("Try again? [Y/n]: ").lower() == 'n':
                    break

        while True:
            try:
                until_date_str = input("Until date (optional): ").strip()
                self.until_date = self.parse_date_input(until_date_str)
                if self.from_date and self.until_date and self.from_date > self.until_date:
                    raise ValueError("'From' date must be before 'until' date")
                break
            except ValueError as e:
                print(f"Error: {e}")
                if input("Try again? [Y/n]: ").lower() == 'n':
                    break
        

        # Get the base name of the zip file without extension
        zip_base_name = Path(self.zip_path).stem

        if os.path.exists(self.output_dir):
                print(f"Cleaning existing directory: {self.output_dir}")
                shutil.rmtree(self.output_dir)

        # Create fresh output directories
        os.makedirs(self.output_dir)
        os.makedirs(self.media_dir)

        

        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
            chat_file_candidates = [f for f in zip_ref.namelist() if f.lower().endswith('.txt')]
            if '_chat.txt' in chat_file_candidates:
                self.is_ios = True
                chat_file = '_chat.txt'
            else:
                self.is_ios = False
                chat_file = self.most_similar(f"{zip_base_name}.txt", chat_file_candidates)

            # Extract media files
            for file in zip_ref.namelist():
                if file != chat_file:
                    self.attachments_in_zip.add(file)
                    self.has_media = True
            
            # If still not found, raise error
            if chat_file not in zip_ref.namelist():
                raise FileNotFoundError(f"The chat file '{chat_file}' does not exist in the ZIP archive. Not a valid WhatsApp export zip.")

            with zip_ref.open(chat_file) as f:
                chat_content = f.read().decode('utf-8')
        if self.has_media:
            print(f"ZIP file is an {'iOS' if self.is_ios else 'Android'} export with media/attachments, '{chat_file}' is the chat text file.")
        else:
            print(f"ZIP file is an {'iOS' if self.is_ios else 'Android'} export without media/attachments, '{chat_file}' is the chat text file.")
            shutil.rmtree(self.media_dir)
        # Setup modular components now that we know the platform and media status
        self.setup_modular_components()

        # Create date range for filtering
        date_range = DateRange(self.from_date, self.until_date) if (self.from_date or self.until_date) else None

        # Get list of senders first to let user choose their name
        senders = self.parser.get_senders(chat_content)
        print("\nFound the following participants in the chat:")
        for i, sender in enumerate(senders, 1):
            print(f"{i}. {sender}")

        while True:
            try:
                choice = int(input("\nEnter the number corresponding to your name: ")) - 1
                if 0 <= choice < len(senders):
                    self.own_name = senders[choice]
                    break
                else:
                    print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        
        processing_start_time = time.time()
        
        # Parse messages using the new MessageParser - now returns a Chat object
        chat, filtered_count, total_count = self.parser.parse_messages(
            chat_content,
            chat_name=os.path.basename(self.zip_path),
            date_range=date_range,
            own_name=self.own_name
        )

        if date_range and date_range.is_filtered():
            print(f"\n{filtered_count} of {total_count} messages match date range filter.")
            if filtered_count == 0:
                raise ValueError("No messages found in the specified date range. Aborting.")
        print(f"Exporting {len(chat.messages)} messages.")

        # Render messages using the new HTMLRenderer
        attachments_to_extract = self.renderer.render(chat)

        if self.has_media:
            print("Extracting attachments/media...")
            # extract attachments of rendered messages
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                # Extract media files
                for file in zip_ref.namelist():
                    if file in attachments_to_extract:
                        zip_ref.extract(file, self.media_dir)
        processing_end_time = time.time()
        print(f"Processing took {processing_end_time - processing_start_time:.3f} seconds")

    def process_chat_non_interactive(self):
        """Process chat in non-interactive mode using pre-set parameters."""
        # Validate date parameters if provided
        if self.from_date:
            try:
                self.from_date = self.parse_date_input(self.from_date)
            except ValueError as e:
                raise ValueError(f"Invalid from-date format: {e}")

        if self.until_date:
            try:
                self.until_date = self.parse_date_input(self.until_date)
            except ValueError as e:
                raise ValueError(f"Invalid until-date format: {e}")

        if self.from_date and self.until_date and self.from_date > self.until_date:
            raise ValueError("'From' date must be before 'until' date")

        processing_start_time = time.time()

        # Get the base name of the zip file without extension
        zip_base_name = Path(self.zip_path).stem

        if os.path.exists(self.output_dir):
            print(f"Cleaning existing directory: {self.output_dir}")
            shutil.rmtree(self.output_dir)

        # Create fresh output directories
        os.makedirs(self.output_dir)
        os.makedirs(self.media_dir)

        # Validate that it's a proper ZIP file
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                chat_file_candidates = [f for f in zip_ref.namelist() if f.lower().endswith('.txt')]
                if '_chat.txt' in chat_file_candidates:
                    self.is_ios = True
                    chat_file = '_chat.txt'
                else:
                    self.is_ios = False
                    chat_file = self.most_similar(f"{zip_base_name}.txt", chat_file_candidates)

                # Extract media files
                for file in zip_ref.namelist():
                    if file != chat_file:
                        self.attachments_in_zip.add(file)
                        self.has_media = True

                # If still not found, raise error
                if chat_file not in zip_ref.namelist():
                    raise FileNotFoundError(f"The chat file '{chat_file}' does not exist in the ZIP archive. Not a valid WhatsApp export zip.")

                with zip_ref.open(chat_file) as f:
                    chat_content = f.read().decode('utf-8')

        except zipfile.BadZipFile:
            raise ValueError(f"The file {self.zip_path} is not a valid ZIP file.")

        if self.has_media:
            print(f"ZIP file is an {'iOS' if self.is_ios else 'Android'} export with media/attachments, '{chat_file}' is the chat text file.")
        else:
            print(f"ZIP file is an {'iOS' if self.is_ios else 'Android'} export without media/attachments, '{chat_file}' is the chat text file.")
            shutil.rmtree(self.media_dir)

        # Setup modular components now that we know the platform and media status
        self.setup_modular_components()

        # Create date range for filtering
        date_range = DateRange(self.from_date, self.until_date) if (self.from_date or self.until_date) else None
        print(f"from date: {self.from_date}, until date: {self.until_date}")

        # Get list of senders and validate the provided participant
        senders = self.parser.get_senders(chat_content)
        self.validate_participant(self.own_name, senders)

        # Parse messages using the new MessageParser - now returns a Chat object
        chat, filtered_count, total_count = self.parser.parse_messages(
            chat_content,
            chat_name=os.path.basename(self.zip_path),
            date_range=date_range,
            own_name=self.own_name
        )

        if date_range and date_range.is_filtered():
            print(f"\n{filtered_count} of {total_count} messages match date range filter.")
            if filtered_count == 0:
                raise ValueError("No messages found in the specified date range. Aborting.")
        print(f"Exporting {len(chat.messages)} messages.")

        # Render messages using the new HTMLRenderer
        attachments_to_extract = self.renderer.render(chat)

        if self.has_media:
            print("Extracting attachments/media...")
            # extract attachments of rendered messages
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                # Extract media files
                for file in zip_ref.namelist():
                    if file in attachments_to_extract:
                        zip_ref.extract(file, self.media_dir)
        processing_end_time = time.time()
        print(f"Processing took {processing_end_time - processing_start_time:.3f} seconds")
        


def check_tkinter_availability():
    """Check if tkinter is available and working on the system."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.destroy()
        return True
    except Exception as e:
        print("Tkinter is not available on your system. Using prompt input instead of file picker dialog.")
        return False

def browse_zip_file():
    if sys.platform == 'darwin' and pyobjc_available:
        result = macos_file_picker()
        return result
    elif sys.platform == 'win32' and pywin32_available:
        result = windows_file_picker()
        return result

    # Check tkinter availability first
    if not check_tkinter_availability():
        # Fallback to command line input
        file_path = input("Please enter the path to your WhatsApp chat export ZIP file: ").strip()
        return file_path if file_path else None

    import tkinter as tk
    from tkinter import filedialog
    # Initialize Tkinter root window and hide it
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Open file dialog and set file type filter to .zip files
    zip_file_path = filedialog.askopenfilename(
        title="Select a WhatsApp Chat Export ZIP file",
        filetypes=[("ZIP files", "*.zip")]
    )

    # Return the selected file path
    return zip_file_path

def open_html_file_in_browser(html_file: Path):
    """Opens the specified HTML file in the default web browser."""
    # Get the absolute path of the file
    file_path = Path(os.path.abspath(html_file))
    # Open the file in the default web browser
    # file:///
    webbrowser.open(f"file://{file_path.as_posix()}")

def main():
    args = parse_arguments()

    if args.non_interactive:
        # Non-interactive mode
        print(f"chat-export v{version} - Non-interactive mode")
        print("----------------------------------------")
        success = False
        try:
            print(f"Processing file: {args.zip_file}...")

            # Parse dates if provided
            from_date = args.from_date if args.from_date else None
            until_date = args.until_date if args.until_date else None

            chat_export = ChatExport(args.zip_file, from_date, until_date, args.participant, args.output_dir)
            chat_export.process_chat_non_interactive()
            print(f'Written: {", ".join([str(p.absolute()) for p in chat_export.renderer.get_generated_files()])}')
            print("Done.")
            success = True

        except FileNotFoundError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print(traceback.format_exc())
            sys.exit(1)

    else:
        # Interactive mode (original behavior)
        print(f"Welcome to chat-export v{version}")
        print("----------------------------------------")
        print("Select the WhatsApp chat export ZIP file you want to convert to HTML.")
        success = False
        try:
            selected_zip_file = browse_zip_file()
            if not selected_zip_file:
                raise FileNotFoundError("No file selected.")
            print(f"Processing selected file: {selected_zip_file}...")
            chat_export = ChatExport(selected_zip_file, base_output_dir=args.output_dir)
            chat_export.process_chat()
            print(f'Written: {", ".join([str(p.absolute()) for p in chat_export.renderer.get_generated_files()])}')
            print("Done.")
            open_in_browser = input("Would you like to open them in the browser? [Y/n]: ").strip().lower()
            if open_in_browser != 'n':
                for file in chat_export.renderer.get_generated_files():
                    open_html_file_in_browser(file.absolute())
            success = True

        except FileNotFoundError as e:
            print(f"Error: {e}")
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            print(traceback.format_exc())

        if success and input("Do you like the tool and want to buy me a coffee? [y/N]: ").strip().lower() == 'y':
            webbrowser.open(donate_link)
        if not success:
            print("Press enter to exit")
            input()

if __name__ == "__main__":
    main()
