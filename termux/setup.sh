#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

# Run this script manually inside official Termux (F-Droid or GitHub release).
pkg update -y
pkg install -y python git nodejs-lts
npm install --global @qwen-code/qwen-code
mkdir -p "$HOME/.local/bin" "$HOME/.termux"
cp "$(dirname "$0")/agent.py" "$HOME/.local/bin/qwen-github-agent.py"
chmod 700 "$HOME/.local/bin/qwen-github-agent.py"
if grep -q '^allow-external-apps=' "$HOME/.termux/termux.properties" 2>/dev/null; then
  sed -i 's/^allow-external-apps=.*/allow-external-apps=true/' "$HOME/.termux/termux.properties"
else
  printf '\nallow-external-apps=true\n' >> "$HOME/.termux/termux.properties"
fi
termux-reload-settings || true
printf '\nTermux agent installed. Next: Android Settings > Apps > Qwen GitHub Agent > Permissions > Additional permissions > Run commands in Termux.\n'
