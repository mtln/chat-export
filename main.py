import zipfile
import os
from datetime import datetime, date
import re
from pathlib import Path
import shutil
import sys
import webbrowser


version = "0.3.0"

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
            'ios': re.compile(r'\[(\d{1,2}.\d{1,2}.\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?)\] (.*?): (.*)'),
            'android': re.compile(r'(\d{1,2}.\d{1,2}.\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?) - (.*?): (.*)')
        }
        self.message_date_format = "%d.%m.%y"
        self.own_name = None
        self.attachments_to_extract = set()
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
        # Various attachment markers in different languages
        self.attachment_patterns = [
            # iOS patterns
            r'<(?:Anhang|attached|adjunto|joint|allegato|anexado):\s*([^>]+)>',
            
            # Android patterns
            # English
            r'(.+?) \(file attached\)',
            # German
            r'(.+?) \(Datei angehängt\)',
            # Spanish
            r'(.+?) \(archivo adjunto\)',
            # French
            r'(.+?) \(fichier joint\)',
            # Italian
            r'(.+?) \(file allegato\)',
            # Portuguese
            r'(.+?) \(arquivo anexado\)',
        ]
        self.has_media = False
        self.from_date = None
        self.until_date = None
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

        first_line_date = first_line.split(',')[0].replace('[', '')
        # find first non-digit in the date string
        for char in first_line_date:
            if not char.isdigit():
                deliminator = char
                break
        
        # check if year is 2 or 4 digits
        year_pattern = '%y' if len(first_line_date.split(deliminator)[2]) == 2 else '%Y'
        day_before_month = True
        for line in chat_content.split('\n'):
            if not pattern.match(line):
                continue
            date_str = line.replace('[', '').split(',')[0]
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
        raise ValueError(f"Invalid date format. Please use DD.MM.YYYY, MM/DD/YYYY, DD.MM.YY, or MM/DD/YY")

    def parse_message_date(self, date_str):
        """Parse the date from a message timestamp."""
        # Remove time part
        date_str = date_str.split(',')[0]
        return datetime.strptime(date_str, self.message_date_format).date()


    def is_message_in_date_range(self, timestamp):
        """Check if message timestamp falls within the specified date range."""
        msg_date = self.parse_message_date(timestamp)
        if self.from_date and msg_date < self.from_date:
            return False
        if self.until_date and msg_date > self.until_date:
            return False
        return True

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

        media_in_zip = set()

        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
            # Extract media files
            for file in zip_ref.namelist():
                if file.lower() == '_chat.txt':
                    self.is_ios = True
                if file != f"{zip_base_name}.txt" and file != '_chat.txt':
                    # zip_ref.extract(file, self.media_dir)
                    media_in_zip.add(file)
                    self.has_media = True
            
            # Find the chat file using the zip file's name or _chat.txt for iOS
            chat_file = '_chat.txt' if self.is_ios else f"{zip_base_name}.txt"
            
            # Check if the chat file exists in the zip archive
            if chat_file not in zip_ref.namelist():
                raise FileNotFoundError(f"The chat file '{chat_file}' does not exist in the ZIP archive. Not a valid WhatsApp export zip.")

            
            with zip_ref.open(chat_file) as f:
                chat_content = f.read().decode('utf-8')
        if self.has_media:
            print(f"ZIP file is an {'iOS' if self.is_ios else 'Android'} export with media/attachments.")
        else:
            print(f"ZIP file is an {'iOS' if self.is_ios else 'Android'} export without media/attachments.")
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
      
        print("Writing HTML...")
        # Write HTML file
        with open(os.path.join(self.output_dir, self.html_filename), 'w', encoding='utf-8') as f:
            f.write(self.generate_html(chat_content, render_attachments=True))
        if self.has_media:
            with open(os.path.join(self.output_dir, self.html_filename_media_linked), 'w', encoding='utf-8') as f:
                f.write(self.generate_html(chat_content, render_attachments=False))
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
        for pattern in self.attachment_patterns:
            match = re.search(pattern, content)
            if match:
                # Return the first group if it exists, otherwise the full match
                result = match.group(1) if match.groups() else match.group(0)
                return result
        return None

    def clean_message_content(self, content):
        """Remove attachment markers from message content."""
        cleaned_content = content
        for pattern in self.attachment_patterns:
            cleaned_content = re.sub(pattern, '', cleaned_content)
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

    def generate_html(self, chat_content, render_attachments):
        html = """
        <!DOCTYPE html>
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
        <h1>PLACEHOLDER_CHAT_NAME</h1>
        """.replace('PLACEHOLDER_CHAT_NAME', self.chat_name)
        if self.from_date or self.until_date:
            date_range = f"Filtered: {self.from_date.strftime(self.message_date_format) if self.from_date else 'start'} to {self.until_date.strftime(self.message_date_format) if self.until_date else 'end'}"
            html += f'<p style="color: #667781;">{date_range}</p>'
        
        pattern = self.chat_patterns['ios'] if self.is_ios else self.chat_patterns['android']
        for line in chat_content.split('\n'):
            match = pattern.match(line)
            if match:
                timestamp, sender, content = match.groups()
                
                # Determine message alignment and background color
                is_own_message = sender == self.own_name
                message_class = "sent" if is_own_message else "received"
                bg_color = self.sender_color_map.get(sender, '#ffffff')

                html += f'<div class="message {message_class} clearfix" style="background-color: {bg_color};">'
                html += f'<div class="sender">{sender}</div>'
                html += '<div class="content">'
                
                # Check if the message contains media
                # Check for attachments using the new patterns
                attachment_name = self.extract_attachment_name(content)
                if attachment_name:
                    self.attachments_to_extract.add(attachment_name)
                    media_path = f"./media/{attachment_name}"
                    if render_attachments:
                        if attachment_name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                            html += f'<img class="media" src="{media_path}"><br>'
                        elif attachment_name.lower().endswith('.mp4'):
                            html += f'<video class="media" controls><source src="{media_path}" type="video/mp4"></video><br>'
                        elif attachment_name.lower().endswith('.opus'):
                            html += f'<audio class="media" controls><source src="{media_path}" type="audio/ogg"></audio><br>'
                        elif attachment_name.lower().endswith('.wav'):
                            html += f'<audio class="media" controls><source src="{media_path}" type="audio/wav"></audio><br>'
                        elif attachment_name.lower().endswith('.mp3'):
                            html += f'<audio class="media" controls><source src="{media_path}" type="audio/mpeg"></audio><br>'
                        elif attachment_name.lower().endswith('.m4a'):
                            html += f'<audio class="media" controls><source src="{media_path}" type="audio/mp4"></audio><br>'
                        else:
                            html += f'<a href="{media_path}">📎 {attachment_name}</a><br>'
                    else:
                        html += f'<a href="{media_path}">📎 {attachment_name}</a><br>'


                
                # Add the message content
                cleaned_content = self.clean_message_content(content)
                if cleaned_content:
                    html += f'{cleaned_content}'
                html += '</div>'
                html += f'<span class="timestamp">{timestamp}</span>'
                html += '</div>'
                

        html += """
        </div>
        </body>
        </html>
        """
        return html

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
    print(f"Welcome to WhatsAppChatConverter v{version}")
    print("----------------------------------------")
    print("Select the WhatsApp chat export ZIP file you want to convert to HTML.")
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
    
    except FileNotFoundError as e:
        print(f"\nError: {e}")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
    if input("\nDo you like the tool and want to buy me a coffee? [Y/n]: ").strip().lower() != 'n':
            webbrowser.open(donate_link)
