import re
import os
from datetime import datetime, timedelta
import base64
import mimetypes
import zipfile


THIS_SCRIPT = os.path.split(__file__)[-1]
INSTRUCTIONS = f"""
Usage: python {THIS_SCRIPT} your-filename.html your-mobile-export.zip

This script reads a WhatsApp chat export and prints out 
an HTML file with the chat messages and attached media.
To export, use WhatsApp on mobile, go to the chat, and
go to the contact info, then export chat to get your
zipfile.
""".strip()

def read_file_from_zip(zip_filename, target_filename):
    try:
        # Open the ZIP file
        with zipfile.ZipFile(zip_filename, 'r') as zip_file:
            # Check if the target file exists in the ZIP
            # print(zip_file.namelist())
            if target_filename in zip_file.namelist():
                # Read the content of the target file
                content = zip_file.read(target_filename)
                # print('read_file_from_zip', zip_filename, target_filename, len(content), type(content))
                # Return as text if needed
                return content if content else b'sorry bub, no content'
            else:
                raise FileNotFoundError(f"{target_filename} not found in {zip_filename}")
    except Exception as e:
        print(f"Error: {e}")
        return None

def wrap_dt(dt):
    return f"<br/><span class='when'>{dt} ET</span>"


def data_url(zip_fn, filename):
    #data = open(filename, "rb").read()
    data = read_file_from_zip(zip_fn, filename)
    if data is None:
        return f"Error: {filename} not found in {zip_fn}"
    b64_data = base64.b64encode(data)
    b64_text = b64_data.decode('utf-8')
    extension = os.path.splitext(filename)[1]
    if extension.startswith('.'): extension = extension[1:]
    if extension == 'jpg': extension = 'jpeg'
    if extension == 'webp': extension = 'webp' 
    url = f"data:image/{extension};base64,{b64_text}"
    return url

def exit_with_instructions():
    print(INSTRUCTIONS)
    exit(1)

def header_html():
    return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Slippery Slinky Scam</title>
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
    """.strip()

def _message_html_header(speaker, datetime, message, first_speaker=None):
    is_own_message = speaker == first_speaker
    message_class = "sent" if not is_own_message else "received"
    bg_color = '#ffffff' if is_own_message else '#f0f0f0'
    return f"""
    <div class="message {message_class} clearfix" style="background-color: {bg_color};">
    <div class="sender">{speaker}</div>
    <div class="content">
    """.strip()

def _message_html_footer(speaker, datetime, message, first_speaker=None):
    is_own_message = speaker == first_speaker
    return f"""
    </div>
    <span class="timestamp">{datetime}</span>
    </div>
    """.strip()

def _message_html_media_tag(zip_filename, attachment_name):
    media_path = data_url(zip_filename, attachment_name)
    if attachment_name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
        return f'<img class="media" src="{media_path}"><br>'
    elif attachment_name.lower().endswith('.mp4'):
        html = f'<video class="media" controls><source src="{media_path}" type="video/mp4"></video><br>'
    elif attachment_name.lower().endswith('.opus'):
        html = f'<audio class="media" controls><source src="{media_path}" type="audio/ogg"></audio><br>'
    elif attachment_name.lower().endswith('.wav'):
        html = f'<audio class="media" controls><source src="{media_path}" type="audio/wav"></audio><br>'
    elif attachment_name.lower().endswith('.mp3'):
        html = f'<audio class="media" controls><source src="{media_path}" type="audio/mpeg"></audio><br>'
    elif attachment_name.lower().endswith('.m4a'):
        html = f'<audio class="media" controls><source src="{media_path}" type="audio/mp4"></audio><br>'
    else:
        html = f'<a href="{media_path}">📎 {attachment_name}</a><br>'
    return html

def message_html(speaker, datetime, message, first_speaker, media_url, zip_filename=None):
    media_html = _message_html_media_tag(zip_filename, media_url) if media_url else ''
    message = message.replace("\n",'<br />') if message else ''
    return f"""
    {_message_html_header(speaker, datetime, message, first_speaker)}
        {message}
        {media_html}
    {_message_html_footer(speaker, datetime, message, first_speaker)}
    """.strip()

def footer_html():
    return """</div>\n</body>\n</html>"""

def validate_zip(zip_filename):
    zip_filename = sys.argv[-1]
    if not 'zip' in zip_filename:
        exit_with_instructions()
        exit(1)
    zip_mime = mimetypes.guess_type(zip_filename)[0]
    if zip_mime != 'application/zip':
        print(f"Error: {zip_filename} not a zip file")
        exit_with_instructions()

def extract_messages(data):
    # Regex to match the format
    pattern = r"\[(\d+/\d+/\d+, \d+:\d+:\d+[^[]*)\]([^:]*):([^[]*)"

    # Find all matches
    matches = re.findall(pattern, data, re.MULTILINE | re.DOTALL)

    # Process matches into a structured format
    parsed_messages = []
    for match in matches:
        if len(match) != 3:
            print(f"Error: match {match} does not have 3 parts")
            continue
        dt, speaker, message = match
        message = message.strip()
        if not message: continue
        msg = {
            "datetime": dt.strip(),
            "speaker": speaker.strip(),
            "message": message.strip()
        }
        if '<attached: ' in message:
            filename = message.split('<attached: ')[1].split('>')[0]
            msg['media'] = filename
            msg['message'] = message.replace(f"<attached: {filename}>", '')
        
        parsed_messages.append(msg) 
    return parsed_messages

def page_html(parsed_messages, zip_filename):
    pieces = [header_html()]
    first_speaker = parsed_messages[0]['speaker']
    for o in parsed_messages:
        message = o['message']
        media_filename = o.get('media')
        html = message_html(o['speaker'], o['datetime'], message, first_speaker, media_filename, zip_filename)
        pieces.append(html)
    pieces.append(footer_html())
    return "\n\n".join(pieces)


# Main

if __name__ == "__main__":
    # Input data
    import sys
    if len(sys.argv) < 3:
        exit_with_instructions()
    zip_filename = sys.argv[-1]
    html_filename = sys.argv[-2]

    # Validate the input
    validate_zip(zip_filename)

    # Read the chat data
    data = read_file_from_zip(zip_filename, '_chat.txt')
    if data is None: 
        print("Error: _chat.txt not found in {zip_filename}")
        exit_with_instructions()

    # Clean up the data
    data = (data
        .decode('utf-8','ignore')
        .replace("\u200e",' ')
        .replace("\u202f",' '))

    # Extract messages
    parsed_messages = extract_messages(data)

    # Generate HTML
    html = page_html(parsed_messages, zip_filename)
    with open(html_filename, 'w') as f:
        f.write(html)
    print(f"HTML written to {html_filename}")    