# Convert WhatsApp Chat to HTML

This tool converts a WhatsApp chat export into two HTML formats: one with inline media (such as images, videos, and audio files) and a compact version with media links.

## Instructions

1. **Export the Chat:** Begin by exporting a chat from the WhatsApp app, preferably with media included. For detailed instructions, refer to [WhatsApp FAQ](https://faq.whatsapp.com/search?helpref=search&query=%20export%20chat).

2. **Transfer the File:** Move the exported ZIP file to your computer.

3. **Download the Tool:** 
   - For Windows, download [WhatsAppChatConverter.exe](https://raw.githubusercontent.com/mtln/WhatsAppChatConverter/refs/heads/binary_releases/WhatsAppChatConverter.exe).

   You will have to copy the file away from your Downloads folder to another folder, e.g. Documents. Because the .exe is unsigned, you will see a warning, but after clicking on "More Information" you should have the option to run it anyway.

   **OR**

   - If Python is installed on your computer, run the tool directly (no installation required) with the following command:
     ```bash
     python -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mtln/WhatsAppChatConverter/refs/heads/main/main.py').read().decode())"
     ```
     or
     ```bash
     python3 -c "import urllib.request; exec(urllib.request.urlopen('https://raw.githubusercontent.com/mtln/WhatsAppChatConverter/refs/heads/main/main.py').read().decode())"
     ```

4. **Run the Tool:**
   - After starting the tool, a file picker dialog will open. Select the ZIP file of the chat export you want to convert.

5. **Identify Yourself:** A list of chat participants will appear. Select your name so that your messages are displayed in green chat bubbles, just like on WhatsApp. If the terminal window doesn’t accept your keyboard input, click right after the colon in `Enter the number corresponding to your name:`.

6. **Open HTML Files:** Once the conversion completes, you can choose to open the HTML files immediately in your browser. From there, you can save the chat as a PDF or print it if needed.

## Supported languages
WhatsApp chat exports vary depending on your phone’s system language. Currently, this tool has been tested with:

* German

## Supported Operating Systems

* Windows
