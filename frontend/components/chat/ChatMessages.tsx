"use client"

import React from "react"

import { MessageResponse } from "@/services/messages"
import MarkdownContent from "./MarkdownContent"

interface ChatMessagesProps {
    messages: MessageResponse[]
    pending?: boolean
}

const ThinkingIndicator = () => (
    <div className="flex w-full items-center gap-1.5 py-2" aria-label="Assistant is thinking">
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.3s]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:-0.15s]" />
        <span className="size-2 animate-bounce rounded-full bg-muted-foreground" />
    </div>
)

const ChatMessages = ({ messages, pending = false }: ChatMessagesProps) => {
    return (
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
            {messages.map((message) =>
                message.role === "user" ? (
                    <div key={message.id} className="flex w-full justify-end">
                        <div className="max-w-[75%] whitespace-pre-wrap break-words rounded-3xl bg-muted px-4 py-2.5 text-sm leading-relaxed text-foreground">
                            {message.content}
                        </div>
                    </div>
                ) : (
                    <MarkdownContent
                        key={message.id}
                        content={message.content}
                        timestamp={message.created_at}
                    />
                )
            )}

            {pending && <ThinkingIndicator />}
        </div>
    )
}

export default ChatMessages