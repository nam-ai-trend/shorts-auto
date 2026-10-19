#!/usr/bin/env node

import { spawn } from "node:child_process";

export function buildDevProcesses() {
  return [
    {
      name: "api",
      command: "pnpm",
      args: ["dev:api"]
    },
    {
      name: "web",
      command: "pnpm",
      args: ["dev:web"]
    }
  ];
}

function prefixOutput(name, stream, chunk) {
  const lines = chunk.toString().split(/\r?\n/);
  for (const line of lines) {
    if (line.length > 0) {
      stream.write(`[${name}] ${line}\n`);
    }
  }
}

export function startDevProcesses(processes = buildDevProcesses()) {
  const children = processes.map((processConfig) => {
    const child = spawn(processConfig.command, processConfig.args, {
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"]
    });
    child.stdout.on("data", (chunk) => prefixOutput(processConfig.name, process.stdout, chunk));
    child.stderr.on("data", (chunk) => prefixOutput(processConfig.name, process.stderr, chunk));
    child.on("exit", (code, signal) => {
      const reason = signal ? `signal ${signal}` : `code ${code}`;
      process.stderr.write(`[${processConfig.name}] exited with ${reason}\n`);
    });
    return child;
  });

  function stopAll() {
    for (const child of children) {
      if (!child.killed) {
        child.kill("SIGINT");
      }
    }
  }

  process.on("SIGINT", () => {
    stopAll();
    setTimeout(() => process.exit(130), 100);
  });
  process.on("SIGTERM", () => {
    stopAll();
    setTimeout(() => process.exit(143), 100);
  });

  return children;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  startDevProcesses();
}
