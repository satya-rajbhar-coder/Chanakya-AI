"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2, X, FileText, ChevronDown, ChevronUp, AlertCircle } from "lucide-react"

import { useWorkspace } from "@/components/workspace-provider"
import {
    getEntireConversationMessages,
    MessageResponse,
} from "@/services/messages"
import { askIntelligence, IntelligenceResponse } from "@/services/intelligence"
import {
    listClients,
    runHistory,
    type AnalysisClient,
    type AnalysisResponse,
} from "@/services/analysis"
import { getApiErrorMessage } from "@/services/error"
import { generateId } from "@/lib/utils"
import { useRouter } from "next/navigation"

import ChatInput from "./ChatInput"
import MarkdownContent from "./MarkdownContent"
import ResultTable from "./ResultTable"
import { Button } from "@/components/ui/button"
import { TooltipProvider } from "@/components/ui/tooltip"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"

interface DocumentsChatProps {
    conversationId?: string
}

interface DocumentSource {
    filename: string
    page?: number | null
    score?: number | null
}

interface MessageWithSources extends MessageResponse {
    intent?: string
    sources?: DocumentSource[]
    databaseResult?: AnalysisResponse | null
    databaseLoading?: boolean
    databaseError?: string | null
    databaseRefreshedAt?: string
    chart?: {
        type: string
        x_axis?: { field: string; label?: string }
        y_axis?: { field: string; label?: string }
    } | null
}

const DocumentsChat = ({ conversationId }: DocumentsChatProps) => {
    const router = useRouter()

    const {
        documents,
        refreshConversations,
        flashError,
        setFlashError,
    } = useWorkspace()

    const [messages, setMessages] = useState<MessageWithSources[]>([])
        const [loadingHistory, setLoadingHistory] = useState(Boolean(conversationId))
        const [sending, setSending] = useState(false)
        const [error, setError] = useState<string | null>(flashError)
        const [showSources, setShowSources] = useState<string | null>(null)
        const [clients, setClients] = useState<AnalysisClient[]>([])
        const [selectedClientId, setSelectedClientId] = useState<string | null>(null)
        const [clientsLoading, setClientsLoading] = useState(true)
        const [activeConversationId, setActiveConversationId] = useState(conversationId)

    const bottomRef = useRef<HTMLDivElement>(null)
    const skipScrollRef = useRef(false)
    const initialScrollDoneRef = useRef(false)

    useEffect(() => {
        if (flashError) {
            setFlashError(null)
        }
    }, [flashError, setFlashError])

    useEffect(() => {
        let cancelled = false

        const loadClients = async () => {
            try {
                const availableClients = await listClients()
                if (cancelled) return

                setClients(availableClients)
                if (availableClients.length === 1) {
                    setSelectedClientId(availableClients[0].id)
                }
            } catch (err) {
                if (!cancelled) {
                    setError(getApiErrorMessage(err))
                }
            } finally {
                if (!cancelled) {
                    setClientsLoading(false)
                }
            }
        }

        void loadClients()

        return () => {
                    cancelled = true
                }
            }, [])

            useEffect(() => {
        if (!conversationId) return

        let cancelled = false

        const loadHistory = async () => {
            setLoadingHistory(true)

            try {
                const loadedMessages = await getEntireConversationMessages(conversationId)

                if (cancelled) return

                const restoredMessages = [...loadedMessages].reverse().map(
                    (message) => ({
                        ...message,
                        databaseLoading:
                            message.role === "assistant" &&
                            Boolean(message.analysis_query_id),
                    }) as MessageWithSources,
                )
                setMessages(restoredMessages)
                setLoadingHistory(false)

                // Load only the first page of each saved query result to avoid
                // hundreds of API calls for large result sets. Full results can
                // be loaded on demand via "Load more" or CSV export.
                const targets = restoredMessages.filter(
                    (message): message is MessageWithSources & { analysis_query_id: string } =>
                        message.role === "assistant" &&
                        typeof message.analysis_query_id === "string" &&
                        message.analysis_query_id.length > 0,
                )

                await Promise.all(
                    targets.map(async (message) => {
                        try {
                            const result = await runHistory(message.analysis_query_id)
                            if (cancelled) return
                            setMessages((current) =>
                                current.map((item) =>
                                    item.id === message.id
                                        ? {
                                            ...item,
                                            databaseResult: result,
                                            databaseLoading: false,
                                            databaseRefreshedAt: new Date().toISOString(),
                                        }
                                        : item,
                                ),
                            )
                        } catch (err) {
                            if (cancelled) return
                            setMessages((current) =>
                                current.map((item) =>
                                    item.id === message.id
                                        ? {
                                            ...item,
                                            databaseLoading: false,
                                            databaseError: getApiErrorMessage(err),
                                        }
                                        : item,
                                ),
                            )
                        }
                    }),
                )
            } catch (err) {
                if (!cancelled) {
                    setError(getApiErrorMessage(err))
                }
            } finally {
                if (!cancelled) {
                    setLoadingHistory(false)
                }
            }
        }

        void loadHistory()

        return () => {
            cancelled = true
        }
    }, [conversationId])

    useEffect(() => {
        if (skipScrollRef.current) {
            skipScrollRef.current = false
            return
        }

        bottomRef.current?.scrollIntoView({
            behavior: initialScrollDoneRef.current ? "smooth" : "auto",
        })

        if (messages.length > 0) {
            initialScrollDoneRef.current = true
        }
    }, [messages, sending])

    const handleSend = async (content: string) => {
        if (sending) return

        setError(null)
        setSending(true)

        const tempId = `temp-${generateId()}`
        const now = new Date().toISOString()

        setMessages((prev) => [
            ...prev,
            {
                id: tempId,
                user_id: null,
                conversation_id: conversationId ?? "",
                role: "user",
                content,
                created_at: now,
                updated_at: now,
            } as MessageWithSources,
        ])

        let activeId = activeConversationId

        try {
            const data: IntelligenceResponse = await askIntelligence({
                question: content,
                client_id: selectedClientId,
                conversation_id: activeId ?? undefined,
            })

            const databaseResult: AnalysisResponse | null = data.database
                ? {
                    title: data.database.title ?? content.slice(0, 80),
                    database: data.database.database ?? "",
                    tables: data.database.tables,
                    sql: data.database.sql ?? "",
                    analysis_query_id: data.database.analysis_query_id ?? undefined,
                    token: data.database.token,
                    result: {
                        columns: data.database.columns,
                        rows: data.database.rows,
                        page: data.database.page,
                        page_size: data.database.page_size,
                        has_more: data.database.has_more,
                        total_time_ms: data.database.total_time_ms ?? undefined,
                    },
                }
                : null
            const completeDatabaseResult = databaseResult

            activeId = data.conversation_id ?? activeId
            setActiveConversationId(activeId)

            setMessages((prev) => [
                ...prev.filter((m) => m.id !== tempId),
                {
                    id: data.user_message_id ?? tempId,
                    user_id: null,
                    conversation_id: activeId,
                    role: "user",
                    content,
                    created_at: data.created_at ?? now,
                    updated_at: data.created_at ?? now,
                } as MessageWithSources,
                {
                    id: data.assistant_message_id ?? `temp-${generateId()}`,
                    user_id: null,
                    conversation_id: activeId,
                    role: "assistant",
                    content: data.answer,
                    created_at: data.created_at ?? now,
                    updated_at: data.created_at ?? now,
                    intent: data.intent,
                    sources: data.document?.sources ?? data.sources ?? [],
                    databaseResult: completeDatabaseResult,
                    analysis_query_id: data.database?.analysis_query_id ?? null,
                    chart: data.chart ?? null,
                } as MessageWithSources,
            ])

            void refreshConversations()

            if (!conversationId && activeId) {
                router.replace(`/chat/${activeId}`)
            }

            if (data.database) {
                            // Query history removed from user chat
            }
        } catch (err) {
            const message = getApiErrorMessage(err)

            setMessages((prev) =>
                prev.filter((m) => m.id !== tempId)
            )

            setError(message)
        } finally {
            setSending(false)
        }
    }

    const isEmpty = !loadingHistory && messages.length === 0

    return (
            <TooltipProvider>
                <div className="min-h-0 flex-1 flex flex-col">
                    <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/50 px-4 py-2.5 md:px-6">
                        {!clientsLoading && clients.length > 1 && (
                            <div className="flex items-center gap-3">
                                <label htmlFor="chat-client" className="text-sm text-muted-foreground">
                                    Database
                                </label>
                                <Select
                                    value={selectedClientId ?? ""}
                                    onValueChange={(clientId) => {
                                        setSelectedClientId(clientId)
                                    }}
                                >
                                    <SelectTrigger id="chat-client" className="w-[240px]">
                                        <SelectValue placeholder="Select a client" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {clients.map((client) => (
                                            <SelectItem key={client.id} value={client.id}>
                                                {client.name} ({client.code})
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                    </div>

                {/* Chat Messages */}
                <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6">
                    {loadingHistory ? (
                        <div className="flex h-full min-h-[50vh] items-center justify-center gap-3 text-sm text-muted-foreground">
                            <Loader2 className="h-5 w-5 text-primary" />
                            <span>Loading conversation</span>
                        </div>
                    ) : isEmpty ? (
                        <div className="flex h-full min-h-[50vh] flex-col items-center justify-center text-center px-4">
                            <h1 className="mb-2 text-2xl font-semibold tracking-tight">Ask anything</h1>

                            <p className="mb-8 max-w-md text-sm text-muted-foreground">
                                {documents.length > 0
                                    ? "Your documents and databases are searched automatically when relevant."
                                    : "You can ask about your assigned databases. An administrator can add documents in the sidebar for document Q&A."}
                            </p>
                        </div>
                    ) : (
                        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
                            {messages.map((message) => (
                                <div key={message.id} className="flex flex-col gap-2">
                                    {message.role === "user" ? (
                                        <div className="flex justify-end">
                                            <div className="max-w-[75%] whitespace-pre-wrap wrap-break-word rounded-3xl bg-muted px-4 py-2.5 text-sm leading-relaxed text-foreground">
                                                {message.content}
                                            </div>
                                        </div>
                                    ) : (
                                        <>
                                            <MarkdownContent
                                                content={message.content}
                                                timestamp={message.created_at}
                                            />
                                            {(message as MessageWithSources).databaseResult && (
                                                <ResultTable
                                                    data={(message as MessageWithSources).databaseResult!}
                                                    refreshedAt={(message as MessageWithSources).databaseRefreshedAt}
                                                />
                                            )}
                                            {(message as MessageWithSources).databaseLoading && (
                                                <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-muted/30 p-3 text-sm text-muted-foreground">
                                                    <Loader2 className="size-4 animate-spin" />
                                                    Refreshing saved database results…
                                                </div>
                                            )}
                                            {(message as MessageWithSources).databaseError && (
                                                <p role="alert" className="rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
                                                    Could not refresh this database result: {(message as MessageWithSources).databaseError}
                                                </p>
                                            )}
                                        </>
                                    )}
                                    {((message as MessageWithSources).sources ??
                                        []).length > 0 && (
                                            <div className="mt-1">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    className="h-7 gap-1 text-xs text-muted-foreground"
                                                    onClick={() => setShowSources(
                                                        showSources === message.id ? null : message.id
                                                    )}
                                                >
                                                    <FileText className="h-3 w-3" />
                                                    Sources ({(message as MessageWithSources).sources!.length})
                                                    {showSources === message.id ? (
                                                        <ChevronUp className="h-3 w-3" />
                                                    ) : (
                                                        <ChevronDown className="h-3 w-3" />
                                                    )}
                                                </Button>

                                                {showSources === message.id && (
                                                    <div className="mt-2 rounded-lg border bg-muted/30 p-3">
                                                        <div className="mb-2">
                                                            <span className="text-xs font-medium text-muted-foreground">Referenced documents</span>
                                                        </div>
                                                        <div className="space-y-1 max-h-48 overflow-auto">
                                                            {(message as MessageWithSources).sources!.map((source, i) => (
                                                                <div
                                                                    key={i}
                                                                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs"
                                                                >
                                                                    <FileText className="size-4 shrink-0 text-muted-foreground" />
                                                                    <div className="min-w-0 flex-1">
                                                                        <p className="truncate font-medium">{source.filename || "Document"}</p>
                                                                        {source.page != null && (
                                                                            <p className="truncate text-muted-foreground">
                                                                                Page {source.page}
                                                                            </p>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                </div>
                            ))}

                            {sending && (
                                <div className="flex items-center gap-1.5 py-2" aria-label="Assistant is thinking">
                                    <span className="size-2 rounded-full bg-muted-foreground" />
                                    <span className="size-2 rounded-full bg-muted-foreground" />
                                    <span className="size-2 rounded-full bg-muted-foreground" />
                                </div>
                            )}

                            <div ref={bottomRef} />
                        </div>
                    )}

                    {error && (
                        <div
                            role="alert"
                            className="mx-auto mb-4 flex w-full max-w-3xl items-start gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-4 text-destructive"
                        >
                            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                            <span className="flex-1 text-sm">{error}</span>
                            <Button variant="ghost" size="icon" onClick={() => setError(null)} className="h-7 w-7">
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    )}
                </div>

                {/* Input pinned at the bottom */}
                <ChatInput
                    onSend={handleSend}
                    disabled={sending}
                    placeholder="Ask about your documents or databases"
                />
            </div>
        </TooltipProvider>
    )
}

export default DocumentsChat