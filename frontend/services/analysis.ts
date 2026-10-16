const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"

export interface ResultPage {
    columns: string[]
    rows: unknown[][]
    page: number
    page_size: number
    has_more: boolean
    total_time_ms?: number
}

export interface MultiClientResult {
    clients: Record<string, ResultPage>
    merged_result: ResultPage | null
    join_key: string | null
    join_type: string
}

export interface AnalysisResponse {
    title: string
    database: string
    tables: string[]
    sql: string
    token: string
    result: ResultPage
    multi_result?: MultiClientResult
}

export interface SavedAnalysis {
    id: string
    title: string
    question: string
    database: string
    sql: string
    created_at: string
}

export interface HistoryItem {
    id: string
    question: string
    title: string | null
    database: string
    sql: string
    client_id: string | null
    row_count: number | null
    created_at: string
}

export const errorMessage = (err: unknown): string => err instanceof Error ? err.message : "Something went wrong"


async function send(path: string, method: string, body?: unknown): Promise<Response> {
    const url = `${API}/analysis${path}`
    const init: RequestInit = {
        method,
        credentials: "include",
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
    }

    let res = await fetch(url, init)

    if (res.status === 401) {
        const refreshed = await fetch(`${API}/auth/refresh`, {
            method: "POST",
            credentials: "include",
        })
        if (refreshed.ok) {
            res = await fetch(url, init)
        }
    }

    if (!res.ok) {
        let detail = `Request failed (${res.status})`
        try {
            const json = await res.json()
            if (typeof json.detail === "string") {
                detail = json.detail
            } else if (Array.isArray(json.detail)) {
                detail = json.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(", ")
            }
        } catch {
            /* keep default message */
        }
        throw new Error(detail)
    }

    return res
}

export interface AnalysisClient {
    id: string
    code: string
    name: string
    client_identifier: string
    database_name: string
    description: string | null
    is_active: boolean
}

/** Clients the current user is assigned to (admins get all). */
export const listClients = async (): Promise<AnalysisClient[]> =>
    (await send("/clients", "GET")).json()

export const askAnalysis = async (
    question: string,
    clientId: string,
    previousSql?: string,
): Promise<AnalysisResponse> =>
    (await send("/query", "POST", {
        question,
        client_id: clientId,
        previous_sql: previousSql ?? null,
    })).json()

export interface AskGlobalRequest {
    question: string
    table_type_filter?: string
    client_ids?: string[]
    join_key?: string
    join_type?: "inner" | "left" | "right" | "outer"
}

export const askGlobalAnalysis = async (
    data: AskGlobalRequest
): Promise<AnalysisResponse> =>
    (await send("/query/global", "POST", data)).json()

export const fetchRows = async (
    token: string,
    page: number,
    pageSize: number,
): Promise<ResultPage> =>
    (await send("/rows", "POST", { token, page, page_size: pageSize })).json()

export const exportCsv = async (token: string): Promise<Blob> =>
    (await send("/export", "POST", { token })).blob()

export const saveAnalysis = async (
    token: string,
    question: string,
    title: string,
): Promise<SavedAnalysis> =>
    (await send("/saved", "POST", { token, question, title })).json()

export const listSaved = async (): Promise<SavedAnalysis[]> =>
    (await send("/saved", "GET")).json()

export const runSaved = async (id: string): Promise<AnalysisResponse> =>
    (await send(`/saved/${id}/run`, "POST")).json()

export const deleteSaved = async (id: string): Promise<void> => {
    await send(`/saved/${id}`, "DELETE")
}

export const listHistory = async (clientId?: string): Promise<HistoryItem[]> =>
    (await send(`/history${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ""}`, "GET")).json()

export const runHistory = async (id: string): Promise<AnalysisResponse> =>
    (await send(`/history/${id}/run`, "POST")).json()

export const deleteHistory = async (id: string): Promise<void> => {
    await send(`/history/${id}`, "DELETE")
}