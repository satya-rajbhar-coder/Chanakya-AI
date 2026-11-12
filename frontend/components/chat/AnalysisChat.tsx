"use client"

import { useEffect, useRef, useState } from "react"
import {
    RotateCcw, Plus,
    AlertCircle, Sparkles,
} from "lucide-react"

import {
    AnalysisClient,
    AnalysisResponse,
    askAnalysis,
    errorMessage,
    listClients,
} from "@/services/analysis"
import { generateId } from "@/lib/utils"

import ChatInput from "./ChatInput"
import ResultTable from "./ResultTable"
import { Button } from "@/components/ui/button"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { TooltipProvider } from "@/components/ui/tooltip"

interface Turn {
    id: string
    question: string
    status: "loading" | "done" | "error"
    data?: AnalysisResponse
    error?: string
}

const ThinkingIndicator = () => (
    <div className="flex items-center gap-2 py-3" aria-label="Assistant is thinking">
        <div className="flex flex-col gap-1">
            <Sparkles className="size-5 text-primary animate-spin-slow" />
        </div>
        <div className="flex items-center gap-1">
            <span className="text-xs font-medium text-muted-foreground">Analyzing your data</span>
            <div className="flex gap-1">
                <span className="h-1 w-1 rounded-full bg-primary animate-pulse" />
                <span className="h-1 w-1 rounded-full bg-primary animate-pulse" style={{ animationDelay: "0.2s" }} />
                <span className="h-1 w-1 rounded-full bg-primary animate-pulse" style={{ animationDelay: "0.4s" }} />
            </div>
        </div>
    </div>
)

const AnalysisChat = () => {
    const [turns, setTurns] = useState<Turn[]>([])
    const [clients, setClients] = useState<AnalysisClient[]>([])
    const [selectedClient, setSelectedClient] = useState<string | null>(null)
    const [clientsLoading, setClientsLoading] = useState(true)
    const bottomRef = useRef<HTMLDivElement>(null)

    const sending = turns.some((turn) => turn.status === "loading")

    useEffect(() => {
        let active = true
        listClients()
            .then((data) => {
                if (!active) return
                setClients(data)
                if (data.length === 1) {
                    setSelectedClient(data[0].id)
                }
            })
            .catch(() => {
                if (active) setClients([])
            })
            .finally(() => {
                if (active) setClientsLoading(false)
            })
        return () => {
            active = false
        }
    }, [])

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [turns])

    const patch = (id: string, change: Partial<Turn>) =>
        setTurns((prev) => prev.map((turn) => (turn.id === id ? { ...turn, ...change } : turn)))

    const handleSend = async (question: string) => {
            if (sending) return

            const id = generateId()

            setTurns((prev) => [...prev, { id, question, status: "loading" }])

            try {
                const data = await askAnalysis(question, selectedClient ?? undefined)
                patch(id, { status: "done", data })
            } catch (err) {
                patch(id, { status: "error", error: errorMessage(err) })
            }
        }

        const retry = (turn: Turn) => {
            if (sending) return
            setTurns((prev) => prev.filter((t) => t.id !== turn.id))
            void handleSend(turn.question)
        }

    return (
        <TooltipProvider>
            <div className="flex min-h-0 flex-1 flex-col bg-background">
                {/* Header */}
                <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 px-6 py-3 border-b border-border/50 bg-background">
                    <div className="flex items-center gap-2">
                        <Button
                                                    onClick={() => {
                                                        setTurns([])
                                                    }}
                                                    disabled={sending}
                                                    className="h-9 gap-2 bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm"
                                                    aria-label="Start new analysis"
                                                >
                            <Plus className="size-4" />
                            <span className="hidden sm:inline font-medium">New analysis</span>
                        </Button>
                    </div>

                    <div className="ml-auto flex items-center gap-2">
                        {!clientsLoading && clients.length > 1 && (
                            <Select
                                                            onValueChange={(value) => {
                                                                setSelectedClient(value ?? null)
                                                            }}
                                                            defaultValue={selectedClient ?? undefined}
                                                        >
                                <SelectTrigger className="w-[200px] h-9">
                                    <SelectValue placeholder="Select client" />
                                </SelectTrigger>
                                <SelectContent>
                                    {clients.map((c) => (
                                        <SelectItem key={c.id} value={c.id}>
                                            {c.name} ({c.code})
                                                                                    </SelectItem>
                                                                                ))}
                                                                            </SelectContent>
                                                                        </Select>
                                                                    )}
                                                                </div>
                                                            </div>

                                                            {/* Messages */}
                <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6">
                    {turns.length === 0 ? (
                        <div className="flex h-full min-h-[60vh] flex-col items-center justify-center text-center px-4">
                            <div className="flex flex-col items-center gap-3">
                                <div className="p-3 rounded-full bg-primary/10 text-primary">
                                    <Sparkles className="size-6" />
                                </div>
                                <h1 className="mb-2 text-2xl font-semibold tracking-tight text-foreground">Ask about your data</h1>
                                <p className="mb-6 max-w-md text-sm text-muted-foreground leading-relaxed">
                                    Type a question in plain language and get instant answers
                                    from your databases. All queries are saved automatically
                                    to your history.
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="mx-auto flex w-full max-w-3xl min-w-0 flex-col gap-6">
                            {turns.map((turn) => (
                                <div key={turn.id} className="flex flex-col gap-3">
                                    {/* User Question */}
                                    <div className="flex justify-end">
                                        <div className="max-w-[75%] whitespace-pre-wrap break-words rounded-2xl bg-primary px-4 py-3 text-sm leading-relaxed text-primary-foreground shadow-sm">
                                            {turn.question}
                                        </div>
                                    </div>

                                    {/* Status / Result */}
                                    {turn.status === "loading" && (
                                        <div className="flex justify-start">
                                            <ThinkingIndicator />
                                        </div>
                                    )}

                                    {turn.status === "error" && (
                                        <div className="flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-3.5 shadow-sm">
                                            <AlertCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
                                            <div className="flex-1">
                                                <p className="min-w-0 flex-1 text-sm text-destructive leading-relaxed">{turn.error}</p>
                                                <Button
                                                    variant="outline"
                                                    size="sm"
                                                    className="mt-2 h-8 shrink-0 border-destructive/30 text-destructive hover:bg-destructive/10"
                                                    onClick={() => retry(turn)}
                                                >
                                                    <RotateCcw className="size-3" />
                                                    <span className="hidden sm:inline">Retry</span>
                                                </Button>
                                            </div>
                                        </div>
                                    )}

                                    {turn.status === "done" && turn.data && (
                                        <ResultTable
                                            data={turn.data}
                                            question={turn.question}
                                        />
                                    )}
                                </div>
                            ))}
                        </div>
                    )}

                    <div ref={bottomRef} />
                </div>

                <ChatInput
                    onSend={handleSend}
                    disabled={sending}
                    placeholder="Ask about your databases..."
                />
            </div>
        </TooltipProvider>
    )
}

export default AnalysisChat
