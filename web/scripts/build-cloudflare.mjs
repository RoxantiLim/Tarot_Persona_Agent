import { cp, mkdir, mkdtemp, readFile, rename, stat, symlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const auxiliaryRoot = process.env.TAROT_BUILD_DIR ?? (process.platform === "win32"
  ? "E:/for-LLM/AUXI/Tarot_Persona_Agent/web-builds" : "/tmp/tarot-persona-web-builds");
await mkdir(auxiliaryRoot, { recursive: true });
const staging = await mkdtemp(path.join(auxiliaryRoot, "cloudflare-"));
console.log(`Static build workspace: ${staging}`);

// Leave local Next.js API routes and private environment files in the original checkout.
for (const name of ["app", "components", "lib", "public", "package.json", "package-lock.json", "tsconfig.json", "next-env.d.ts", "postcss.config.js", "tailwind.config.ts"]) {
  const source = path.join(webRoot, name);
  await cp(source, path.join(staging, name), {
    recursive: true,
    filter: (entry) => entry !== path.join(webRoot, "app", "api"),
  });
}
await symlink(path.join(webRoot, "node_modules"), path.join(staging, "node_modules"), process.platform === "win32" ? "junction" : "dir");
await writeFile(path.join(staging, "next.config.ts"), `import type { NextConfig } from "next";
const config: NextConfig = { reactStrictMode: true, output: "export", trailingSlash: true, images: { unoptimized: true }, experimental: { cpus: 2 } };
export default config;
`);
const buildEnv = { ...process.env, NEXT_PUBLIC_API_BASE_URL: "", NEXT_TELEMETRY_DISABLED: "1" };
for (const key of ["BACKEND_API_ACCESS_TOKEN", "API_ACCESS_TOKEN", "DEEPSEEK_API_KEY", "EMBEDDING_API_KEY"]) delete buildEnv[key];
await new Promise((resolve, reject) => {
  const child = spawn(process.execPath, [path.join(webRoot, "node_modules/next/dist/bin/next"), "build"], {
    cwd: staging, env: buildEnv, stdio: "inherit",
  });
  child.on("error", reject);
  child.on("exit", (code) => code === 0 ? resolve() : reject(new Error(`Static build exited with ${code}`)));
});
const builtOutput = path.join(staging, "out");
for (const page of ["index.html", "knowledge/index.html", "reading/index.html", "status/index.html"]) {
  await readFile(path.join(builtOutput, page));
}
await writeFile(path.join(builtOutput, "_routes.json"), JSON.stringify({ version: 1, include: ["/api/*"], exclude: [] }, null, 2));
const output = path.join(webRoot, "out");
const candidate = path.join(webRoot, `.out-${randomUUID()}`);
// All directory moves stay in this project's web directory; previous exports are retained.
for (const target of [output, candidate]) {
  if (path.dirname(path.resolve(target)) !== webRoot) throw new Error("Output path is outside the web workspace");
}
await cp(builtOutput, candidate, { recursive: true });
const exists = await stat(output).then(() => true, (cause) => {
  if (cause.code === "ENOENT") return false;
  throw cause;
});
const backup = exists ? path.join(webRoot, `out.backup-${randomUUID()}`) : undefined;
if (backup) await rename(output, backup);
try {
  await rename(candidate, output);
} catch (cause) {
  if (backup) await rename(backup, output);
  throw cause;
}
console.log(`Cloudflare Pages assets ready: ${output}`);
console.log(`Run Wrangler from ${webRoot} so it also includes functions/api/[[path]].ts`);
