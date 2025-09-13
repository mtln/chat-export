import difflib
import os
import sys
import time
import traceback
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

import zipfile
import os
from datetime import datetime, date
import re
from pathlib import Path
import shutil
import sys
import webbrowser


version = "0.9.0"

donate_link = "https://donate.stripe.com/3csfZLaIj5JE6dO4gg"

class WhatsAppChatRenderer:
    def __init__(self, zip_path):
        # Validate zip file existence
        if not os.path.exists(zip_path):
            raise FileNotFoundError(f"Could not find the file: {zip_path}\nPlease check if the file path is correct.")
        
        if not zip_path.lower().endswith('.zip'):
            raise ValueError(f"The file {zip_path} is not a zip file.\nPlease provide a valid WhatsApp chat export zip file.")

        self.zip_path = zip_path
        self.output_dir = Path(zip_path).stem
        self.chat_name = Path(zip_path).stem
        self.media_dir = os.path.join(self.output_dir, "media")
        # Replace the single chat_pattern with a map of patterns
        self.chat_patterns = {
            'ios': re.compile(r'\[(\d{1,4}.\d{1,2}.\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\] (.*?): (.*)'),
            'android': re.compile(r'(\d{1,4}.\d{1,2}.\d{2,4},? \d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?) - (.*?): (.*)')
        }
        self.message_date_format = "%d.%m.%y"
        self.own_name = None
        self.attachments_to_extract = set()
        self.attachments_in_zip = set()
        self.sender_colors = {
            'own': '#d9fdd3',    # WhatsApp green for own messages
            'default': '#ffffff', # White for the second sender
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
        self.sender_color_map = {}
        self.newline_marker = ' $NEWLINE$ '
        self.html_filename = 'chat.html'
        self.html_filename_media_linked = 'chat_media_linked.html'
                
        self.attachment_pattern_android = r'(.+?\.[a-zA-Z0-9]{0,4}) \(.{1,20} .{1,20}\)'
        self.attachment_pattern_ios =  r'<\w{2,20}:\s*([^>]+)>'
        self.has_media = False
        self.from_date = None
        self.until_date = None
        self.re_render_dates = False
        self.date_formats = [
            "%d.%m.%Y",  # German format: DD.MM.YYYY
            "%m/%d/%Y",  # US format: MM/DD/YYYY
            "%d.%m.%y",  # German format: DD.MM.YY
            "%m/%d/%y"   # US format: MM/DD/YY
        ]
        self.is_ios = False

    def get_senders(self, chat_content):
        senders = set()
        pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
        for line in chat_content.split('\n'):
            match = pattern.match(line)
            if match:
                sender = match.group(2)
                senders.add(sender)
        return sorted(list(senders))

    def setup_sender_colors(self, senders):
        # Remove own name from senders list for color assignment
        other_senders = [s for s in senders if s != self.own_name]
        
        # Assign colors to senders
        self.sender_color_map[self.own_name] = self.sender_colors['own']
        
        # Assign white to the first other sender
        if other_senders:
            self.sender_color_map[other_senders[0]] = self.sender_colors['default']
        
        # Assign different colors to remaining senders
        for i, sender in enumerate(other_senders[1:]):
            color_index = i % len(self.sender_colors['others'])
            self.sender_color_map[sender] = self.sender_colors['others'][color_index]

    def get_date_format(self, chat_content):
        chat_content = chat_content.replace('‎','')
        first_line = None
        pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
        for line in chat_content.split('\n'):
            if pattern.match(line):
                first_line = line
                break
        
        if first_line is None:
            raise ValueError(f"Could not determine the date format of the chat: {chat_content.split('\n')[0]}")

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

        

    def parse_date_input(self, date_str):
        """Parse date string in either US or German format."""
        if not date_str:
            return None
            
        for fmt in self.date_formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        raise ValueError("Invalid date format. Please use DD.MM.YYYY, MM/DD/YYYY, DD.MM.YY, or MM/DD/YY")

    def parse_message_date(self, date_str):
        """Parse the date from a message timestamp."""
        # Remove time part and any AM/PM indicator
        date_str = re.split(', | ',  date_str.replace('[',''))[0]
        return datetime.strptime(date_str, self.message_date_format).date()


    def re_render_with_day_of_week(self, date_str: str) -> str:
        """Parse the date string using self.message_date_format and then re-render it including the day of week.
        If something fails, returns the input date_str.
        e.g. 4/18/25, 3:09:10 PM becomes Fri, 4/18/25, 3:09:10 PM.
        31.08.2025 becomes Sun, 31.08.2025
        """
        try:
            # Parse the date using the current message_date_format
            parsed_date = self.parse_message_date(date_str)
            day_of_week = parsed_date.strftime('%a')
            # Re-render with day of week prefix
            return f"{day_of_week}, {date_str}"
        except (ValueError, AttributeError):
            # If parsing fails, return the original string
            return date_str

    


    def is_message_in_date_range(self, timestamp):
        """Check if message timestamp falls within the specified date range."""
        msg_date = self.parse_message_date(timestamp)
        if self.from_date and msg_date < self.from_date:
            return False
        if self.until_date and msg_date > self.until_date:
            return False
        return True

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
        # Preprocess the chat content to handle multi-line messages
        processed_content = []
        current_line = []
        filtered_count = 0
        total_count = 0

        self.message_date_format = self.get_date_format(chat_content)
        
        for line in chat_content.split('\n'):
            # remove the Left-to-right_marks
            line = line.replace('‎','')
            pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
            match = pattern.match(line)
            if match:
                total_count += 1
                if current_line:
                    processed_content.append(''.join(current_line))
                # Only add messages within date range
                if not self.is_message_in_date_range(match.group(1)):
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

        # Join all processed lines with newlines
        chat_content = '\n'.join(processed_content)
        if self.from_date or self.until_date:
            print(f"\n{filtered_count} of {total_count} messages match date range filter.")
            if filtered_count == 0:
                raise ValueError("No messages found in the specified date range. Aborting.")
        print(f"Exporting {len(processed_content)} messages.")
        # print(processed_content)
        # Get list of senders and let user choose their name
        senders = self.get_senders(chat_content)
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

        # Setup color mapping for senders
        self.setup_sender_colors(senders)
      
       
        self.generate_both_html_files(chat_content)
        
        if self.has_media:
            print("Extracting attachments/media...")
            # extract attachments of rendered messages
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                # Extract media files
                for file in zip_ref.namelist():
                    if file in self.attachments_to_extract:
                        zip_ref.extract(file, self.media_dir)
        print("Done.")
                       

    @staticmethod
    def wrap_urls_with_anchor_tags(text):
        # Regular expression to match URLs
        url_pattern = re.compile(r'(https?://[^\s]+)')
        
        # Replace each URL with an <a> tag
        result = url_pattern.sub(r'<a href="\1" target="_blank">\1</a>', text)
        return result

    def extract_attachment_name(self, content):
        """Extract attachment filename from message content using various patterns."""
        if self.is_ios and '<' in content:
            match = re.search(self.attachment_pattern_ios, content)
            if match:
                result = match.group(1) if match.groups() else match.group(0)
                if result in self.attachments_in_zip:
                    return result
        elif not self.is_ios and '(' in content:
            match = re.search(self.attachment_pattern_android, content)
            if match:
                result = match.group(1) if match.groups() else match.group(0)
                if result in self.attachments_in_zip:
                    return result
        return None

    def clean_message_content(self, content):
        """Remove attachment markers from message content."""
        cleaned_content = content
        # if no < or ( in content, skip the attachment pattern matching
        if self.has_media and self.is_ios and '<' in content and self.extract_attachment_name(content) is not None:
            cleaned_content = re.sub(self.attachment_pattern_ios, '', cleaned_content)
        elif self.has_media and not self.is_ios and '(' in content and self.extract_attachment_name(content) is not None:
            cleaned_content = re.sub(self.attachment_pattern_android, '', cleaned_content)
        if cleaned_content != content:
            # Clean up any remaining parentheses and extra whitespace
            cleaned_content = re.sub(r'\s*\([^)]+\)\s*$', '', cleaned_content)
        # make '<medien ausgeschlossen>' visible in html
        cleaned_content = cleaned_content.replace('<', '[').replace('>', ']')
        cleaned_content = self.wrap_urls_with_anchor_tags(cleaned_content)
        cleaned_content = cleaned_content.replace(self.newline_marker, '<br>')
        # we don't have any details on calls. Whether if they were video or audio. 
        # Nor if they where attempts or established
        # Nor if they were incoming or outgoing.
        # Just a string "null"
        if cleaned_content == "null":
            cleaned_content = "[call (attempt)]"
        return cleaned_content.strip()

    

    def generate_both_html_files(self, chat_content):
        """Generate both HTML files in a single pass for better efficiency."""
        print("Writing HTML files...")
        
        # Prepare file paths
        main_html_path = os.path.join(self.output_dir, self.html_filename)
        media_linked_html_path = os.path.join(self.output_dir, self.html_filename_media_linked)
        
        # Open both files for writing
        with open(main_html_path, 'w', encoding='utf-8') as main_f, \
             open(media_linked_html_path, 'w', encoding='utf-8') as media_f:
            
            # Write header to both files
            header = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>PLACEHOLDER_CHAT_NAME</title>
    <style>
        body {
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
        }
    </style>
</head>
<body>
<div class="chat-container">
<h1>PLACEHOLDER_CHAT_NAME</h1>""".replace('PLACEHOLDER_CHAT_NAME', self.chat_name)
            
            main_f.write(header)
            media_f.write(header)
            
            # Write date range and attribution to both files
            if self.from_date or self.until_date:
                date_range = f"Filtered: {self.from_date.strftime(self.message_date_format) if self.from_date else 'start'} to {self.until_date.strftime(self.message_date_format) if self.until_date else 'end'}"
                date_html = f'<p style="color: #667781;">{date_range}</p>'
                main_f.write(date_html)
                media_f.write(date_html)
            
            attribution = '<p style="color: #667781;">This rendering has been created with the free offline tool `chat-export` from https://chat-export.click </p>'
            main_f.write(attribution)
            media_f.write(attribution)
            
            pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
            
            # Time the message processing loop
            loop_start_time = time.time()
            message_count = 0
            
            for line in chat_content.split('\n'):
                match = pattern.match(line)
                if match:
                    timestamp, sender, content = match.groups()
                    
                    # Determine message alignment and background color
                    is_own_message = sender == self.own_name
                    message_class = "sent" if is_own_message else "received"
                    bg_color = self.sender_color_map.get(sender, '#ffffff')

                    # Common message structure
                    message_start = f'\n<div class="message {message_class} clearfix" style="background-color: {bg_color};">'
                    sender_div = f'<div class="sender">{sender}</div>'
                    content_start = '<div class="content">'
                    content_end = '</div>'
                    timestamp_span = f'<span class="timestamp">{self.re_render_with_day_of_week(timestamp)}</span>'
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
                    attachment_name = self.extract_attachment_name(content) if self.has_media else None
                    if attachment_name:
                        self.attachments_to_extract.add(attachment_name)
                        media_path = f"./media/{attachment_name}"
                        
                        # Main file: render media
                        if attachment_name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                            main_f.write(f'<img class="media" src="{media_path}"><br>')
                        elif attachment_name.lower().endswith('.mp4'):
                            main_f.write(f'<video class="media" controls><source src="{media_path}" type="video/mp4"></video><br>')
                        elif attachment_name.lower().endswith('.opus'):
                            main_f.write(f'<audio class="media" controls><source src="{media_path}" type="audio/ogg"></audio><br>')
                        elif attachment_name.lower().endswith('.wav'):
                            main_f.write(f'<audio class="media" controls><source src="{media_path}" type="audio/wav"></audio><br>')
                        elif attachment_name.lower().endswith('.mp3'):
                            main_f.write(f'<audio class="media" controls><source src="{media_path}" type="audio/mpeg"></audio><br>')
                        elif attachment_name.lower().endswith('.m4a'):
                            main_f.write(f'<audio class="media" controls><source src="{media_path}" type="audio/mp4"></audio><br>')
                        else:
                            main_f.write(f'<a href="{media_path}">📎 {attachment_name}</a><br>')
                        
                        # Media-linked file: always show as link
                        media_f.write(f'<a href="{media_path}">📎 {attachment_name}</a><br>')

                    # Add the message content to both files
                    cleaned_content = self.clean_message_content(content)
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
                    
                    message_count += 1

            loop_end_time = time.time()
            print(f"  Processed {message_count} messages in {loop_end_time - loop_start_time:.2f} seconds")

            # Write footer to both files
            footer = """
</div>
</body>
</html>"""
            main_f.write(footer)
            media_f.write(footer)
        
    
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
    print(file_path.as_posix())
    webbrowser.open(f"file://{file_path.as_posix()}")

def main():
    print(f"Welcome to chat-export v{version}")
    print("----------------------------------------")
    print("Select the WhatsApp chat export ZIP file you want to convert to HTML.")
    success = False
    try:
        selected_zip_file = browse_zip_file()
        if not selected_zip_file:
            raise FileNotFoundError("No file selected.")
        print(f"\nProcessing selected file: {selected_zip_file}...")
        renderer = WhatsAppChatRenderer(selected_zip_file)
        renderer.process_chat()
        print(f'\n{renderer.html_filename} and {renderer.html_filename_media_linked} have been created in the "{renderer.output_dir}" directory\n("{os.path.abspath(renderer.output_dir)}").')
        open_in_browser = input("\nWould you like to open them in the browser? [Y/n]: ").strip().lower()
        if open_in_browser != 'n':
            if renderer.has_media:
                open_html_file_in_browser(Path(renderer.output_dir)/renderer.html_filename_media_linked)
            open_html_file_in_browser(Path(renderer.output_dir)/renderer.html_filename)
        success = True
    
    except FileNotFoundError as e:
        print(f"\nError: {e}")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        print(traceback.format_exc())

    if success and input("\nDo you like the tool and want to buy me a coffee? [y/N]: ").strip().lower() == 'y':
        webbrowser.open(donate_link)
    if not success:
        print("Press enter to exit")
        input()

if __name__ == "__main__":
    main()
