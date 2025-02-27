# once: xcrun notarytool store-credentials --apple-id "<omitted>" --team-id "<omitted>"
source .venv/bin/activate
pyinstaller --noconfirm --onefile --console --name "chat-export" --optimize "2" main.py
codesign --deep --force --verbose --options runtime --entitlements entitlements.plist --sign "Developer ID Application: Andri Kraemer (9NCXVF3Y67)" dist/chat-export
cd dist
zip chat-export.zip chat-export
xcrun notarytool submit chat-export.zip --keychain-profile "notary-gfdev" --wait
cd ..
cp -f dist/chat-export chat-export
rm -rf dist
rm -rf build
rm chat-export.spec
deactivate

