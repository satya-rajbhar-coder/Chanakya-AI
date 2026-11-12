"use client"

import React, { KeyboardEvent, useEffect, useRef, useState } from "react"
import { ArrowUp } from "lucide-react"

import { Button } from "@/components/ui/button"

interface ChatInputProps {
    onSend: (message: string) => void
    disabled?: boolean
    placeholder?: string
}

const ChatInput = ({
    onSend,
    disabled = false,
    placeholder = "Ask about your databases...",
}: ChatInputProps) => {
    const [message, setMessage] = useState("")

    const textareaRef = useRef<HTMLTextAreaElement>(null)

    const canSend = message.trim().length > 0 && !disabled

    useEffect(() => {
        const element = textareaRef.current
        if (!element) return

        element.style.height = "auto"
        element.style.height = `${Math.min(element.scrollHeight, 120)}px`
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
        <div className="w-full shrink-0 px-4 pb-4 pt-2">
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
                        className="max-h-48 min-h-10 flex-1 resize-none bg-transparent px-3 py-2.5 text-sm outline-none placeholder:text-muted-foreground"
                    />

                    <Button
                        type="button"
                        size="icon"
                        onClick={handleSend}
                        disabled={!canSend}
                        aria-label="Send message"
                        className="size-10 shrink-0 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm transition-all"
                    >
                        <ArrowUp className="size-4" />
                    </Button>
                </div>
            </div>
        </div>
    )
}

export default ChatInput