// Minimal exec bridge for the Lingua workspace container.
//
// The deepagents engine runs in the orchestrator container, which has no node/npm and no
// access to the project's node_modules. This server lets it run shell commands *here* — in
// the workspace, co-located with node + Vite + the installed deps — exactly where OpenCode
// runs its own bash.
//
//   POST /exec  { "cmd": "npm install react-icons" }  ->  { stdout, stderr, exit }
//
// Internal-only: bound on the Docker network, never published to the host (see compose).
// It runs arbitrary commands by design — same trust level as OpenCode's bash tool.

import { exec } from "node:child_process";
import { createServer } from "node:http";

const PORT = Number(process.env.EXEC_PORT || 4097);
const CWD = process.env.PROJECT_SYMLINK || "/project-data/active";
const TIMEOUT_MS = 180_000;
const MAX_BUFFER = 10 * 1024 * 1024; // 10 MB of combined stdout/stderr

const server = createServer((req, res) => {
  if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
    return;
  }
  if (req.method !== "POST" || req.url !== "/exec") {
    res.writeHead(404);
    res.end("not found");
    return;
  }

  let body = "";
  req.on("data", (chunk) => {
    body += chunk;
    if (body.length > 1_000_000) req.destroy(); // cap request size
  });
  req.on("end", () => {
    let cmd;
    try {
      cmd = JSON.parse(body).cmd;
    } catch {
      res.writeHead(400);
      res.end("bad json");
      return;
    }
    if (!cmd || typeof cmd !== "string") {
      res.writeHead(400);
      res.end("missing cmd");
      return;
    }
    exec(
      cmd,
      { cwd: CWD, timeout: TIMEOUT_MS, maxBuffer: MAX_BUFFER, shell: "/bin/bash" },
      (err, stdout, stderr) => {
        const exit =
          err && typeof err.code === "number" ? err.code : err ? 1 : 0;
        res.writeHead(200, { "content-type": "application/json" });
        res.end(
          JSON.stringify({
            stdout: stdout || "",
            stderr: stderr || "",
            exit,
          }),
        );
      },
    );
  });
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`==> exec bridge listening on :${PORT} (cwd=${CWD})`);
});
