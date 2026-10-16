"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
    History, Play, RotateCcw, Trash2,
    Table, X, AlertCircle
} from "lucide-react"

import {
    AnalysisResponse,
    HistoryItem,
    SavedAnalysis,
    askGlobalAnalysis,
    AskGlobalRequest,
    deleteHistory,
    errorMessage,
    listHistory,
    listSaved,
    runHistory,
    runSaved,
} from "@/services/analysis"

import ChatInput from "./ChatInput"
import ResultTable from "./ResultTable"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider } from "@/components/ui/tooltip"

interface Turn {
    id: string
    question: string
    status: "loading" | "done" | "error"
    data?: AnalysisResponse
    error?: string
}

const ThinkingIndicator = () => (
    <div className="flex items-center gap-1.5 py-2" aria-label="Assistant is thinking">
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground" />
    </div>
)

const AnalysisChat = () => {
    const [turns, setTurns] = useState<Turn[]>([])
    const [saved, setSaved] = useState<SavedAnalysis[]>([])
    const [history, setHistory] = useState<HistoryItem[]>([])
    const [showHistory, setShowHistory] = useState(false)
    const bottomRef = useRef<HTMLDivElement>(null)

    const sending = turns.some((turn) => turn.status === "loading")

    const loadSaved = useCallback(() => {
        listSaved()
            .then(setSaved)
            .catch(() => { })
    }, [])

    const loadHistory = useCallback(() => {
        listHistory()
            .then(setHistory)
            .catch(() => setHistory([]))
    }, [])

    useEffect(() => {
        loadSaved()
        loadHistory()
    }, [loadSaved, loadHistory])

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [turns])

    const patch = (id: string, change: Partial<Turn>) =>
        setTurns((prev) => prev.map((turn) => (turn.id === id ? { ...turn, ...change } : turn)))

    const handleSend = async (question: string) => {
        if (sending) return

        const id = `analysis-${Date.now()}`

        setTurns((prev) => [...prev, { id, question, status: "loading" }])

        try {
            const request: AskGlobalRequest = {
                question,
            }
            const data = await askGlobalAnalysis(request)
            patch(id, { status: "done", data })
            loadHistory()
        } catch (err) {
            patch(id, { status: "error", error: errorMessage(err) })
        }
    }

    const rerun = async (load: () => Promise<AnalysisResponse>, question: string) => {
        if (sending) return

        const turnId = `analysis-${Date.now()}`
        setTurns((prev) => [...prev, { id: turnId, question, status: "loading" }])

        try {
            patch(turnId, { status: "done", data: await load() })
        } catch (err) {
            patch(turnId, { status: "error", error: errorMessage(err) })
        }
    }

    const openSaved = (item: SavedAnalysis) =>
        rerun(() => runSaved(item.id), item.question)

    const openHistory = (item: HistoryItem) =>
        rerun(() => runHistory(item.id), item.question)

    const retry = (turn: Turn) => {
        if (sending) return
        setTurns((prev) => prev.filter((t) => t.id !== turn.id))
        void handleSend(turn.question)
    }

    const removeHistory = async (id: string) => {
        try {
            await deleteHistory(id)
            setHistory((prev) => prev.filter((item) => item.id !== id))
        } catch (err) {
            window.alert(errorMessage(err))
        }
    }

    return (
        <TooltipProvider>
            <div className="flex min-h-0 flex-1 flex-col">
                {/* Header */}
                <div className="flex shrink-0 flex-wrap items-center gap-2 px-6 py-2.5">
                    <div className="ml-auto flex items-center">
                        <Tooltip>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setShowHistory((v) => !v)}
                                className="h-8 gap-1.5 text-muted-foreground"
                            >
                                <History className="size-3.5" />
                                History
                            </Button>
                            <TooltipContent side="bottom">Past queries</TooltipContent>
                        </Tooltip>
                    </div>
                </div>

                {/* History Panel */}
                {showHistory && history.length > 0 && (
                    <div className="mx-6 mb-2 overflow-hidden rounded-lg border">
                        <div className="flex items-center justify-between border-b px-4 py-2">
                            <h3 className="text-sm font-medium">Query history</h3>
                            <Button variant="ghost" size="icon" className="size-7" onClick={() => setShowHistory(false)}>
                                <X className="size-4" />
                            </Button>
                        </div>
                        <div className="max-h-64 divide-y overflow-y-auto">
                            {history.map((item) => (
                                <div
                                    key={item.id}
                                    className="flex items-start gap-3 px-4 py-2.5 transition-colors hover:bg-accent"
                                >
                                    <button
                                        onClick={() => openHistory(item)}
                                        disabled={sending}
                                        className="min-w-0 flex-1 text-left"
                                    >
                                        <p className="truncate text-sm font-medium">{item.title || item.question}</p>
                                        <p className="truncate text-xs text-muted-foreground">
                                            {item.database}
                                            {item.row_count !== null ? ` · ${item.row_count} rows` : ""}
                                            {" · "}
                                            {new Date(item.created_at).toLocaleString()}
                                        </p>
                                    </button>
                                    <div className="flex shrink-0 items-center gap-0.5">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="size-7 text-muted-foreground"
                                            onClick={() => openHistory(item)}
                                            disabled={sending}
                                            aria-label="Run again"
                                        >
                                            <Play className="size-3.5" />
                                        </Button>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="size-7 text-muted-foreground hover:text-destructive"
                                            onClick={() => removeHistory(item.id)}
                                            aria-label="Delete"
                                        >
                                            <Trash2 className="size-3.5" />
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Messages */}
                <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6">
                    {turns.length === 0 ? (
                        <div className="flex h-full min-h-[50vh] flex-col items-center justify-center text-center px-4">
                            <h1 className="mb-2 text-2xl font-semibold tracking-tight">Analyze your data</h1>
                            <p className="mb-8 max-w-md text-sm text-muted-foreground">
                                Ask a question in plain language and get an answer
                                from your data. Queries are saved in History so you
                                can re-run them.
                            </p>

                            {saved.length > 0 && (
                                <div className="w-full max-w-xl space-y-2">
                                    {saved.slice(0, 5).map((item) => (
                                        <button
                                            key={item.id}
                                            onClick={() => openSaved(item)}
                                            disabled={sending}
                                            className="flex w-full items-center gap-3 rounded-xl border px-4 py-2.5 text-left transition-colors hover:bg-accent disabled:opacity-50"
                                        >
                                            <Table className="size-4 shrink-0 text-muted-foreground" />
                                            <span className="min-w-0 flex-1 truncate text-sm">{item.title}</span>
                                            <Play className="size-3.5 shrink-0 text-muted-foreground" />
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="mx-auto flex w-full max-w-3xl min-w-0 flex-col gap-6">
                            {turns.map((turn) => (
                                <div key={turn.id} className="flex flex-col gap-3">
                                    {/* User Question */}
                                    <div className="flex justify-end">
                                        <div className="max-w-[75%] whitespace-pre-wrap break-words rounded-3xl bg-muted px-4 py-2.5 text-sm leading-relaxed text-foreground">
                                            {turn.question}
                                        </div>
                                    </div>

                                    {/* Status / Result */}
                                    {turn.status === "loading" && <ThinkingIndicator />}

                                    {turn.status === "error" && (
                                        <div className="flex items-start gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-3.5 text-destructive">
                                            <AlertCircle className="mt-0.5 size-4 shrink-0" />
                                            <p className="min-w-0 flex-1 break-words text-sm">{turn.error}</p>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="h-7 shrink-0 border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
                                                onClick={() => retry(turn)}
                                            >
                                                <RotateCcw className="size-3" />
                                                Retry
                                            </Button>
                                        </div>
                                    )}

                                    {turn.status === "done" && turn.data && (
                                        <ResultTable
                                            data={turn.data}
                                            question={turn.question}
                                            onSaved={loadSaved}
                                        />
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    <div ref={bottomRef} />
                </div>

                {/* Input pinned at the bottom */}
                <ChatInput
                    onSend={handleSend}
                    disabled={sending}
                    placeholder="Ask about all databases"
                />
            </div>
        </TooltipProvider>
    )
}

export default AnalysisChat