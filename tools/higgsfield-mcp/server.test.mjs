import assert from "node:assert/strict";
import { test } from "node:test";

import { createHiggsfieldMcpServer } from "./server.mjs";

test("lists Higgsfield MCP tools", async () => {
  const server = createHiggsfieldMcpServer({ runCommand: async () => ({ stdout: "{}", stderr: "", exitCode: 0 }) });

  const response = await server.handle({
    jsonrpc: "2.0",
    id: 1,
    method: "tools/list"
  });

  assert.equal(response.id, 1);
  assert.equal(response.result.tools.some((tool) => tool.name === "higgsfield_workspace_list"), true);
  assert.equal(response.result.tools.some((tool) => tool.name === "higgsfield_generate"), true);
});

test("workspace list calls the Higgsfield CLI with json output", async () => {
  const calls = [];
  const server = createHiggsfieldMcpServer({
    runCommand: async (command, args) => {
      calls.push([command, args]);
      return { stdout: '[{"id":"workspace-1"}]', stderr: "", exitCode: 0 };
    }
  });

  const response = await server.handle({
    jsonrpc: "2.0",
    id: 2,
    method: "tools/call",
    params: {
      name: "higgsfield_workspace_list",
      arguments: {}
    }
  });

  assert.deepEqual(calls, [["/opt/homebrew/bin/higgsfield", ["workspace", "list", "--json"]]]);
  assert.equal(response.result.content[0].type, "text");
  assert.match(response.result.content[0].text, /workspace-1/);
});

test("generate builds a guarded wait command", async () => {
  const calls = [];
  const server = createHiggsfieldMcpServer({
    runCommand: async (command, args) => {
      calls.push([command, args]);
      return { stdout: "https://example.com/result.mp4", stderr: "", exitCode: 0 };
    }
  });

  await server.handle({
    jsonrpc: "2.0",
    id: 3,
    method: "tools/call",
    params: {
      name: "higgsfield_generate",
      arguments: {
        model: "seedance_2_5",
        prompt: "cute claymation infographic scene",
        aspect_ratio: "9:16",
        duration: 6,
        wait: true
      }
    }
  });

  assert.deepEqual(calls, [
    [
      "/opt/homebrew/bin/higgsfield",
      [
        "generate",
        "create",
        "seedance_2_5",
        "--prompt",
        "cute claymation infographic scene",
        "--aspect_ratio",
        "9:16",
        "--duration",
        "6",
        "--wait"
      ]
    ]
  ]);
});
