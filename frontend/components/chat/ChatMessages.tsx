"use client"

import React from "react"

import { MessageResponse } from "@/services/messages"
import MarkdownContent from "./MarkdownContent"

interface ChatMessagesProps {
    messages: MessageResponse[]
    pending?: boolean
}

const ThinkingIndicator = () => (
    <div className="flex w-full justify-start">
        <div className="flex items-center gap-2 rounded-lg bg-muted px-4 py-3 text-sm text-muted-foreground">
            <span className="flex gap-1" aria-hidden>
                <span className="size-2 animate-bounce rounded-full bg-current [animation-delay:-0.3s]" />
                <span className="size-2 animate-bounce rounded-full bg-current [animation-delay:-0.15s]" />
                <span className="size-2 animate-bounce rounded-full bg-current" />
            </span>
            Thinking…
        </div>
    </div>
)

const ChatMessages = ({ messages, pending = false }: ChatMessagesProps) => {
    return (
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
            {messages.map((message) =>
                message.role === "user" ? (
                    <div key={message.id} className="flex w-full justify-end">
                        <div className="max-w-[70%] whitespace-pre-wrap wrap-break-word rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground">
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
