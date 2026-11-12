"use client"

import {
    useEffect,
    useRef,
    useState,
} from "react"

import {
    BarChart,
    Bar,
    PieChart,
    Pie,
    LineChart,
    Line,
    ResponsiveContainer,
    Tooltip,
    Legend,
    Cell,
    XAxis,
    YAxis,
    CartesianGrid,
} from "recharts"

import {
    askIntelligence,
    type IntelligenceResponse,
} from "@/services/intelligence"
import { generateId } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Tooltip as TooltipComp,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip"
import {
    Sparkles,
    FileText,
    Bot,
    MessageCircle,
    Database,
    Activity,
    AlertCircle,
    Plus,
    X,
    ChevronDown,
    ChevronUp,
} from "lucide-react"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { markdownComponents } from "@/components/markdown/MarkdownComponents"

const COLORS = [
    "#3b82f6",
    "#ef4444",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#ec4899",
    "#6366f1",
    "#14b8a6",
]

interface Turn {
    id: string
    question: string
    status: "loading" | "done" | "error"
    data?: IntelligenceResponse
    error?: string
}

const isNumeric = (value: unknown): boolean => {
    if (value === null || value === undefined) return false
    if (typeof value === "number") return !isNaN(value)
    if (typeof value === "string") return /^-?\d+(\.\d+)?$/.test(value.trim())
    return false
}

const extractChartData = (response: IntelligenceResponse) => {
    const db = response.database
    if (!db?.columns?.length || !db.rows?.length) return null

    const columns = db.columns
    const rows = db.rows
    const chart = response.chart

    // Prefer fields explicitly suggested by the backend chart config
    const labelField = chart?.label_field ?? chart?.x_axis?.field
    const valueField = chart?.value_field ?? chart?.y_axis?.field

    // Find a categorical column and a numeric column
    let catIdx: number | null = null
    let valIdx: number | null = null

    if (labelField && valueField) {
        catIdx = columns.indexOf(labelField)
        valIdx = columns.indexOf(valueField)
        if (catIdx === -1) catIdx = null
        if (valIdx === -1) valIdx = null
    }

    if (catIdx === null || valIdx === null) {
        for (let i = 0; i < columns.length; i++) {
            const sample = rows.map((r) => r[i]).filter((v) => v != null)
            const numericCount = sample.filter(isNumeric).length
            const total = sample.length
            if (total > 0 && numericCount / total >= 0.7 && valIdx === null) {
                valIdx = i
            } else if (catIdx === null && valIdx !== i) {
                catIdx = i
            }
        }
    }

    if (catIdx === null || valIdx === null) return null

    const data = rows.map((row) => ({
        name: String(row[catIdx] ?? ""),
        value: Number(row[valIdx]) || 0,
    }))

    return {
        columns: [columns[catIdx], columns[valIdx]],
        data: data.slice(0, chart?.limit ?? 10),
        xField: columns[catIdx],
        yField: columns[valIdx],
    }
}

function BarChartWidget({ data, xField, yField }: { data: { name: string; value: number }[]; xField: string; yField: string }) {
    return (
        <div className="rounded-xl border border-border/50 bg-card p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-foreground">Analysis — {yField} by {xField}</h3>
            </div>
            <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/30" />
                        <XAxis dataKey="name" className="text-[10px] fill-muted-foreground" />
                        <YAxis className="text-[10px] fill-muted-foreground" />
                        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                        <Legend />
                        <Bar dataKey="value" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}

function PieChartWidget({ data, xField, yField }: { data: { name: string; value: number }[]; xField: string; yField: string }) {
    return (
        <div className="rounded-xl border border-border/50 bg-card p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-foreground">Distribution — {yField} by {xField}</h3>
            </div>
            <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Tooltip />
                        <Legend />
                        <Pie
                            data={data}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            outerRadius={80}
                            fill="#8884d8"
                            label
                        >
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                        </Pie>
                    </PieChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}

function LineChartWidget({ data, xField, yField }: { data: { name: string; value: number }[]; xField: string; yField: string }) {
    return (
        <div className="rounded-xl border border-border/50 bg-card p-4 shadow-sm">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-foreground">Trend — {yField} over {xField}</h3>
            </div>
            <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} className="stroke-border/30" />
                        <XAxis dataKey="name" className="text-[10px] fill-muted-foreground" />
                        <YAxis className="text-[10px] fill-muted-foreground" />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} dot />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    )
}

function ResultTableWidget({ columns, rows }: { columns: string[]; rows: unknown[][] }) {
    return (
        <div className="rounded-xl border border-border/50 bg-card p-4 shadow-sm">
            <div className="overflow-x-auto">
                <table className="w-full text-sm text-left">
                    <thead>
                        <tr>
                            {columns.map((col) => (
                                <th
                                    key={col}
                                    className="whitespace-nowrap border-b border-border/50 px-3 py-2 text-left font-medium text-xs uppercase tracking-wide text-muted-foreground bg-muted/30"
                                >
                                    {col}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.slice(0, 50).map((row, i) => (
                            <tr
                                key={i}
                                className="whitespace-nowrap border-b border-border/50 px-3 py-2 text-sm hover:bg-muted/30 transition-colors"
                            >
                                {row.map((cell, j) => (
                                    <td key={j} className="whitespace-nowrap border-b border-border/50 px-3 py-2 text-sm">
                                        <span className="font-mono text-muted-foreground/70">
                                            {cell === null || cell === undefined ? "∅" : String(cell)}
                                        </span>
                                    </td>
                                ))}
                            </tr>
                        ))}
                        {rows.length > 50 && (
                            <tr>
                                <td colSpan={columns.length} className="px-3 py-2 text-xs text-muted-foreground text-center">
                                    Showing first 50 of {rows.length} rows
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

function DatabaseResultCard({ response }: { response: IntelligenceResponse }) {
    const db = response.database
    const [showSql, setShowSql] = useState(false)
    if (!db) return null

    const chartData = extractChartData(response)
    // Chart type is driven by the question/response via the backend suggestion
    const chartType = response.chart?.type ?? (chartData ? "bar" : null)

    return (
        <div className="space-y-3">
            {db.title && (
                <div className="flex items-center gap-2">
                    <Database className="size-4 text-primary" />
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">{db.title}</span>
                </div>
            )}
            <div className="text-xs text-muted-foreground mb-2">
                {db.database} · {db.tables.join(", ")} · {db.row_count ?? 0} row(s)
                {db.total_time_ms != null && ` · ${db.total_time_ms.toFixed(0)}ms`}
            </div>
            {chartData && chartType !== "none" && chartType !== "table" ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {chartType === "pie" ? (
                        <PieChartWidget data={chartData.data} xField={chartData.xField} yField={chartData.yField} />
                    ) : chartType === "line" ? (
                        <LineChartWidget data={chartData.data} xField={chartData.xField} yField={chartData.yField} />
                    ) : (
                        <BarChartWidget data={chartData.data} xField={chartData.xField} yField={chartData.yField} />
                    )}
                </div>
            ) : null}
            <ResultTableWidget columns={db.columns} rows={db.rows} />
            {db.sql && (
                <div className="mt-2">
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowSql(!showSql)}
                        className="text-xs text-primary border-primary/50 hover:bg-primary/5"
                    >
                        {showSql ? "Hide SQL" : "View SQL"}
                        {showSql ? (
                            <ChevronUp className="size-3.5 ml-1" />
                        ) : (
                            <ChevronDown className="size-3.5 ml-1" />
                        )}
                    </Button>
                    {showSql && (
                        <pre className="mt-1 p-2 rounded bg-muted text-xs font-mono overflow-x-auto">
                            {db.sql}
                        </pre>
                    )}
                </div>
            )}
        </div>
    )
}

function DocumentSourcesCard({ sources }: { sources: { filename: string; page?: number | null; score?: number | null }[] }) {
    if (!sources?.length) return null
    return (
        <div className="mt-3 rounded-xl border border-border/50 bg-muted/50 p-3">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Sources</h3>
            <ul className="text-xs space-y-1">
                {sources.map((s, i) => (
                    <li key={i} className="flex items-center gap-1 text-muted-foreground/80">
                        <FileText className="size-3" />
                        <span>{s.filename}</span>
                        {s.page != null && <span className="text-muted-foreground/60">· page {s.page}</span>}
                    </li>
                ))}
            </ul>
        </div>
    )
}

export default function DashboardPage() {
    const [turns, setTurns] = useState<Turn[]>([])
    const [conversationId, setConversationId] = useState<string | null>(null)
    const [input, setInput] = useState("")
    const bottomRef = useRef<HTMLDivElement>(null)

    // No client picker on this page; the backend resolves the user's single
    // assigned client (or asks for one when several are assigned).
    const selectedClientId: string | null = null

    const sendingNow = turns.some((t) => t.status === "loading")

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [turns])

    const patch = (id: string, change: Partial<Turn>) =>
        setTurns((prev) => prev.map((t) => (t.id === id ? { ...t, ...change } : t)))

    const handleSend = async (question: string) => {
        if (sendingNow) return
        const id = generateId()
        setTurns((prev) => [...prev, { id, question, status: "loading" }])

        try {
            const data = await askIntelligence({
                question,
                client_id: selectedClientId ?? undefined,
                conversation_id: conversationId ?? undefined,
            })
            if (data.conversation_id) {
                setConversationId(data.conversation_id)
            }
            patch(id, { status: "done", data })
        } catch (err) {
            const message = err instanceof Error ? err.message : "Something went wrong"
            patch(id, { status: "error", error: message })
        }
    }

    const removeTurn = (id: string) => {
        setTurns((prev) => prev.filter((t) => t.id !== id))
    }

    const renderTurnContent = (data: IntelligenceResponse) => {
        return (
            <div className="space-y-3">
                <div className="prose prose-sm text-foreground max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                        {data.answer}
                    </ReactMarkdown>
                </div>
                {data.intent === "database" || data.intent === "hybrid" ? (
                    <DatabaseResultCard response={data} />
                ) : null}
                {data.document ? (
                    <>
                        <div className="prose prose-sm text-foreground max-w-none">
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={markdownComponents}
                            >
                                {data.document.answer ?? ""}
                            </ReactMarkdown>
                        </div>
                        <DocumentSourcesCard sources={data.document.sources} />
                    </>
                ) : null}
                {data.sources?.length && !data.document ? (
                    <DocumentSourcesCard sources={data.sources} />
                ) : null}
                {data.chart && data.chart.type !== "none" && data.intent === "general" ? (
                    <div className="text-xs text-muted-foreground">Chart suggestion available for data questions.</div>
                ) : null}
            </div>
        )
    }

    return (
        <TooltipProvider>
            <div className="flex min-h-0 flex-1 flex-col bg-background">
                {/* Header */}
                <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 px-6 py-3 border-b border-border/50 bg-background">
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2 p-2 rounded-xl bg-primary/10 text-primary">
                            <Sparkles className="size-5" />
                        </div>
                        <div>
                            <h1 className="text-base font-semibold tracking-tight text-foreground">Chanakya AI</h1>
                            <p className="text-xs text-muted-foreground">Hybrid campaign intelligence — database + documents</p>
                        </div>
                    </div>

                    <div className="ml-auto flex items-center gap-2">
                        <TooltipComp>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => {
                                        setTurns([])
                                        setInput("")
                                    }}
                                    disabled={sendingNow}
                                    className="h-9 gap-2 text-muted-foreground hover:text-primary border-border"
                                >
                                    <Plus className="size-4" />
                                    <span className="hidden sm:inline font-medium">New chat</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="top">Start new chat</TooltipContent>
                        </TooltipComp>
                    </div>
                </div>

                {/* Messages */}
                <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6">
                    {turns.length === 0 && (
                        <div className="flex h-full min-h-[60vh] flex-col items-center justify-center text-center px-4">
                            <div className="flex flex-col items-center gap-3">
                                <div className="p-3 rounded-full bg-primary/10 text-primary">
                                    <Bot className="size-6" />
                                </div>
                                <h1 className="mb-2 text-2xl font-semibold tracking-tight text-foreground">Ask about your campaign</h1>
                                <p className="mb-6 max-w-md text-sm text-muted-foreground leading-relaxed">
                                    Ask anything about wards, booths, workers, societies, or your campaign documents.
                                    Chanakya AI will decide whether to query the database, search documents, or both.
                                </p>
                            </div>
                        </div>
                    )}

                    <div ref={bottomRef} className="space-y-6">
                        {turns.map((turn) => (
                            <div key={turn.id} className="flex gap-4">
                                {/* User */}
                                <div className="shrink-0">
                                    <div className="rounded-xl bg-primary text-primary-foreground p-3">
                                        <MessageCircle className="size-4" />
                                    </div>
                                </div>
                                <div className="flex-1">
                                    <div className="rounded-xl border border-border/50 bg-card p-3 shadow-sm">
                                        <p className="text-sm text-foreground">{turn.question}</p>
                                        {turn.status === "loading" && (
                                            <div className="mt-2 flex items-center gap-2">
                                                <Activity className="size-3 text-primary animate-spin" />
                                                <span className="text-xs text-muted-foreground">Analyzing…</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                                <div className="shrink-0">
                                    {turn.status === "error" && (
                                        <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-destructive" onClick={() => handleSend(turn.question)}>
                                            <AlertCircle className="size-3.5" />
                                        </Button>
                                    )}
                                    {turn.status === "done" && (
                                        <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-destructive" onClick={() => removeTurn(turn.id)}>
                                            <X className="size-3.5" />
                                        </Button>
                                    )}
                                </div>
                            </div>
                        ))}
                        {turns.length > 0 && turns[turns.length - 1].status === "done" && (
                            <div className="flex gap-4">
                                {/* Assistant avatar */}
                                <div className="shrink-0">
                                    <div className="rounded-xl bg-muted p-3">
                                        <Sparkles className="size-4 text-primary" />
                                    </div>
                                </div>
                                <div className="flex-1">
                                    <div className="rounded-xl border border-border/50 bg-card p-3 shadow-sm">
                                        {renderTurnContent(turns[turns.length - 1].data!)}
                                        <div className="mt-2 flex items-center justify-between">
                                            <span className="text-xs text-muted-foreground">
                                                {turns[turns.length - 1].data?.intent ?? "done"}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Input */}
                <div className="shrink-0 px-4 pb-4 pt-2">
                    <div className="mx-auto w-full max-w-3xl">
                        <div className="flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm">
                            <Input
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault()
                                        if (input.trim()) {
                                            handleSend(input.trim())
                                            setInput("")
                                        }
                                    }
                                }}
                                placeholder="Ask about wards, booths, workers, societies, or documents…"
                                disabled={sendingNow}
                                className="max-h-48 min-h-10 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm outline-none placeholder:text-muted-foreground"
                            />
                            <Button
                                type="button"
                                size="icon"
                                onClick={() => {
                                    if (input.trim()) {
                                        handleSend(input.trim())
                                        setInput("")
                                    }
                                }}
                                disabled={!input.trim() || sendingNow}
                                className="size-10 shrink-0 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm transition-all"
                            >
                                <Sparkles className="size-4" />
                            </Button>
                        </div>
                        {sendingNow && (
                            <p className="mt-2 text-xs text-muted-foreground">Processing your question across database and documents…</p>
                        )}
                    </div>
                </div>
            </div>
        </TooltipProvider>
    )
}
