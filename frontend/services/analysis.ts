import { errorMessage, send as rawSend } from "./http"

export { errorMessage }

export interface ResultPage {
    columns: string[]
    rows: unknown[][]
    page: number
    page_size: number
    has_more: boolean
    total_time_ms?: number
}

export interface AnalysisResponse {
    title: string
    database: string
    tables: string[]
    sql: string
    analysis_query_id?: string
    token: string
    result: ResultPage
}

export interface HistoryItem {
    id: string
    question: string
    title: string | null
    database: string
    client_id: string | null
    row_count: number | null
    created_at: string
}

export interface AdminHistoryItem extends HistoryItem {
    sql: string
}

const send = (path: string, method: string, body?: unknown): Promise<Response> =>
    rawSend(`/analysis${path}`, method, body)

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
    clientId?: string | null,
): Promise<AnalysisResponse> =>
    (await send("/query", "POST", {
        question,
        client_id: clientId ?? null,
    })).json()

export const listHistory = async (clientId?: string): Promise<HistoryItem[]> =>
    (await send(`/history${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ""}`, "GET")).json()

export const deleteHistory = async (id: string): Promise<void> => {
    await send(`/history/${id}`, "DELETE")
}

export const adminListHistory = async (clientId?: string): Promise<AdminHistoryItem[]> =>
    (await send(`/admin/history${clientId ? `?client_id=${encodeURIComponent(clientId)}` : ""}`, "GET")).json()

export const runHistory = async (
    id: string,
    page = 0,
    pageSize = 500,
): Promise<AnalysisResponse> =>
    (await send(
        `/history/${id}/run?page=${page}&page_size=${pageSize}`,
        "POST",
    )).json()

// Safety cap so a backend that keeps reporting has_more cannot loop forever.
const MAX_HISTORY_PAGES = 1000

export const loadAllHistoryRows = async (
    id: string,
    firstPage?: AnalysisResponse,
): Promise<AnalysisResponse> => {
    let response = firstPage ?? await runHistory(id)
    if (
        firstPage &&
        firstPage.result.has_more &&
        firstPage.result.page_size < 500
    ) {
        response = await runHistory(id, 0, 500)
    }
    const rows = [...response.result.rows]
    let page = response.result.page

    while (response.result.has_more) {
        if (++page > MAX_HISTORY_PAGES) {
            throw new Error("This result is too large to load here; use the CSV export instead")
        }
        response = await runHistory(id, page, response.result.page_size || 500)
        rows.push(...response.result.rows)
    }

    return {
        ...response,
        result: {
            ...response.result,
            rows,
            page: 0,
            page_size: rows.length,
            has_more: false,
        },
    }
}

export const exportCsv = async (token: string): Promise<Blob> =>
    (await send("/export", "POST", { token })).blob()
