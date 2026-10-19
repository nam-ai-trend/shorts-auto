# Higgsfield MCP Wrapper

Local MCP server that wraps the installed `higgsfield` CLI for Shorts Auto.

## Registered Clients

The server is registered by running:

```bash
pnpm setup:higgsfield-mcp
```

This updates:

- `/Users/gwn/.codex/config.toml`
- `/Users/gwn/.gemini/config/mcp_config.json`
- `/Users/gwn/.gemini/antigravity-ide/mcp_config.json`

Restart the client after registration so the MCP tools are loaded. Registration is persistent; do not repeat it every time unless the project path or config files change.

Authentication is separate from registration:

```bash
higgsfield auth login
higgsfield workspace list
higgsfield workspace set <workspace_id>
```

Run login again only when the session expires or a different account should be used.

## Command

```bash
/opt/homebrew/bin/node /Users/gwn/antigravity/16_shorts_auto/tools/higgsfield-mcp/server.mjs
```

## Tools

- `higgsfield_account_status`
- `higgsfield_workspace_list`
- `higgsfield_workspace_set`
- `higgsfield_model_list`
- `higgsfield_model_get`
- `higgsfield_generate`

`higgsfield_generate` can spend Higgsfield credits. Use status/model/list tools first, then call generation only after explicit user approval in the workflow.

## Local Verification

```bash
pnpm setup:higgsfield-mcp
node --test tools/higgsfield-mcp/server.test.mjs
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node tools/higgsfield-mcp/server.mjs
```
