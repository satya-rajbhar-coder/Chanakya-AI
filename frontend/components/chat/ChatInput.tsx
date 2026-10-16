"use client"

import React, { KeyboardEvent, useEffect, useRef, useState } from "react"
import { ArrowUp } from "lucide-react"

import { Button } from "@/components/ui/button"

interface ChatInputProps {
    onSend: (message: string) => void
    disabled?: boolean
    placeholder?: string
    documentCount?: number
}

const ChatInput = ({
    onSend,
    disabled = false,
    placeholder = "Ask anything",
    documentCount = 0,
}: ChatInputProps) => {
    const [message, setMessage] = useState("")

    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const canSend = message.trim().length > 0 && !disabled

    useEffect(() => {
        const element = textareaRef.current
        if (!element) return

        element.style.height = "auto"
        element.style.height = `${Math.min(element.scrollHeight, 200)}px`
    }, [message])

    const handleSend = () => {
        const trimmed = message.trim()

        if (!trimmed || disabled) {
            return
        }

        onSend(trimmed)
        setMessage("")
    }

    const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
        if (
            event.key === "Enter" &&
            !event.shiftKey &&
            !event.nativeEvent.isComposing
        ) {
            event.preventDefault()
            handleSend()
        }
    }

    return (
        <div className="w-full shrink-0 bg-gradient-to-t from-background via-background to-transparent px-4 pb-4 pt-2">
            <div className="mx-auto w-full max-w-3xl">
                <div className="flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm">
                    <textarea
                        ref={textareaRef}
                        value={message}
                        rows={1}
                        onChange={(event) => setMessage(event.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder={placeholder}
                        aria-label="Message"
                        className="max-h-50 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted-foreground"
                    />

                    <Button
                        type="button"
                        size="icon"
                        onClick={handleSend}
                        disabled={!canSend}
                        aria-label="Send message"
                        className="size-9 shrink-0 rounded-full"
                    >
                        <ArrowUp className="size-4" />
                    </Button>
                </div>

                <p className="mt-2 h-4 text-center text-xs text-muted-foreground">
                    {documentCount > 0
                        ? `Answers search ${documentCount} indexed ${documentCount === 1 ? "document" : "documents"} when relevant.`
                        : ""}
                </p>
            </div>
        </div>
    )
}

export default ChatInput