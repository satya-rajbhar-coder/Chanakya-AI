import axios from "axios"

interface ValidationItem {
    msg?: string
}

export const getApiErrorMessage = (error: unknown): string => {
    if (!axios.isAxiosError(error)) {
        if (error instanceof Error) {
            if (/failed to fetch|networkerror|load failed/i.test(error.message)) {
                return "We couldn't connect to the server. Check your connection and try again."
            }
            return error.message || "We couldn't complete your request. Please try again."
        }
        return "We couldn't complete your request. Please try again."
    }

    // No response at all = network error / API down.
    if (!error.response) {
        return "We couldn't connect to the server. Check your connection and try again."
    }

    const status = error.response.status
    if (status === 401) return "Your session has expired. Please sign in again."
    if (status === 403) return "You don't have permission to do that."
    if (status === 404) return "We couldn't find what you requested."
    if (status === 408) return "That took too long. Please try again."
    if (status === 429) return "You're making requests too quickly. Please wait a moment and try again."
    if (status >= 500) {
        return "We couldn't complete your request right now. Please try again in a moment."
    }

    const data = error.response.data as
        | { detail?: unknown; message?: unknown }
        | undefined

    if (typeof data?.detail === "string") {
        return data.detail
    }

    if (Array.isArray(data?.detail)) {
        const messages = (data.detail as ValidationItem[])
            .map((item) => item.msg)
            .filter(Boolean)

        if (messages.length > 0) {
            return messages.join(", ")
        }
    }

    if (typeof data?.message === "string") {
        return data.message
    }

    return "We couldn't complete your request. Please check your input and try again."
}
