# chat-export: Convert WhatsApp Chats to HTML

This tool converts a WhatsApp chat export into two HTML formats: one with inline media (such as images, videos, and audio files) and a compact version with media links.


Video Tutorial (still refers to the previously used tool name instead of `chat-export`, doesn't cover new features like the non-interactive CLI mode yet):  
[![YouTube](https://img.youtube.com/vi/s1dMO8pjkC8/0.jpg)](https://www.youtube.com/watch?v=s1dMO8pjkC8)"

## Binary Release Downloads
* Windows: [chat-export.exe](https://github.com/mtln/chat-export/releases/latest/download/chat-export.exe)
* Mac: [chat-export-installer.pkg](https://github.com/mtln/chat-export/releases/latest/download/chat-export-installer.pkg)


## Why is this useful?
The HTML export is:

* **Printable:** You can print the chat or save as a PDF.
* **Searchable:** You can search for specific messages in the browser.
* **Shareable:** You can share the chat with others, but make sure to get consent from all other participants first.
* **Durable:** You can keep the chat as a record for years to come. Apps come and go. Plain HTML is here to stay.
* **Automatable:** With the non-interactive CLI mode, you can script batch processing of multiple chat exports or integrate the tool into other workflows.

Maybe you want to:

* keep a record of a conversation with a former loved one, friend, or business partner. You want to delete the chat from your phone, but you don’t want to lose the memories.
* save a chat with important information, such as addresses, phone numbers, or other data.
* keep a chat with a person who has passed away.
* export just an excerpt of a chat from a specific date range.
* archive a chat before freeing up space on your phone by deleting photos, videos, and other documents that were part of the chat.
* ask another chat participant who still has a complete version of the chat (including all pictures) on his or her phone to send you a chat export, so you can convert and archive it.
* batch process multiple chat exports automatically using the CLI mode.
* integrate chat conversion into backup or archival scripts.
* process chat exports on headless servers or in automated workflows.

Furthermore, the tool is [open-source](https://github.com/mtln/chat-export) and runs offline on your computer, so you can be sure that your data is not being sent to any server.  
And by the way, it’s free! If you find it useful, you can [donate](https://donate.stripe.com/3csfZLaIj5JE6dO4gg).

## Instructions

1. **Export the Chat:** Begin by exporting a chat from the WhatsApp app, preferably with media included. For detailed instructions, refer to [WhatsApp FAQ](https://faq.whatsapp.com/search?helpref=search&query=%20export%20chat).
You can for example save it on Google Drive or Dropbox or send it to yourself with WhatsApp.

2. **Transfer the File:** Move the exported ZIP file to your computer. If you have sent it to yourself with WhatsApp, you can download it with WhatsApp Web or with the WhatsApp App on your computer. Delete the WhatsApp message afterwards to save space.

3. **Install and Run the Tool:** 

### Option 1: Download Binary Executables: Easy for non-technical users

   If you don't know what Python is and just want to use the tool without having to deal with technical details, you can download the binary executables.
   
   - For Windows, download [chat-export.exe](https://github.com/mtln/chat-export/releases/latest/download/chat-export.exe).

   Because the .exe is unsigned, you will see a warning, but after clicking on "More Information" you should have the option to run it anyway. An EV code signing certificate for Windows costs a lot. If I get enough donations, I will buy one, so I can release signed exe files.

   - For Mac, download [chat-export-installer.pkg](https://github.com/mtln/chat-export/releases/latest/download/chat-export-installer.pkg)

   Once installed on Mac:

   1. Open the **Terminal** app (e.g. by typing "terminal" in Spotlight Search).
   2. Type: `chat-export`
    
   This will start the chat export tool from anywhere in the terminal.

   To uninstall `chat-export` from Mac, open the Terminal and run: `sudo rm /usr/local/bin/chat-export`

   The executables have been built with pyinstaller.

### Option 2: Install via pip
   
   If you have Python installed, you can install chat-export as a command-line tool:
   ```
   pip install chat-export
   ```
   
   **Optional: Install with platform-specific dependencies for native file dialogs**
   
   For better user experience with native file picker dialogs, you can install platform-specific dependencies:
   
   **On macOS:**
   ```
   pip install chat-export[macos]
   ```
   
   **On Windows:**
   ```
   pip install chat-export[windows]
   ```
   
      
   *Note: Without these optional dependencies, the tool will fall back to command-line input for file selection or use tkinter (if available) for file dialogs. If you're planning to use the tool in non-interactive mode, you don't need to install these dependencies.*
   
   After installation, you can run it from anywhere in your terminal:

   ```
   chat-export
   ```

   or
   ```
   chat-export --help
   ```

   To uninstall:
   ```
   pip uninstall chat-export
   ```

#### Using uv tool instead of pip
   If you have uv installed, you can use `uv tool install` instead of `pip install`. This is perfect for tools like chat-export because it will install the dependencies in a virtual environment and not in the global environment - while still making the tool available globally in your shell / path. 

   
   `uv tool install chat-export[windows]` 
   or 
   `uv tool install chat-export[macos]` 
   or just 
   `uv tool install chat-export` 
   uninstall with: 
   `uv tool uninstall chat-export`
   

###Option 3: Run Directly (No Installation)
   
   If Python is installed on your Windows, Mac or Linux computer, run the tool directly (no pip installation required, no venv required, no additional dependencies required because it's just vanilla standard lib Python in a single scriptfile, always run the latest up to date version directly from GitHub) with the following command:
     ```
     python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mtln/chat-export/refs/heads/main/main.py').read().decode())"
     ```
     or
     ```
     python3 -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mtln/chat-export/refs/heads/main/main.py').read().decode())"
     ```
     Options for special features, such as `--embed-media` or `--output-dir`, can be passed as command line arguments:
     ```
     python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mtln/chat-export/refs/heads/main/main.py').read().decode())" --embed-media --output-dir "C:\temp"
     ```
     or
     ```
     python3 -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mtln/chat-export/refs/heads/main/main.py').read().decode())" --embed-media --output-dir "C:\temp"
     ```

## Usage

The tool supports both interactive and non-interactive modes:

### Interactive Mode (Default)

Just run `chat-export` in your terminal. Use CLI parameters to pass options for special features, such as `--output-dir` or `--embed-media`.

**CLI Parameters:**

`-o, --output-dir`: Base directory where the chat folder will be created (optional, default: current directory)
`--embed-media`: Embed media files as base64 in HTML instead of linking to external files (optional)


* After starting the tool, a file picker dialog will open. Select the ZIP file of the chat export you want to convert. If your installation does not support file dialogs, you will be prompted for the path to the ZIP file.
* You can enter start and end dates to export only a specific date range. If you leave the fields empty, the entire chat will be exported. **If the terminal window doesn't accept your keyboard input, click with your mouse right after the colon in `Enter the number corresponding to your name:`** to set the focus to the terminal window.
* A list of chat participants will appear. Select your name so that your messages are displayed in green chat bubbles, just like on WhatsApp.
* Once the conversion completes, you can choose to open the HTML files immediately in your browser (just hit enter). From there, you can save the chat as a PDF or print it if needed.

### Command Line Interface (Non-Interactive Mode)

For automation, scripting, or when you know all parameters in advance, you can use the non-interactive CLI mode. This mode processes the chat without any prompts and is perfect for batch processing or integration into other tools.

#### Media Embedding Options

The tool offers two approaches for handling media files:

**Default Behavior (External Media Files):**
- Creates a folder structure with HTML files and a separate `media/` folder
- Media files are extracted and linked to from the HTML
- Results in multiple files that need to be kept together
- Smaller HTML files, but requires managing multiple files

**Embedded Media (`--embed-media` option):**
- Creates a single self-contained HTML file with all media embedded as base64
- No external media files are created or needed
- Perfect for sharing, archiving, or when you want everything in one file
- Larger HTML file size, but completely portable

**Basic Usage:**
```
chat-export -n -z "path/to/chat.zip" -p "Your Name"
```

**CLI Parameters:**

- `-n, --non-interactive`: Enable non-interactive mode (required)
- `-z, --zip-file`: Path to WhatsApp chat export ZIP file (required)
- `-p, --participant`: Your name exactly as it appears in the chat (required)
- `--from-date`: Optional start date for filtering (formats: DD.MM.YYYY, MM/DD/YYYY, DD.MM.YY, MM/DD/YY)
- `--until-date`: Optional end date for filtering
- `-o, --output-dir`: Base directory where the chat folder will be created (default: current directory)
- `--embed-media`: Embed media files as base64 in HTML instead of linking to external files (optional)


**Examples:**

Basic conversion:
```
chat-export -n -z "WhatsApp Chat with John.zip" -p "Your Name"
```
With absolute path to ZIP file (Windows):
```
chat-export -n -z "c:\temp\WhatsApp Chat with John.zip" -p "Your Name"
```

With date filtering:
```
chat-export -n -z "chat.zip" -p "Your Name" --from-date "01.01.2024" --until-date "31.12.2024"
```

Custom output directory (creates chat folder in /tmp instead of current directory):
```
chat-export -n -z "chat.zip" -p "Your Name" -o "/tmp"
```

Windows paths (important: no trailing backslash):
```
chat-export -n -z "chat.zip" -p "Your Name" -o "C:\temp"
```

With embedded media (creates a single self-contained HTML file):
```
chat-export -n -z "chat.zip" -p "Your Name" --embed-media
```

**Important Notes:**
- The participant name must match exactly as it appears in the chat (case-sensitive)
- If the participant name is not found, the tool will display all available participants and exit
- When using `--embed-media`, media files are encoded as base64 and embedded directly in the HTML, creating a single self-contained file that doesn't require external media files


* When printing an HTML page, most web browsers are set by default to exclude background colors to save ink or toner. If you want to include them, you need to enable background graphics in your browser settings. See the section below for instructions. 
   * **In Google Chrome**: Go to `Print` → `More settings` → Check `Background graphics`.
   * **In Mozilla Firefox**: Go to `File` → `Print` → `Page Setup` → Check `Print Background (colors & images)`.
   * **In Microsoft Edge**: Go to `Print` → `More settings` → Check `Background graphics`.


## Supported languages
WhatsApp chat exports vary depending on your phone’s system language. 

chat-export has been tested with many languages and regional settings.

If it doesn't work for your language, please let me know.

## Supported Operating Systems

* Windows
* Mac
* Linux

## Limitations
There is information in chats, that is not included in the export.zip created by WhatsApp. As a consequence, this information cannot be rendered by chat-export.

This includes:

* Reactions (thumbs up and other emojis that are not a stand-alone message, but created by long tapping a previous message)
* Message relations (in WhatsApp, you can right-swipe a previous message and then write a message in relation to this)
* Chat group metadata (e.g. list of all members, admins, ...)

## Disclaimer
chat-export comes with no warranty. Use it responsibly and respect the privacy of other chat participants. The tool is not affiliated with WhatsApp or Meta.
