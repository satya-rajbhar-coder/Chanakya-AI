"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2, X, FileText, Search, ChevronDown, ChevronUp, AlertCircle } from "lucide-react"

import { useWorkspace } from "@/components/workspace-provider"
import {
    getAllConversationMessages,
    MessageResponse,
    sendMessage,
} from "@/services/messages"
import { createConversation } from "@/services/conversations"
import { getApiErrorMessage } from "@/services/error"

import ChatInput from "./ChatInput"
import MarkdownContent from "./MarkdownContent"
import { Button } from "@/components/ui/button"
import { TooltipProvider } from "@/components/ui/tooltip"

interface DocumentsChatProps {
    conversationId?: string
}

interface MessageWithSources extends MessageResponse {
    sources?: Array<{
        document_title: string
        chunk_text: string
        score: number
    }>
}

const DocumentsChat = ({ conversationId }: DocumentsChatProps) => {
    const {
        documents,
        refreshConversations,
        flashError,
        setFlashError,
    } = useWorkspace()

    const [messages, setMessages] = useState<MessageWithSources[]>([])
    const [nextCursor, setNextCursor] = useState<string | null>(null)

    const [loadingHistory, setLoadingHistory] = useState(Boolean(conversationId))
    const [loadingOlder, setLoadingOlder] = useState(false)
    const [sending, setSending] = useState(false)
    const [error, setError] = useState<string | null>(flashError)
    const [showSources, setShowSources] = useState<string | null>(null)

    const bottomRef = useRef<HTMLDivElement>(null)
    const skipScrollRef = useRef(false)
    const initialScrollDoneRef = useRef(false)

    useEffect(() => {
        if (flashError) {
            setFlashError(null)
        }
    }, [flashError, setFlashError])

    useEffect(() => {
        if (!conversationId) {
            setMessages([])
            setNextCursor(null)
            setLoadingHistory(false)
            return
        }

        let cancelled = false

        const loadHistory = async () => {
            setLoadingHistory(true)

            try {
                const page = await getAllConversationMessages({ conversation_id: conversationId })

                if (cancelled) return

                setMessages([...page.items].reverse() as MessageWithSources[])
                setNextCursor(page.next_cursor)
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

    const loadOlder = async () => {
        if (!conversationId || !nextCursor || loadingOlder) {
            return
        }

        setLoadingOlder(true)

        try {
            const page = await getAllConversationMessages({
                conversation_id: conversationId,
                cursor: nextCursor,
            })

            skipScrollRef.current = true

            setMessages((prev: MessageWithSources[]) => [
                ...([...page.items].reverse() as MessageWithSources[]),
                ...prev,
            ])

            setNextCursor(page.next_cursor)
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setLoadingOlder(false)
        }
    }

    const handleSend = async (content: string) => {
        if (sending) return

        setError(null)
        setSending(true)

        const tempId = `temp-${Date.now()}`
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

        let activeId = conversationId
        let createdHere = false

        try {
            if (!activeId) {
                const conversation = await createConversation({
                    title: content.slice(0, 60),
                })

                activeId = conversation.id
                createdHere = true

                void refreshConversations()
            }

            const {
                user_message,
                assistant_message,
            } = await sendMessage(activeId, { content })

            setMessages((prev) => [
                ...prev.filter((m) => m.id !== tempId),
                user_message as MessageWithSources,
                assistant_message as MessageWithSources,
            ])

            void refreshConversations()

            if (createdHere) {
                window.history.replaceState(
                    null,
                    "",
                    `/chat/${activeId}`
                )
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
                {/* Header */}
                <div className="flex shrink-0 items-center justify-between gap-4 px-6 py-3">
                    <div className="flex items-center gap-2">
                        <h2 className="text-sm font-medium">Documents</h2>
                        <span className="text-xs text-muted-foreground">
                            {documents.length > 0
                                ? `${documents.length} indexed`
                                : "No documents yet"}
                        </span>
                    </div>
                </div>

                {/* Chat Messages */}
                <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6">
                    {loadingHistory ? (
                        <div className="flex h-full min-h-[50vh] items-center justify-center gap-3 text-sm text-muted-foreground">
                            <Loader2 className="h-5 w-5 animate-spin text-primary" />
                            <span>Loading conversation</span>
                        </div>
                    ) : isEmpty ? (
                        <div className="flex h-full min-h-[50vh] flex-col items-center justify-center text-center px-4">
                            <h1 className="mb-2 text-2xl font-semibold tracking-tight">Ask anything</h1>

                            <p className="mb-8 max-w-md text-sm text-muted-foreground">
                                {documents.length > 0
                                    ? "Your documents are searched automatically when relevant."
                                    : "No documents available yet. An administrator can add them in the sidebar."}
                            </p>

                            {documents.length > 0 && (
                                <div className="w-full max-w-xl space-y-2">
                                    {[
                                        "What are the key policies in the HR document?",
                                        "Summarize the latest quarterly report",
                                        "Find all mentions of 'budget' in the documents",
                                        "What are the compliance requirements?"
                                    ].map((q) => (
                                        <button
                                            key={q}
                                            onClick={() => handleSend(q)}
                                            className="w-full rounded-xl border px-4 py-2.5 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                                        >
                                            {q}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
                            {messages.map((message) => (
                                <div key={message.id} className="flex flex-col gap-2">
                                    {message.role === "user" ? (
                                        <div className="flex justify-end">
                                            <div className="max-w-[75%] whitespace-pre-wrap break-words rounded-3xl bg-muted px-4 py-2.5 text-sm leading-relaxed text-foreground">
                                                {message.content}
                                            </div>
                                        </div>
                                    ) : (
                                        <MarkdownContent
                                            content={message.content}
                                            timestamp={message.created_at}
                                        />
                                    )}
                                    {(message as MessageWithSources).sources && (message as MessageWithSources).sources!.length > 0 && (
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
                                                                className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs transition-colors hover:bg-accent"
                                                            >
                                                                <FileText className="size-4 shrink-0 text-muted-foreground" />
                                                                <div className="min-w-0 flex-1">
                                                                    <p className="truncate font-medium">{source.document_title || "Document"}</p>
                                                                    <p className="truncate text-muted-foreground">{source.chunk_text?.slice(0, 80)}</p>
                                                                </div>
                                                                <span className="shrink-0 text-xs text-muted-foreground">{Math.round((source.score || 0) * 100)}%</span>
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
                                    <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
                                    <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
                                    <span className="size-2 animate-bounce rounded-full bg-muted-foreground" />
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
                    placeholder="Ask about your documents"
                    documentCount={documents.length}
                />
            </div>
        </TooltipProvider>
    )
}

export default DocumentsChat