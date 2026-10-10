import { NextRequest } from "next/server";

const BACKEND_API_BASE_URL = process.env.BACKEND_API_BASE_URL ?? "http://127.0.0.1:8787";
const API_TIMEOUT_MS = Number(process.env.BACKEND_API_TIMEOUT_MS ?? 180000);

type RouteContext = {
  params: Promise<{ path: string[] }>;
};

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyRequest(request, context);
}

async function proxyRequest(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const requestUrl = new URL(request.url);
  const targetUrl = new URL(`/api/${path.join("/")}${requestUrl.search}`, BACKEND_API_BASE_URL);
  const headers = forwardedHeaders(request.headers);
  const accessToken = process.env.BACKEND_API_ACCESS_TOKEN;
  if (accessToken) {
    headers.set("authorization", `Bearer ${accessToken}`);
  }
  const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();

  try {
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    });

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders(response.headers),
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown backend proxy error";
    const friendlyMessage = backendProxyMessage(message);
    return Response.json(
      {
        detail: friendlyMessage,
      },
      { status: 502 },
    );
  }
}

function backendProxyMessage(message: string) {
  const lower = message.toLowerCase();
  if (lower.includes("timeout") || lower.includes("aborted")) {
    return "后端请求超时。请稍后重试，或降低本次请求复杂度。";
  }
  if (lower.includes("fetch failed") || lower.includes("econnrefused") || lower.includes("connect")) {
    return "还没有连上 FastAPI 后端。请运行 scripts\\start_local.ps1；如果在分享给朋友，请运行 scripts\\start_share.ps1。";
  }
  if (lower.includes("invalid url")) {
    return "后端地址配置不正确。请检查 BACKEND_API_BASE_URL。";
  }
  return `后端服务请求失败：${message}`;
}

function forwardedHeaders(headers: Headers) {
  const forwarded = new Headers(headers);
  forwarded.delete("host");
  forwarded.delete("x-forwarded-host");
  forwarded.delete("x-forwarded-proto");
  forwarded.delete("x-forwarded-port");
  return forwarded;
}

function responseHeaders(headers: Headers) {
  const forwarded = new Headers(headers);
  forwarded.delete("content-encoding");
  forwarded.delete("content-length");
  forwarded.delete("transfer-encoding");
  return forwarded;
}
