#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Sub-Agent Delegation Control Layer Setup ==="
echo "(Local installation only - no online requests, no telemetry, no secrets touched)"
echo ""

# 1. Install global AGENTS.md (delegation & runtime policy hooks)
echo "[1/4] Installing global AGENTS.md..."
cp "$DIR/global/AGENTS.md" ~/AGENTS.md

# 2. Install global /delegate command
echo "[2/4] Installing global /delegate command..."
mkdir -p ~/.config/opencode/command
cp "$DIR/global/command/delegate.md" ~/.config/opencode/command/delegate.md

# 3. Install the runtime enforcement plugin (OpenCode loads ~/.config/opencode/plugins/*.js)
echo "[3/4] Installing runtime enforcement plugin..."
mkdir -p ~/.config/opencode/plugins
cp "$DIR/plugin/guard.js" ~/.config/opencode/plugins/guard.js

# 4. Install the standalone verifier CLI and make demo/test executable
echo "[4/4] Installing verifier CLI and setting permissions..."
chmod +x "$DIR/bin/subagent-guard" "$DIR/demo/run_demo.sh" "$DIR/demo/run_demo.py"
mkdir -p ~/.local/bin
ln -sf "$DIR/bin/subagent-guard" ~/.local/bin/subagent-guard

echo ""
echo "=== Done ==="
echo "- Global hook:        ~/AGENTS.md"
echo "- Slash command:      ~/.config/opencode/command/delegate.md"
echo "- Enforcement plugin: ~/.config/opencode/plugins/guard.js"
echo "- Verifier CLI:       ~/.local/bin/subagent-guard"
echo ""
echo "The plugin is INERT until a delegation contract exists."
echo "Activate per project by creating:  <project>/.opencode/delegation-contract.json"
echo "or by setting:                     DELEGATION_CONTRACT=/abs/path/contract.json"
echo ""
echo "Verify enforcement:  node \"$DIR/test/guard-plugin.test.mjs\""
echo "Verify boundaries:   \"$DIR/demo/run_demo.sh\""
