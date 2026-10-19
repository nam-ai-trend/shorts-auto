import assert from "node:assert/strict";
import { test } from "node:test";

import { buildMcpServerConfig, upsertCodexConfig, upsertMcpJsonConfig } from "./register.mjs";

const nodePath = "/opt/homebrew/bin/node";
const serverPath = "/repo/tools/higgsfield-mcp/server.mjs";

test("builds the shared Higgsfield MCP server config", () => {
  assert.deepEqual(buildMcpServerConfig({ nodePath, serverPath }), {
    command: nodePath,
    args: [serverPath],
    disabled: false
  });
});

test("upserts Codex config without duplicating the Higgsfield server", () => {
  const first = upsertCodexConfig("model = \"gpt-5\"\n", { nodePath, serverPath });
  const second = upsertCodexConfig(first, { nodePath, serverPath });

  assert.equal((second.match(/\[mcp_servers\.higgsfield\]/g) ?? []).length, 1);
  assert.match(second, /command = "\/opt\/homebrew\/bin\/node"/);
  assert.match(second, /args = \["\/repo\/tools\/higgsfield-mcp\/server\.mjs"\]/);
  assert.match(second, /startup_timeout_sec = 120/);
});

test("upserts JSON MCP config while preserving existing servers", () => {
  const json = JSON.stringify({
    mcpServers: {
      "notebooklm-mcp": {
        command: "/Users/gwn/.local/bin/notebooklm-mcp",
        disabled: false
      }
    }
  });

  const updated = JSON.parse(upsertMcpJsonConfig(json, { nodePath, serverPath }));

  assert.equal(updated.mcpServers["notebooklm-mcp"].command, "/Users/gwn/.local/bin/notebooklm-mcp");
  assert.deepEqual(updated.mcpServers.higgsfield, {
    command: nodePath,
    args: [serverPath],
    disabled: false
  });
});
