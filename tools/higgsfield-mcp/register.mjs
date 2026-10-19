#!/usr/bin/env node

import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function repoRoot() {
  return path.resolve(new URL("../..", import.meta.url).pathname);
}

function defaultNodePath() {
  if (process.env.NODE_PATH_FOR_MCP) {
    return process.env.NODE_PATH_FOR_MCP;
  }
  if (fs.existsSync("/opt/homebrew/bin/node")) {
    return "/opt/homebrew/bin/node";
  }
  return process.execPath;
}

function defaultServerPath() {
  return path.join(repoRoot(), "tools", "higgsfield-mcp", "server.mjs");
}

export function buildMcpServerConfig({ nodePath, serverPath }) {
  return {
    command: nodePath,
    args: [serverPath],
    disabled: false
  };
}

export function upsertCodexConfig(toml, { nodePath, serverPath }) {
  const block = [
    "[mcp_servers.higgsfield]",
    `command = "${nodePath}"`,
    `args = ["${serverPath}"]`,
    "startup_timeout_sec = 120",
    ""
  ].join("\n");
  const sectionPattern = /\n?\[mcp_servers\.higgsfield\][\s\S]*?(?=\n\[[^\n]+\]|$)/;

  if (sectionPattern.test(toml)) {
    return toml.replace(sectionPattern, `\n${block}`).trimEnd() + "\n";
  }
  return `${toml.trimEnd()}\n\n${block}`;
}

export function upsertMcpJsonConfig(json, { nodePath, serverPath }) {
  const data = json.trim() ? JSON.parse(json) : {};
  data.mcpServers ||= {};
  data.mcpServers.higgsfield = buildMcpServerConfig({ nodePath, serverPath });
  return `${JSON.stringify(data, null, 2)}\n`;
}

function writeWithBackup(filePath, nextContent) {
  const current = fs.existsSync(filePath) ? fs.readFileSync(filePath, "utf8") : "";
  if (current === nextContent) {
    return "unchanged";
  }
  if (fs.existsSync(filePath)) {
    fs.copyFileSync(filePath, `${filePath}.bak-higgsfield`);
  } else {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
  }
  fs.writeFileSync(filePath, nextContent);
  return "updated";
}

export function registerHiggsfieldMcp({
  homeDir = os.homedir(),
  nodePath = defaultNodePath(),
  serverPath = defaultServerPath()
} = {}) {
  const codexConfig = path.join(homeDir, ".codex", "config.toml");
  const geminiConfigs = [
    path.join(homeDir, ".gemini", "config", "mcp_config.json"),
    path.join(homeDir, ".gemini", "antigravity-ide", "mcp_config.json")
  ];

  const results = [];
  const codexCurrent = fs.existsSync(codexConfig) ? fs.readFileSync(codexConfig, "utf8") : "";
  results.push({
    file: codexConfig,
    state: writeWithBackup(codexConfig, upsertCodexConfig(codexCurrent, { nodePath, serverPath }))
  });

  for (const configPath of geminiConfigs) {
    const current = fs.existsSync(configPath) ? fs.readFileSync(configPath, "utf8") : "{}";
    results.push({
      file: configPath,
      state: writeWithBackup(configPath, upsertMcpJsonConfig(current, { nodePath, serverPath }))
    });
  }

  return results;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const results = registerHiggsfieldMcp();
  for (const result of results) {
    process.stdout.write(`${result.state}: ${result.file}\n`);
  }
  process.stdout.write("Restart Codex or Antigravity so the Higgsfield MCP server is loaded.\n");
}
