#!/bin/bash
set -e  # Exit on error

# Ensure credentials are stored (one-time setup)
# xcrun notarytool store-credentials --apple-id "<your-apple-id>" --team-id "<your-team-id>"

# Activate Python virtual environment
source .venv/bin/activate

# Build binary with PyInstaller
pyinstaller --noconfirm --onefile --console --name "chat-export" --optimize "2" main.py

# Code signing
codesign --deep --force --verbose --options runtime --entitlements entitlements.plist --sign "Developer ID Application: Andri Kraemer (9NCXVF3Y67)" dist/chat-export

# Create a notarizable DMG
hdiutil create -fs HFS+ -srcfolder dist -volname "Chat Export" -format UDZO -o chat-export.dmg

# Submit DMG for notarization
xcrun notarytool submit chat-export.dmg --keychain-profile "notary-gfdev" --wait

# Staple the notarization ticket to the DMG
xcrun stapler staple chat-export.dmg


# Cleanup
rm -rf dist/chat-export
rm -rf build
rm chat-export.spec

# Deactivate virtual environment
deactivate

echo "Build complete: dist/chat-export.dmg is signed, notarized, and stapled."
