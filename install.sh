#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== OpenCode Agent Setup ==="
echo ""

# 1. Install global AGENTS.md (delegation hooks)
echo "Installing global AGENTS.md..."
cp "$DIR/global/AGENTS.md" ~/AGENTS.md

# 2. Install global /delegate command
echo "Installing global /delegate command..."
mkdir -p ~/.config/opencode/command
cp "$DIR/global/command/delegate.md" ~/.config/opencode/command/delegate.md

echo ""
echo "=== Done ==="
echo "Open OpenCode in any project. The delegation hook is active."
echo ""
echo "Reminder: Set your API key in ~/.config/opencode/opencode.jsonc if not already done."
