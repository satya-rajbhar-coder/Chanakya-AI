"use client"

import { useState } from "react"
import { Check, Copy } from "lucide-react"

import { copyToClipboard } from "./markdown-utils"

interface CodeBlockProps {
    language: string
    code: string
}

export default function CodeBlock({ language, code }: CodeBlockProps) {
    const [copied, setCopied] = useState(false)

    const handleCopy = async () => {
        const success = await copyToClipboard(code)

        if (!success) {
            return
        }

        setCopied(true)

        setTimeout(() => {
            setCopied(false)
        }, 2000)
    }

    return (
        <div className="my-4 overflow-hidden rounded-lg border bg-muted/50">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-2">
                <span className="text-xs font-medium text-muted-foreground">
                    {language}
                </span>

                <button
                    type="button"
                    onClick={handleCopy}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground"
                >
                    {copied ? (
                        <Check className="size-3" />
                    ) : (
                        <Copy className="size-3" />
                    )}

                    {copied ? "Copied" : "Copy"}
                </button>
            </div>

            {/* Code */}
            <pre className="overflow-x-auto p-4 text-sm leading-relaxed">
                <code>{code}</code>
            </pre>
        </div>
    )
}