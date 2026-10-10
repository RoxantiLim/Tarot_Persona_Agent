import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../functions/api/[[path]].ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { onRequest } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const env = { BACKEND_API_BASE_URL: "https://example.modal.run", BACKEND_API_ACCESS_TOKEN: "server-secret" };

test("proxy adds its server token, strips browser credentials and preserves rate-limit responses", async (context) => {
  context.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(String(url), "https://example.modal.run/api/knowledge/query");
    assert.equal(options.headers.Authorization, "Bearer server-secret");
    assert.equal(options.headers.Cookie, undefined);
    assert.equal(options.redirect, "manual");
    return new Response('{"detail":"limited"}', { status: 429, headers: { "Retry-After": "60", "Set-Cookie": "private=value", "Content-Encoding": "gzip" } });
  });
  const request = new Request("https://site.pages.dev/api/knowledge/query?secret=value", {
    method: "POST", headers: { "Content-Type": "application/json", "Authorization": "Bearer browser-value", "Cookie": "browser-cookie" }, body: '{"query":"hello"}',
  });
  const response = await onRequest({ request, env });
  assert.equal(response.status, 429);
  assert.equal(response.headers.get("retry-after"), "60");
  assert.equal(response.headers.get("set-cookie"), null);
  assert.equal(response.headers.get("content-encoding"), null);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.ok(!(await response.text()).includes("server-secret"));
});

test("unknown routes, methods, bad config and oversized bodies never reach Modal", async (context) => {
  const upstream = context.mock.method(globalThis, "fetch", () => { throw new Error("must not call"); });
  for (const [request, settings, status] of [
    [new Request("https://site.pages.dev/api/arbitrary"), env, 404],
    [new Request("https://site.pages.dev/api/cards", { method: "DELETE" }), env, 405],
    [new Request("https://site.pages.dev/api/cards"), { ...env, BACKEND_API_ACCESS_TOKEN: "" }, 503],
    [new Request("https://site.pages.dev/api/cards"), { ...env, BACKEND_API_BASE_URL: "http://example.com" }, 503],
    [new Request("https://site.pages.dev/api/knowledge/query", { method: "POST", headers: { "Content-Type": "application/json" }, body: "x".repeat(16385) }), env, 413],
  ]) assert.equal((await onRequest({ request, env: settings })).status, status);
  assert.equal(upstream.mock.callCount(), 0);
});

test("upstream redirects and exception messages cannot reveal credentials", async (context) => {
  const upstream = context.mock.method(globalThis, "fetch", async () => new Response(null, { status: 302, headers: { "Location": "https://elsewhere.example" } }));
  const request = new Request("https://site.pages.dev/api/cards");
  assert.equal((await onRequest({ request, env })).status, 502);
  upstream.mock.mockImplementation(async () => { throw new Error("server-secret"); });
  const response = await onRequest({ request, env });
  assert.equal(response.status, 502);
  assert.ok(!(await response.text()).includes("server-secret"));
});
