// One-time setup: backend virtualenv + Python deps, frontend npm deps, .env from the example.
import { execSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const backendDir = join(root, "backend");
const run = (cmd, cwd = root) => {
  console.log(`\n> ${cmd}`);
  execSync(cmd, { cwd, stdio: "inherit" });
};

const systemPython = process.platform === "win32" ? "python" : "python3";
const venvPython =
  process.platform === "win32"
    ? join(backendDir, ".venv", "Scripts", "python.exe")
    : join(backendDir, ".venv", "bin", "python");

if (!existsSync(venvPython)) run(`${systemPython} -m venv .venv`, backendDir);
run(`"${venvPython}" -m pip install --upgrade pip`, backendDir);
run(`"${venvPython}" -m pip install -r requirements-dev.txt`, backendDir);
run("npm install", join(root, "frontend"));

if (!existsSync(join(root, ".env"))) {
  copyFileSync(join(root, ".env.example"), join(root, ".env"));
  console.log("\nCreated .env from .env.example. Add your GEMINI_API_KEY to it.");
}
for (const dir of ["data/base_resumes", "data/outputs"]) mkdirSync(join(root, dir), { recursive: true });

console.log("\nSetup complete. Start everything with: npm run dev");
