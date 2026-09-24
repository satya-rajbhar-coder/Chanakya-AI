"use client"

import React, { KeyboardEvent, useEffect, useRef, useState } from "react"
import { ArrowUp, Loader2, Paperclip, X } from "lucide-react"

import { Button } from "@/components/ui/button"
import { ACCEPTED_FILES } from "@/components/documents-panel"

interface ChatInputProps {
    onSend: (message: string) => void
    onAttach: (files: File[]) => void
    disabled?: boolean
    uploadingName?: string | null
    uploadError?: string | null
    onDismissUploadError?: () => void
    documentCount?: number
}

const ChatInput = ({
    onSend,
    onAttach,
    disabled = false,
    uploadingName = null,
    uploadError = null,
    onDismissUploadError,
    documentCount = 0,
}: ChatInputProps) => {
    const [message, setMessage] = useState("")

    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const uploading = uploadingName !== null
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

    const handleFiles = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(event.target.files ?? [])
        event.target.value = ""

        if (files.length > 0) {
            onAttach(files)
        }
    }

    return (
        <div className="w-full shrink-0 border-t bg-background p-4">
            <div className="mx-auto w-full max-w-4xl">
                <div className="flex items-end gap-2 rounded-3xl border bg-background p-1.5 shadow-sm">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept={ACCEPTED_FILES}
                        multiple
                        onChange={handleFiles}
                        className="hidden"
                    />

                    <Button
                        type="button"
                        size="icon"
                        variant="outline"
                        onClick={() => fileInputRef.current?.click()}
                        disabled={uploading}
                        title="Upload PDF, TXT or Markdown"
                        aria-label="Upload documents"
                        className="h-10 w-10 shrink-0 rounded-full border-0 shadow-none"
                    >
                        <Paperclip className="h-5 w-5" />
                    </Button>

                    <textarea
                        ref={textareaRef}
                        value={message}
                        rows={1}
                        onChange={(event) => setMessage(event.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Ask anything..."
                        aria-label="Message"
                        className="max-h-50 min-h-10 flex-1 resize-none bg-transparent px-1 py-2 text-base outline-none placeholder:text-muted-foreground"
                    />

                    <Button
                        type="button"
                        size="icon"
                        onClick={handleSend}
                        disabled={!canSend}
                        aria-label="Send message"
                        className="h-10 w-10 shrink-0 rounded-full"
                    >
                        <ArrowUp className="h-5 w-5" />
                    </Button>
                </div>

                <div className="mt-2 min-h-4 px-3 text-xs">
                    {uploading ? (
                        <span className="flex items-center gap-2 text-muted-foreground">
                            <Loader2 className="size-3.5 animate-spin" />
                            Indexing {uploadingName}… large PDFs can take a minute.
                        </span>
                    ) : uploadError ? (
                        <span
                            role="alert"
                            className="flex items-start gap-2 text-destructive"
                        >
                            <span className="flex-1">{uploadError}</span>
                            <button
                                type="button"
                                onClick={onDismissUploadError}
                                aria-label="Dismiss"
                            >
                                <X className="size-3.5" />
                            </button>
                        </span>
                    ) : documentCount > 0 ? (
                        <span className="text-muted-foreground">
                            Answers use your {documentCount} indexed{" "}
                            {documentCount === 1 ? "document" : "documents"} when relevant.
                        </span>
                    ) : null}
                </div>
            </div>
        </div>
    )
}

export default ChatInput
