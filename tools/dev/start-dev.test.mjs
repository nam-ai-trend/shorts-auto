import assert from "node:assert/strict";
import { test } from "node:test";

import { buildDevProcesses } from "./start-dev.mjs";

test("starts API and web dev processes", () => {
  const processes = buildDevProcesses();

  assert.deepEqual(
    processes.map((process) => process.name),
    ["api", "web"]
  );
  assert.equal(processes[0].command, "pnpm");
  assert.deepEqual(processes[0].args, ["dev:api"]);
  assert.equal(processes[1].command, "pnpm");
  assert.deepEqual(processes[1].args, ["dev:web"]);
});
