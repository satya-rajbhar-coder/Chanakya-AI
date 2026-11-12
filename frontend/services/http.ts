export const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"

export const errorMessage = (err: unknown): string =>
    err instanceof Error ? err.message : "Something went wrong"

// Single in-flight refresh so a burst of 401s (e.g. many API calls fired in a
// loop) triggers only one /auth/refresh instead of racing each other.
let refreshPromise: Promise<boolean> | null = null

const refreshSession = (): Promise<boolean> => {
    if (!refreshPromise) {
        refreshPromise = fetch(`${API_BASE_URL}/auth/refresh`, {
            method: "POST",
            credentials: "include",
        })
            .then((res) => res.ok)
            .finally(() => {
                refreshPromise = null
            })
    }
    return refreshPromise
}

const detailFrom = async (res: Response): Promise<string> => {
    let detail = `Request failed (${res.status})`
    try {
        const json = await res.json()
        if (typeof json.detail === "string") {
            detail = json.detail
        } else if (Array.isArray(json.detail)) {
            detail = json.detail
                .map((d: { msg?: string }) => d.msg)
                .filter(Boolean)
                .join(", ")
        }
    } catch {
        /* keep default message */
    }
    return detail
}

/**
 * fetch() wrapper that attaches credentials, retries once after a deduped
 * token refresh on 401, and throws an Error with the backend detail message.
 */
export const send = async (
    path: string,
    method: string,
    body?: unknown,
): Promise<Response> => {
    const url = `${API_BASE_URL}${path}`

    const buildInit = (): RequestInit => ({
        method,
        credentials: "include",
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
    })

    let res = await fetch(url, buildInit())

    if (res.status === 401) {
        const refreshed = await refreshSession()
        if (refreshed) {
            res = await fetch(url, buildInit())
        }
    }

    if (!res.ok) {
        throw new Error(await detailFrom(res))
    }

    return res
}
