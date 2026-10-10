interface Env {
  BACKEND_API_BASE_URL: string;
  BACKEND_API_ACCESS_TOKEN: string;
}

interface Context {
  request: Request;
  env: Env;
}

const ROUTES: Record<string, string> = {
  "/api/health": "GET",
  "/api/cards": "GET",
  "/api/readers": "GET",
  "/api/knowledge/query": "POST",
  "/api/reading/generate": "POST",
};
const MAX_BODY_BYTES = 16 * 1024;

function error(detail: string, status: number) {
  return Response.json({ detail }, { status, headers: { "Cache-Control": "no-store" } });
}

async function readBody(request: Request): Promise<Uint8Array | undefined> {
  if (!request.body) return undefined;
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY_BYTES) {
        await reader.cancel();
        throw new RangeError("Request body too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body;
}

export async function onRequest({ request, env }: Context): Promise<Response> {
  const url = new URL(request.url);
  const method = ROUTES[url.pathname];
  if (!method) return error("接口不存在。", 404);
  if (request.method !== method) return error("请求方式不支持。", 405);
  let base: URL;
  try {
    base = new URL(env.BACKEND_API_BASE_URL);
    if (base.protocol !== "https:" || base.username || base.password || base.search || base.hash || !env.BACKEND_API_ACCESS_TOKEN?.trim()) {
      throw new Error("Invalid backend configuration");
    }
  } catch {
    return error("后端连接尚未配置。", 503);
  }
  if (method === "POST" && !request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    return error("请求需要使用 JSON 格式。", 415);
  }
  try {
    const body = method === "POST" ? await readBody(request) : undefined;
    const upstream = await fetch(new URL(url.pathname, base), {
      method,
      headers: {
        "Authorization": `Bearer ${env.BACKEND_API_ACCESS_TOKEN}`,
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
      body: body as BodyInit | undefined,
      redirect: "manual",
      signal: AbortSignal.timeout(145000),
    });
    if (upstream.status >= 300 && upstream.status < 400) {
      return error("后端响应超时或部署地址需要检查。", 502);
    }
    const headers = new Headers({
      "Content-Type": upstream.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    });
    const retryAfter = upstream.headers.get("retry-after");
    if (retryAfter) headers.set("Retry-After", retryAfter);
    return new Response(upstream.body, { status: upstream.status, headers });
  } catch (cause) {
    if (cause instanceof RangeError) return error("请求内容过长。", 413);
    return error("后端暂时无法响应，请稍后重试。", 502);
  }
}
