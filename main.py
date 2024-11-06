import zipfile
import os
from datetime import datetime
import re
from pathlib import Path
import shutil
import sys
import webbrowser


version = "0.1.0"

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
        # self.chat_pattern = re.compile(r'(\d{1,2}/\d{1,2}/\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?) - (.*?): (.*)')
        self.chat_pattern = re.compile(r'(\d{1,2}.\d{1,2}.\d{2,4}, \d{1,2}:\d{2}(?::\d{2})?) - (.*?): (.*)')
        self.own_name = None
        self.sender_colors = {
            'own': '#d9fdd3',    # WhatsApp green for own messages
            'default': '#ffffff', # White for the second sender
            # Additional colors for other senders
            'others': ['#f0e6ff', '#fff3e6', '#e6fff0', '#ffe6e6', '#e6f3ff']
        }
        self.sender_color_map = {}
        self.newline_marker = ' $NEWLINE$ '
        self.html_filename = 'chat.html'
        self.html_filename_media_linked = 'chat_media_linked.html'
        # Various attachment markers in different languages
        self.attachment_patterns = [
            # English
            r'<attached: (.+?)>',
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
            # Common WhatsApp format for images/videos
            r'‎?(IMG|VID)-\d{8}(?:-WA\d{4})?\.(?:jpg|jpeg|png|mp4|gif|webp)',
        ]
        self.has_media = False

    def get_senders(self, chat_content):
        senders = set()
        for line in chat_content.split('\n'):
            match = self.chat_pattern.match(line)
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

    def process_chat(self):
        # Clean output directory if it exists

        # Get the base name of the zip file without extension
        zip_base_name = Path(self.zip_path).stem

        with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
            # Extract media files
            for file in zip_ref.namelist():
                if file != f"{zip_base_name}.txt":
                    zip_ref.extract(file, self.media_dir)
                    self.has_media = True
            
            # Find the chat file using the zip file's name
            chat_file = f"{zip_base_name}.txt"
            
            # Check if the chat file exists in the zip archive
            if chat_file not in zip_ref.namelist():
                raise FileNotFoundError(f"The chat file '{chat_file}' does not exist in the ZIP archive. Not a valid WhatsApp export zip.")

            if os.path.exists(self.output_dir):
                print(f"Cleaning existing directory: {self.output_dir}")
                shutil.rmtree(self.output_dir)

                # Create fresh output directories
                os.makedirs(self.output_dir)
                os.makedirs(self.media_dir)
            with zip_ref.open(chat_file) as f:
                chat_content = f.read().decode('utf-8')

        # Preprocess the chat content to handle multi-line messages
        processed_content = []
        current_line = []
        
        for line in chat_content.split('\n'):
            # Check if line starts with a date pattern
            if self.chat_pattern.match(line):
                if current_line:
                    processed_content.append(''.join(current_line))
                current_line = [line]
            else:
                # If it's a continuation, add it with a <br>
                if current_line:
                    current_line.append(self.newline_marker + line)
                else:
                    # If somehow we start with a continuation line, just add it
                    current_line = [line]
        
        # Don't forget to add the last message
        if current_line:
            processed_content.append(''.join(current_line))

        # Join all processed lines with newlines
        chat_content = '\n'.join(processed_content)

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
      
        # Write HTML file
        with open(os.path.join(self.output_dir, self.html_filename), 'w', encoding='utf-8') as f:
            f.write(self.generate_html(chat_content, render_attachments=True))
        if self.has_media:
            with open(os.path.join(self.output_dir, self.html_filename_media_linked), 'w', encoding='utf-8') as f:
                f.write(self.generate_html(chat_content, render_attachments=False))

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
                # remove the Left-to-right_mark
                result = result.replace('‎','')
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
            </style>
        </head>
        <body>
        <div class="chat-container">
        <h1>PLACEHOLDER_CHAT_NAME</h1>
        """.replace("PLACEHOLDER_CHAT_NAME", self.chat_name)

        for line in chat_content.split('\n'):
            match = self.chat_pattern.match(line)
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
    print("--------------------------------")
    print("Select the WhatsApp chat export ZIP file you want to convert to HTML.")
    try:
        selected_zip_file = browse_zip_file()
        if not selected_zip_file:
            print("No file selected.")
            exit(0)
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
        sys.exit(1)
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
