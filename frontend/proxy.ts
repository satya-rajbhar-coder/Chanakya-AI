import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

const ACCESS_COOKIE = "access_token";
const REFRESH_COOKIE = "refresh_token";
const PUBLIC_PATHS = ["/login"];

const isPublicPath = (pathname: string) =>
    PUBLIC_PATHS.some(
        (path) => pathname === path || pathname.startsWith(`${path}/`)
    );

const isApiPath = (pathname: string) =>
    pathname.startsWith("/api");

async function proxyApiRequest(request: NextRequest): Promise<NextResponse> {
    const { pathname, searchParams } = request.nextUrl;
    const search = searchParams.toString();
    const targetUrl = `${API_URL}${pathname}${search ? `?${search}` : ""}`;

    const requestBody = request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer();

    try {
        const fwdHeaders: Record<string, string> = {};
        request.headers.forEach((value, key) => {
            const lk = key.toLowerCase();
            if (lk === "host" || lk === "content-length" || lk === "expect") return;
            fwdHeaders[key] = value;
        });
        fwdHeaders["host"] = new URL(API_URL).host;

        const response = await fetch(targetUrl, {
            method: request.method,
            headers: fwdHeaders,
            body: requestBody,
        });

        const responseBody = await response.text();

        // Copy all headers except Set-Cookie (handled via nextResponse.cookies.set below)
        const responseHeaders = new Headers();
        response.headers.forEach((value, key) => {
            const lk = key.toLowerCase();
            if (
                lk === "connection" ||
                lk === "keep-alive" ||
                lk === "proxy-authenticate" ||
                lk === "proxy-authorization" ||
                lk === "te" ||
                lk === "transfer-encoding" ||
                lk === "upgrade" ||
                lk === "set-cookie"
            ) {
                return;
            }
            responseHeaders.set(key, value);
        });

        const nextResponse = new NextResponse(responseBody, {
            status: response.status,
            statusText: response.statusText,
            headers: responseHeaders,
        });

        // Set cookies using NextResponse.cookies.set() for proper Next.js middleware handling
        const setCookies = response.headers.getSetCookie() || [];
        for (const cookie of setCookies) {
            const parts = cookie.split(";");
            const [pair] = parts;
            const separator = pair.indexOf("=");
            if (separator > 0) {
                const name = pair.slice(0, separator).trim();
                const value = pair.slice(separator + 1).trim();
                const cookieOptions: Record<string, unknown> = { path: "/" };
                for (let i = 1; i < parts.length; i++) {
                    const part = parts[i].trim();
                    const lowerPart = part.toLowerCase();
                    if (lowerPart === "httponly") {
                        cookieOptions.httpOnly = true;
                    } else if (lowerPart.startsWith("samesite=")) {
                        cookieOptions.sameSite = lowerPart.split("=")[1] as "lax" | "strict" | "none";
                    } else if (lowerPart.startsWith("max-age=")) {
                        cookieOptions.maxAge = parseInt(lowerPart.split("=")[1], 10);
                    } else if (lowerPart.startsWith("expires=")) {
                        cookieOptions.expires = new Date(lowerPart.split("=")[1]);
                    } else if (lowerPart.startsWith("domain=")) {
                        cookieOptions.domain = lowerPart.split("=")[1];
                    } else if (lowerPart === "secure") {
                        cookieOptions.secure = true;
                    }
                }
                nextResponse.cookies.set(name, value, cookieOptions);
            }
        }

        return nextResponse;
    } catch (error) {
        console.error("Proxy fetch error:", error);
        console.error("Proxy fetch error stack:", error instanceof Error ? error.stack : "no stack");
        return NextResponse.json(
            { detail: "Backend service unavailable", error: String(error), stack: error instanceof Error ? error.stack : "no stack" },
            { status: 502 }
        );
    }
}

async function refreshSession(refreshToken: string): Promise<string[] | null> {
    try {
        const response = await fetch(`${API_URL}/api/auth/refresh`, {
            method: "POST",
            headers: { cookie: `${REFRESH_COOKIE}=${refreshToken}` },
            cache: "no-store",
        });

        if (!response.ok) {
            return null;
        }

        const setCookies = response.headers.getSetCookie();
        return setCookies.length > 0 ? setCookies : null;
    } catch {
        return null;
    }
}

function clearSessionCookies(response: NextResponse) {
    response.cookies.delete(ACCESS_COOKIE);
    response.cookies.delete(REFRESH_COOKIE);
    response.cookies.delete({ name: REFRESH_COOKIE, path: "/" });
}

export async function proxy(request: NextRequest) {
    const { pathname, searchParams } = request.nextUrl;
    const publicPath = isPublicPath(pathname);

    if (isApiPath(pathname)) {
        return proxyApiRequest(request);
    }

    // On /login?reason=expired, just render the page — do NOT clear cookies
    // (cookies will be overwritten on next successful login)
    if (publicPath && searchParams.get("reason") === "expired") {
        return NextResponse.next();
    }

    const accessToken = request.cookies.get(ACCESS_COOKIE)?.value;
    const refreshToken = request.cookies.get(REFRESH_COOKIE)?.value;

    if (accessToken) {
        return publicPath
            ? NextResponse.redirect(new URL("/", request.url))
            : NextResponse.next();
    }

    if (refreshToken) {
        const setCookies = await refreshSession(refreshToken);

        if (setCookies) {
            for (const cookie of setCookies) {
                const [pair] = cookie.split(";");
                const separator = pair.indexOf("=");
                if (separator > 0) {
                    request.cookies.set(
                        pair.slice(0, separator).trim(),
                        pair.slice(separator + 1).trim()
                    );
                }
            }

            const response = publicPath
                ? NextResponse.redirect(new URL("/", request.url))
                : NextResponse.next({ request: { headers: request.headers } });

            for (const cookie of setCookies) {
                try {
                    response.headers.append("set-cookie", cookie);
                } catch {
                    // Ignore if response is closed
                }
            }

            return response;
        }
    }

    if (publicPath) {
        return NextResponse.next();
    }

    const response = NextResponse.redirect(new URL("/login", request.url));
    if (refreshToken) {
        clearSessionCookies(response);
    }
    return response;
}

export default proxy;

export const config = {
    matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
