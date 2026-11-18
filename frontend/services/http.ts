export const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"

export const errorMessage = (err: unknown): string =>
    err instanceof Error
        ? /failed to fetch|networkerror|load failed/i.test(err.message)
            ? "We couldn't connect to the server. Check your connection and try again."
            : err.message || "We couldn't complete your request. Please try again."
        : "We couldn't complete your request. Please try again."

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
    let detail = statusMessage(res.status)
    try {
        const json = await res.json()
        if (res.status < 500 && typeof json.detail === "string") {
            detail = json.detail
        } else if (res.status < 500 && Array.isArray(json.detail)) {
            detail = json.detail
                .map((d: { msg?: string }) => d.msg)
                .filter(Boolean)
                .join(", ")
        }
    } catch {
        // Keep the status-specific message when the response has no JSON body.
    }
    return detail
}

const statusMessage = (status: number): string => {
    if (status === 401) return "Your session has expired. Please sign in again."
    if (status === 403) return "You don't have permission to do that."
    if (status === 404) return "We couldn't find what you requested."
    if (status === 408) return "That took too long. Please try again."
    if (status === 429) return "You're making requests too quickly. Please wait a moment and try again."
    if (status >= 500) return "We couldn't complete your request right now. Please try again in a moment."
    return "We couldn't complete your request. Please check your input and try again."
}

/**
 * fetch() wrapper that attaches credentials, retries once after a deduped
 * token refresh on 401, and throws an Error with a user-facing failure message.
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

    let res: Response
    try {
        res = await fetch(url, buildInit())

        if (res.status === 401) {
            const refreshed = await refreshSession()
            if (refreshed) {
                res = await fetch(url, buildInit())
            }
        }
    } catch (err) {
        if (err instanceof TypeError && /failed to fetch|networkerror|load failed/i.test(err.message)) {
            throw new Error("We couldn't connect to the server. Check your connection and try again.")
        }
        throw err
    }

    if (!res.ok) {
        throw new Error(await detailFrom(res))
    }

    return res
}
