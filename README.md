# chat-export: Convert WhatsApp Chats to HTML

This tool converts a WhatsApp chat export into two HTML formats: one with inline media (such as images, videos, and audio files) and a compact version with media links.

Video Tutorial (still refers to the previously used tool name instead of `chat-export`):  
[![YouTube](https://img.youtube.com/vi/s1dMO8pjkC8/0.jpg)](https://www.youtube.com/watch?v=s1dMO8pjkC8)"

## Why is this useful?
The HTML export is:

* **Printable:** You can print the chat or save as a PDF.
* **Searchable:** You can search for specific messages in the browser.
* **Shareable:** You can share the chat with others, but make sure to get consent from all other participants first.
* **Durable:** You can keep the chat as a record for years to come. Apps come and go. Plain HTML is here to stay.

Maybe you want to:

* keep a record of a conversation with a former loved one, friend, or business partner. You want to delete the chat from your phone, but you don’t want to lose the memories.
* save a chat with important information, such as addresses, phone numbers, or other data.
* keep a chat with a person who has passed away.
* export just an excerpt of a chat from a specific date range.
* archive a chat before freeing up space on your phone by deleting photos, videos, and other documents that were part of the chat.
* ask another chat participant who still has a complete version of the chat (including all pictures) on his or her phone to send you a chat export, so you can convert and archive it.

Furthermore, the tool is [open-source](https://github.com/mtln/chat-export) and runs offline on your computer, so you can be sure that your data is not being sent to any server.  
And by the way, it’s free! If you find it useful, you can [donate](https://donate.stripe.com/3csfZLaIj5JE6dO4gg).

## Instructions

1. **Export the Chat:** Begin by exporting a chat from the WhatsApp app, preferably with media included. For detailed instructions, refer to [WhatsApp FAQ](https://faq.whatsapp.com/search?helpref=search&query=%20export%20chat).
You can for example save it on Google Drive or Dropbox or send it to yourself with WhatsApp.

2. **Transfer the File:** Move the exported ZIP file to your computer. If you have sent it to yourself with WhatsApp, you can download it with WhatsApp Web or with the WhatsApp App on your computer. Delete the WhatsApp message afterwards to save space.

3. **Download and Run the Tool:** 
   - For Windows, download [chat-export.exe](https://raw.githubusercontent.com/mtln/chat-export/refs/heads/binary_releases/ChatExport.exe).

   You will have to copy the file away from your Downloads folder to another folder, e.g. Documents. Because the .exe is unsigned, you will see a warning, but after clicking on "More Information" you should have the option to run it anyway.

   **OR**

   - If Python is installed on your Windows, Mac or Linux computer, run the tool directly (no installation required) with the following command:
     ```
     python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mtln/chat-export/refs/heads/main/main.py').read().decode())"
     ```
     or
     ```
     python3 -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mtln/chat-export/refs/heads/main/main.py').read().decode())"
     ```

**Usage**

* After starting the tool, a file picker dialog will open. Select the ZIP file of the chat export you want to convert. If your installation does not support file dialogs, you will be prompted for the path to the ZIP file.
* You can enter start and end dates to export only a specific date range. If you leave the fields empty, the entire chat will be exported. **If the terminal window doesn’t accept your keyboard input, click with your mouse right after the colon in `Enter the number corresponding to your name:`** to set the focus to the terminal window.
* A list of chat participants will appear. Select your name so that your messages are displayed in green chat bubbles, just like on WhatsApp. 

* Once the conversion completes, you can choose to open the HTML files immediately in your browser (just hit enter). From there, you can save the chat as a PDF or print it if needed.  

* When printing an HTML page, most web browsers are set by default to exclude background colors to save ink or toner. If you want to include them, you need to enable background graphics in your browser settings. See the section below for instructions. 
   * **In Google Chrome**: Go to `Print` → `More settings` → Check `Background graphics`.
   * **In Mozilla Firefox**: Go to `File` → `Print` → `Page Setup` → Check `Print Background (colors & images)`.
   * **In Microsoft Edge**: Go to `Print` → `More settings` → Check `Background graphics`.


## Supported languages
WhatsApp chat exports vary depending on your phone’s system language. Currently, this tool has been tested with:

* English
* German
* French
* Italian
* Spanish
* Portugese

If your language is not supported, please let me know.

## Supported Operating Systems

* Windows
* Mac
* Linux

## Disclaimer
chat-export comes with no warranty. Use it responsibly and respect the privacy of other chat participants. The tool is not affiliated with WhatsApp or Meta.
