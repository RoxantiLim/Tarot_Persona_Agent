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
    return Response.json(
      {
        detail: `Backend service request failed: ${message}`,
      },
      { status: 502 },
    );
  }
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
