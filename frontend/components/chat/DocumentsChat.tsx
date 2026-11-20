"use client"

import React, { useEffect, useRef, useState } from "react"
import { Loader2, X, FileText, ChevronDown, ChevronUp, AlertCircle, Sparkles, RotateCcw } from "lucide-react"

import { useWorkspace } from "@/components/workspace-provider"
import {
    getEntireConversationMessages,
    MessageResponse,
} from "@/services/messages"
import { askIntelligence, IntelligenceResponse } from "@/services/intelligence"
import { runHistory } from "@/services/analysis"
import { getApiErrorMessage } from "@/services/error"
import { generateId } from "@/lib/utils"
import { useRouter } from "next/navigation"

import ChatInput from "./ChatInput"
import MarkdownContent from "./MarkdownContent"
import ResultTable from "./ResultTable"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { TooltipProvider } from "@/components/ui/tooltip"
import { useToast } from "@/components/ui/toast-provider"
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
    sendError?: string
    intent?: string
    sources?: DocumentSource[]
    databaseResult?: any | null
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
    const { showToast } = useToast()

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
    const [activeConversationId, setActiveConversationId] = useState(conversationId)

    const bottomRef = useRef<HTMLDivElement>(null)
    const skipScrollRef = useRef(false)
    const initialScrollDoneRef = useRef(false)
    const abortControllerRef = useRef<AbortController | null>(null)

    useEffect(() => {
        if (flashError) {
            setFlashError(null)
        }
    }, [flashError, setFlashError])

    useEffect(() => {
        if (!conversationId) return

        const abortController = new AbortController()
        abortControllerRef.current = abortController

        let cancelled = false

        const loadHistory = async () => {
            setLoadingHistory(true)

            try {
                const loadedMessages = await getEntireConversationMessages(
                    conversationId,
                    abortController.signal,
                )

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

                const targets = restoredMessages.filter(
                    (message): message is MessageWithSources & { analysis_query_id: string } =>
                        message.role === "assistant" &&
                        typeof message.analysis_query_id === "string" &&
                        message.analysis_query_id.length > 0,
                )

                await Promise.all(
                    targets.map(async (message) => {
                        try {
                            const result = await runHistory(
                                message.analysis_query_id,
                                0,
                                500,
                                abortController.signal,
                            )
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
                            if (err instanceof DOMException && err.name === "AbortError") return
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
                if (cancelled) return
                if (err instanceof DOMException && err.name === "AbortError") return
                setError(getApiErrorMessage(err))
            } finally {
                if (!cancelled) {
                    setLoadingHistory(false)
                }
            }
        }

        void loadHistory()

        return () => {
            cancelled = true
            abortController.abort()
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

    const handleSend = async (content: string, retryId?: string) => {
        if (sending) return

        const sendAbortController = new AbortController()

        setError(null)
        setSending(true)

        const tempId = retryId ?? `temp-${generateId()}`
        const now = new Date().toISOString()

        if (retryId) {
            setMessages((prev) =>
                prev.map((message) =>
                    message.id === retryId
                        ? { ...message, sendError: undefined }
                        : message,
                ),
            )
        } else {
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
        }

        let activeId = activeConversationId

        try {
            const data: IntelligenceResponse = await askIntelligence(
                {
                    question: content,
                    conversation_id: activeId ?? undefined,
                },
                sendAbortController.signal,
            )

            const databaseResult: any | null = data.database
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
            if (err instanceof DOMException && err.name === "AbortError") return
            const message = getApiErrorMessage(err)

            setMessages((prev) =>
                prev.map((item) =>
                    item.id === tempId ? { ...item, sendError: message } : item,
                ),
            )
            showToast({
                title: "Message not sent",
                description: message,
                type: "error",
            })
        } finally {
            setSending(false)
        }
    }

    const isEmpty = !loadingHistory && messages.length === 0

    return (
        <TooltipProvider>
            <div className="min-h-0 flex-1 flex flex-col">
                <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border/50 px-4 py-2.5 md:px-6">
                </div>

                {/* Chat Messages */}
                <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6">
                    {error && (
                        <div
                            role="alert"
                            className="mb-4 flex w-full items-start gap-3 rounded-lg border border-destructive/20 bg-destructive/5 p-4 text-destructive"
                        >
                            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" />
                            <div className="flex-1">
                                <p className="text-sm">{error}</p>
                                <button
                                    type="button"
                                    onClick={() => setError(null)}
                                    className="mt-1 text-xs text-primary underline underline-offset-4 hover:text-primary/80"
                                >
                                    Dismiss
                                </button>
                            </div>
                            <Button variant="ghost" size="icon" onClick={() => setError(null)} className="h-7 w-7">
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    )}
                    {loadingHistory ? (
                        <div className="flex h-full min-h-[50vh] items-center justify-center gap-3 text-sm text-muted-foreground">
                            <Loader2 className="h-5 w-5 text-primary" />
                            <span>Loading conversation</span>
                        </div>
                    ) : isEmpty ? (
                        <div className="flex h-full min-h-[50vh] flex-col items-center justify-center text-center px-4">
                            <div className="flex flex-col items-center gap-3">
                                <div className="p-3 rounded-full bg-primary/10 text-primary">
                                    <Sparkles className="size-6" />
                                </div>
                                <h1 className="mb-2 text-2xl font-semibold tracking-tight">Ask anything</h1>

                                <p className="mb-8 max-w-md text-sm text-muted-foreground">
                                    {documents.length > 0
                                        ? "Your documents and databases are searched automatically when relevant."
                                        : "You can ask about your assigned databases. An administrator can add documents in the sidebar for document Q&A."}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
                            {messages.map((message) => (
                                <div key={message.id} className="flex flex-col gap-2">
                                    {message.role === "user" ? (
                                        <div className="flex justify-end">
                                            <div className="max-w-[75%]">
                                                <div className="whitespace-pre-wrap wrap-break-word rounded-3xl bg-muted px-4 py-2.5 text-sm leading-relaxed text-foreground">
                                                    {message.content}
                                                </div>
                                                {(message as MessageWithSources).sendError && (
                                                    <div
                                                        role="alert"
                                                        className="mt-2 flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-destructive"
                                                    >
                                                        <AlertCircle className="mt-0.5 size-4 shrink-0" />
                                                        <div>
                                                            <p className="text-sm">
                                                                {(message as MessageWithSources).sendError}
                                                            </p>
                                                            <Button
                                                                variant="outline"
                                                                size="sm"
                                                                className="mt-2 h-8 border-destructive/30 text-destructive hover:bg-destructive/10"
                                                                onClick={() => handleSend(message.content, message.id)}
                                                            >
                                                                <RotateCcw className="size-3" />
                                                                Try again
                                                            </Button>
                                                        </div>
                                                    </div>
                                                )}
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
                                                    Refreshing saved database resultsâ€¦
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
                                                Sources {(message as MessageWithSources).sources!.length}
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
