import { send as rawSend } from "./http"

export interface ChartAxis {
    field: string
    label?: string
}

export interface ChartConfig {
    type: "bar" | "line" | "pie" | "table" | "none"
    x_axis?: ChartAxis
    y_axis?: ChartAxis
    label_field?: string
    value_field?: string
    limit?: number
}

export interface DatabaseResult {
    title?: string | null
    database?: string | null
    tables: string[]
    sql?: string | null
    analysis_query_id?: string | null
    token: string
    columns: string[]
    rows: unknown[][]
    row_count?: number | null
    total_time_ms?: number | null
    page: number
    page_size: number
    has_more: boolean
}

export interface DocumentSource {
    filename: string
    page?: number | null
    score?: number | null
}

export interface DocumentResult {
    answer?: string | null
    sources: DocumentSource[]
}

export interface IntelligenceResponse {
    intent: "database" | "document" | "hybrid" | "general"
    answer: string
    database?: DatabaseResult | null
    document?: DocumentResult | null
    chart?: ChartConfig | null
    sources: DocumentSource[]
    conversation_id?: string | null
    user_message_id?: string | null
    assistant_message_id?: string | null
    created_at: string
}

export interface IntelligenceRequest {
    question: string
    client_id?: string | null
    conversation_id?: string | null
}

const send = (path: string, method: string, body?: unknown): Promise<Response> =>
    rawSend(`/intelligence${path}`, method, body)

export const askIntelligence = async (
    data: IntelligenceRequest,
): Promise<IntelligenceResponse> =>
    (await send("/ask", "POST", data)).json()
