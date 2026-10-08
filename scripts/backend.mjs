// Runs a command with the backend virtualenv's Python, on Windows or macOS/Linux.
// Usage: node scripts/backend.mjs <python args...>
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const backendDir = join(dirname(fileURLToPath(import.meta.url)), "..", "backend");
const python =
  process.platform === "win32"
    ? join(backendDir, ".venv", "Scripts", "python.exe")
    : join(backendDir, ".venv", "bin", "python");

if (!existsSync(python)) {
  console.error(`Backend virtualenv not found at ${python}. Run "npm run setup" first.`);
  process.exit(1);
}

const child = spawn(python, process.argv.slice(2), { cwd: backendDir, stdio: "inherit" });
child.on("exit", (code) => process.exit(code ?? 1));
