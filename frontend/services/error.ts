import axios from "axios"

interface ValidationItem {
    msg?: string
}

export const getApiErrorMessage = (error: unknown): string => {
    if (!axios.isAxiosError(error)) {
        return "Something went wrong"
    }

    // No response at all = network error / API down.
    if (!error.response) {
        return "Unable to connect to the server"
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

    return "Something went wrong"
}
