#!/usr/bin/env node

import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

const DEFAULT_HIGGSFIELD_BIN = process.env.HIGGSFIELD_BIN || "/opt/homebrew/bin/higgsfield";

const tools = [
  {
    name: "higgsfield_account_status",
    description: "Check Higgsfield account/workspace status. Use this before paid generation.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      properties: {}
    }
  },
  {
    name: "higgsfield_workspace_list",
    description: "List available Higgsfield workspaces.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      properties: {}
    }
  },
  {
    name: "higgsfield_workspace_set",
    description: "Select the Higgsfield billing workspace by ID.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      properties: {
        workspace_id: { type: "string", minLength: 1 }
      },
      required: ["workspace_id"]
    }
  },
  {
    name: "higgsfield_model_list",
    description: "List Higgsfield models. Use before choosing image or video generation models.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      properties: {
        image: { type: "boolean" },
        video: { type: "boolean" },
        audio: { type: "boolean" }
      }
    }
  },
  {
    name: "higgsfield_model_get",
    description: "Inspect one Higgsfield model schema by model id.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      properties: {
        model: { type: "string", minLength: 1 }
      },
      required: ["model"]
    }
  },
  {
    name: "higgsfield_generate",
    description:
      "Create a Higgsfield generation job through the CLI. This can spend credits; call only after the user explicitly wants generation.",
    inputSchema: {
      type: "object",
      additionalProperties: false,
      properties: {
        model: { type: "string", minLength: 1 },
        prompt: { type: "string" },
        image: { type: "string" },
        start_image: { type: "string" },
        end_image: { type: "string" },
        video: { type: "string" },
        audio: { type: "string" },
        aspect_ratio: { type: "string" },
        duration: { type: ["number", "string"] },
        resolution: { type: "string" },
        mode: { type: "string" },
        wait: { type: "boolean", default: true },
        wait_timeout: { type: "string" }
      },
      required: ["model"]
    }
  }
];

function textContent(text) {
  return {
    content: [
      {
        type: "text",
        text
      }
    ]
  };
}

function requireString(args, name) {
  const value = args?.[name];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${name} is required`);
  }
  return value.trim();
}

function addFlag(cliArgs, flag, value) {
  if (value === undefined || value === null || value === "") {
    return;
  }
  cliArgs.push(flag, String(value));
}

function buildCommand(toolName, rawArgs = {}) {
  const args = rawArgs && typeof rawArgs === "object" ? rawArgs : {};

  if (toolName === "higgsfield_account_status") {
    return ["account", "status", "--json"];
  }
  if (toolName === "higgsfield_workspace_list") {
    return ["workspace", "list", "--json"];
  }
  if (toolName === "higgsfield_workspace_set") {
    return ["workspace", "set", requireString(args, "workspace_id")];
  }
  if (toolName === "higgsfield_model_list") {
    const cliArgs = ["model", "list", "--json"];
    if (args.image) {
      cliArgs.push("--image");
    }
    if (args.video) {
      cliArgs.push("--video");
    }
    if (args.audio) {
      cliArgs.push("--audio");
    }
    return cliArgs;
  }
  if (toolName === "higgsfield_model_get") {
    return ["model", "get", requireString(args, "model"), "--json"];
  }
  if (toolName === "higgsfield_generate") {
    const cliArgs = ["generate", "create", requireString(args, "model")];
    addFlag(cliArgs, "--prompt", args.prompt);
    addFlag(cliArgs, "--image", args.image);
    addFlag(cliArgs, "--start-image", args.start_image);
    addFlag(cliArgs, "--end-image", args.end_image);
    addFlag(cliArgs, "--video", args.video);
    addFlag(cliArgs, "--audio", args.audio);
    addFlag(cliArgs, "--aspect_ratio", args.aspect_ratio);
    addFlag(cliArgs, "--duration", args.duration);
    addFlag(cliArgs, "--resolution", args.resolution);
    addFlag(cliArgs, "--mode", args.mode);
    if (args.wait !== false) {
      cliArgs.push("--wait");
    }
    addFlag(cliArgs, "--wait-timeout", args.wait_timeout);
    return cliArgs;
  }
  throw new Error(`Unknown tool: ${toolName}`);
}

function runCommand(command, args) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"]
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", (error) => {
      resolve({ stdout, stderr: `${stderr}${error.message}`, exitCode: 1 });
    });
    child.on("close", (exitCode) => {
      resolve({ stdout, stderr, exitCode: exitCode ?? 1 });
    });
  });
}

export function createHiggsfieldMcpServer({
  command = DEFAULT_HIGGSFIELD_BIN,
  runCommand: runner = runCommand
} = {}) {
  async function callTool(name, args) {
    const cliArgs = buildCommand(name, args);
    const result = await runner(command, cliArgs);
    const output = [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
    if (result.exitCode !== 0) {
      throw new Error(output || `Higgsfield command failed with exit code ${result.exitCode}`);
    }
    return textContent(output || "OK");
  }

  async function handle(message) {
    if (message.method === "initialize") {
      return {
        jsonrpc: "2.0",
        id: message.id,
        result: {
          protocolVersion: "2024-11-05",
          capabilities: {
            tools: {}
          },
          serverInfo: {
            name: "shorts-auto-higgsfield-mcp",
            version: "0.1.0"
          }
        }
      };
    }
    if (message.method?.startsWith("notifications/")) {
      return null;
    }
    if (message.method === "tools/list") {
      return {
        jsonrpc: "2.0",
        id: message.id,
        result: { tools }
      };
    }
    if (message.method === "tools/call") {
      try {
        const result = await callTool(message.params?.name, message.params?.arguments ?? {});
        return {
          jsonrpc: "2.0",
          id: message.id,
          result
        };
      } catch (error) {
        return {
          jsonrpc: "2.0",
          id: message.id,
          error: {
            code: -32000,
            message: error instanceof Error ? error.message : "Higgsfield MCP tool failed"
          }
        };
      }
    }
    return {
      jsonrpc: "2.0",
      id: message.id,
      error: {
        code: -32601,
        message: `Method not found: ${message.method}`
      }
    };
  }

  return { handle };
}

async function serveStdio() {
  const server = createHiggsfieldMcpServer();
  const rl = createInterface({
    input: process.stdin,
    crlfDelay: Infinity
  });

  for await (const line of rl) {
    if (!line.trim()) {
      continue;
    }
    const message = JSON.parse(line);
    const response = await server.handle(message);
    if (response) {
      process.stdout.write(`${JSON.stringify(response)}\n`);
    }
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  serveStdio().catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.stack : String(error)}\n`);
    process.exitCode = 1;
  });
}
