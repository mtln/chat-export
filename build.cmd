pyinstaller --noconfirm --onefile --console --name "chat-export" --optimize "2"  "chat_export/chat_export.py"
copy dist\chat-export.exe chat-export.exe
rm -rf dist
rm -rf build
rm chat-export.spec
