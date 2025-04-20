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

# Create component package with pkgbuild
pkgbuild \
  --identifier ch.matlon.chat-export \
  --version 1.0.0 \
  --install-location /usr/local/bin \
  --root dist \
  chat-export.pkg

# Create resources folder with HTML dialogs
mkdir -p resources

cat > resources/welcome.html <<EOL
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Welcome</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; }
    </style>
</head>
<body>
<h2>Welcome to the chat-export Installer</h2>
<p>This tool installs the <code>chat-export</code> command-line utility to <code>/usr/local/bin</code>.</p>
<p>Once installed, open the Terminal and type <code>chat-export</code> to get started.</p>
</body>
</html>
EOL

cat > resources/conclusion.html <<EOL
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Installation Complete</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; }
    </style>
</head>
<body>
<h2>Installation Complete</h2>
<p><code>chat-export</code> has been installed.</p>
<p>To run it:</p>
<ol>
  <li>Open the Terminal (e.g. via Spotlight Search)</li>
  <li>Type: <code>chat-export</code></li>
</ol>
<p>To uninstall it later, run:</p>
<pre>sudo rm /usr/local/bin/chat-export</pre>
</body>
</html>
EOL

# Create distribution XML
cat > distribution.xml <<EOL
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1.0">
  <title>chat-export Installer</title>
  <welcome file="welcome.html"/>
  <conclusion file="conclusion.html"/>
  <pkg-ref id="ch.matlon.chat-export"/>
  <options customize="never" allow-external-scripts="no"/>
  <domains enable_anywhere="true"/>

  <choices-outline>
    <line choice="default"/>
  </choices-outline>

  <choice id="default" visible="false">
    <pkg-ref id="ch.matlon.chat-export"/>
  </choice>

  <pkg-ref id="ch.matlon.chat-export" version="1.0.0" auth="Root">chat-export.pkg</pkg-ref>
</installer-gui-script>
EOL

# Create final distribution-style .pkg with productbuild
productbuild \
  --distribution distribution.xml \
  --resources resources \
  --package-path . \
  chat-export-installer.pkg

# Sign and notarize
productsign --sign "Developer ID Installer: Andri Kraemer (9NCXVF3Y67)" chat-export-installer.pkg chat-export.pkg
sudo sntp -sS time.apple.com
xcrun notarytool submit chat-export.pkg --keychain-profile "notary-gfdev" --wait

xcrun stapler staple chat-export.pkg

# Cleanup
rm -rf dist/chat-export
rm -rf build
rm chat-export.spec
rm -rf resources
rm distribution.xml
rm chat-export.pkg  # Remove unsigned component .pkg

# Deactivate virtual environment
deactivate

# Final message
echo ""
echo "✅ Build complete: chat-export.pkg is signed, notarized, and stapled."
echo ""
echo "📦 To install, double-click chat-export.pkg."
echo "💡 After install, open Terminal and run: chat-export"
echo "🧹 To uninstall: sudo rm /usr/local/bin/chat-export"
echo ""
