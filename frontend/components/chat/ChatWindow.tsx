"use client"

import React, { useEffect, useRef, useState } from "react"
import { useRouter } from "next/navigation"
import { Loader2, X } from "lucide-react"

import { SidebarTrigger } from "@/components/ui/sidebar"
import { useWorkspace } from "@/components/workspace-provider"

import { createConversation } from "@/services/conversations"
import { getApiErrorMessage } from "@/services/error"
import {
    getAllConversationMessages,
    MessageResponse,
    sendMessage,
} from "@/services/messages"

import ChatInput from "./ChatInput"
import ChatMessages from "./ChatMessages"

interface ChatWindowProps {
    // Absent on "/" (new chat). The conversation is created on first send.
    conversationId?: string
}

const ChatWindow = ({ conversationId }: ChatWindowProps) => {
    const router = useRouter()

    const {
        conversations,
        documents,
        uploadingName,
        uploadError,
        uploadFiles,
        clearUploadError,
        refreshConversations,
        flashError,
        setFlashError,
    } = useWorkspace()

    const [messages, setMessages] = useState<MessageResponse[]>([])
    const [nextCursor, setNextCursor] = useState<string | null>(null)

    const [loadingHistory, setLoadingHistory] = useState(Boolean(conversationId))
    const [loadingOlder, setLoadingOlder] = useState(false)
    const [sending, setSending] = useState(false)

    // Seeded from a failure that happened right before we navigated here.
    const [error, setError] = useState<string | null>(flashError)

    const bottomRef = useRef<HTMLDivElement>(null)
    const skipScrollRef = useRef(false)
    const initialScrollDoneRef = useRef(false)

    const title =
        conversations.find((c) => c.id === conversationId)?.title ?? "New chat"

    // Consume the flash error once it has been copied into local state.
    useEffect(() => {
        if (flashError) {
            setFlashError(null)
        }
    }, [flashError, setFlashError])

    // ---- load history -----------------------------------------------------
    useEffect(() => {
        if (!conversationId) {
            return
        }

        let cancelled = false

        const loadHistory = async () => {
            setLoadingHistory(true)

            try {
                const page = await getAllConversationMessages({
                    conversation_id: conversationId,
                })

                if (cancelled) return

                // The API returns newest first; render oldest first.
                setMessages([...page.items].reverse())
                setNextCursor(page.next_cursor)
            } catch (err) {
                if (!cancelled) setError(getApiErrorMessage(err))
            } finally {
                if (!cancelled) setLoadingHistory(false)
            }
        }

        void loadHistory()

        return () => {
            cancelled = true
        }
    }, [conversationId])

    // ---- keep the view pinned to the newest message -------------------------
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

    // ---- older messages ---------------------------------------------------
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
            setMessages((prev) => [...[...page.items].reverse(), ...prev])
            setNextCursor(page.next_cursor)
        } catch (err) {
            setError(getApiErrorMessage(err))
        } finally {
            setLoadingOlder(false)
        }
    }

    // ---- send -------------------------------------------------------------
    const handleSend = async (content: string) => {
        if (sending) {
            return
        }

        setError(null)
        setSending(true)

        // Show the user's message immediately; swapped for the saved one
        // when the server answers.
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
            },
        ])

        let activeId: string | undefined = conversationId
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

            const { user_message, assistant_message } = await sendMessage(
                activeId,
                { content }
            )

            setMessages((prev) => [
                ...prev.filter((m) => m.id !== tempId),
                user_message,
                assistant_message,
            ])

            void refreshConversations()

            if (createdHere) {
                router.replace(`/chat/${activeId}`)
            }
        } catch (err) {
            const message = getApiErrorMessage(err)

            if (createdHere && activeId) {
                // The conversation (and the saved user message) exist now, so
                // go there rather than leaving a second "new chat" behind.
                setFlashError(message)
                router.replace(`/chat/${activeId}`)
                return
            }

            setError(message)
        } finally {
            setSending(false)
        }
    }

    const isEmpty = !loadingHistory && messages.length === 0

    return (
        <div className="flex min-h-0 flex-1 flex-col">
            <header className="flex h-12 shrink-0 items-center gap-2 border-b px-3">
                <SidebarTrigger className="md:hidden" />
                <h1 className="truncate text-sm font-medium">{title}</h1>
            </header>

            <div className="min-h-0 flex-1 overflow-y-auto p-4">
                {loadingHistory ? (
                    <div className="flex h-full min-h-[50vh] items-center justify-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="size-4 animate-spin" />
                        Loading messages…
                    </div>
                ) : isEmpty ? (
                    <div className="flex h-full min-h-[50vh] flex-col items-center justify-center text-center">
                        <h2 className="text-3xl font-semibold">Ask anything</h2>
                        <p className="mt-2 max-w-md text-sm text-muted-foreground">
                            {documents.length > 0
                                ? "Your uploaded documents are searched automatically when they're relevant to your question."
                                : "Attach a PDF with the paperclip, wait for it to be indexed, then ask questions about it."}
                        </p>
                    </div>
                ) : (
                    <>
                        {nextCursor && (
                            <div className="mb-4 flex justify-center">
                                <button
                                    type="button"
                                    onClick={loadOlder}
                                    disabled={loadingOlder}
                                    className="rounded-full border px-3 py-1 text-xs text-muted-foreground hover:bg-accent disabled:opacity-50"
                                >
                                    {loadingOlder ? "Loading…" : "Load older messages"}
                                </button>
                            </div>
                        )}

                        <ChatMessages messages={messages} pending={sending} />
                    </>
                )}

                <div ref={bottomRef} />
            </div>

            {error && (
                <div
                    role="alert"
                    className="mx-auto flex w-full max-w-4xl items-start gap-2 px-4 pb-2 text-sm text-destructive"
                >
                    <span className="flex-1">{error}</span>
                    <button
                        type="button"
                        onClick={() => setError(null)}
                        aria-label="Dismiss error"
                    >
                        <X className="size-4" />
                    </button>
                </div>
            )}

            <ChatInput
                onSend={handleSend}
                onAttach={(files) => void uploadFiles(files)}
                disabled={sending}
                uploadingName={uploadingName}
                uploadError={uploadError}
                onDismissUploadError={clearUploadError}
                documentCount={documents.length}
            />
        </div>
    )
}

export default ChatWindow
