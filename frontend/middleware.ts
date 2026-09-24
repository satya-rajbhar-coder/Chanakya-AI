import { NextRequest, NextResponse } from "next/server";

const API_URL =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

const ACCESS_COOKIE = "access_token";
const REFRESH_COOKIE = "refresh_token";
const PUBLIC_PATHS = ["/login", "/register"];

const isPublicPath = (pathname: string) =>
    PUBLIC_PATHS.some(
        (path) => pathname === path || pathname.startsWith(`${path}/`)
    );

async function refreshSession(refreshToken: string): Promise<string[] | null> {
    try {
        const response = await fetch(`${API_URL}/auth/refresh`, {
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
    response.cookies.delete({ name: REFRESH_COOKIE, path: "/api/auth" });
}

export async function middleware(request: NextRequest) {
    const { pathname, searchParams } = request.nextUrl;
    const publicPath = isPublicPath(pathname);

    // The server layout found the session invalid (bad/stale cookies).
    // Wipe them and show the login page instead of looping.
    if (publicPath && searchParams.get("reason") === "expired") {
        const response = NextResponse.next();
        clearSessionCookies(response);
        return response;
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
            // Make the fresh cookies visible to server components rendering
            // during THIS request...
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

            // ...and hand them to the browser for the next ones.
            for (const cookie of setCookies) {
                response.headers.append("set-cookie", cookie);
            }

            return response;
        }
    }

    if (publicPath) {
        return NextResponse.next();
    }

    const response = NextResponse.redirect(new URL("/login", request.url));
    if (refreshToken) {
        // Stale refresh token: stop retrying it on every request.
        clearSessionCookies(response);
    }
    return response;
}

export const config = {
    matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
