"use client"

import { useState } from "react"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"
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
        <div className="my-4 overflow-hidden rounded-lg border bg-[#282c34]">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
                <span className="text-xs font-medium text-white/60">
                    {language}
                </span>

                <button
                    type="button"
                    onClick={handleCopy}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-white/60 transition-colors hover:bg-white/10 hover:text-white"
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
            <SyntaxHighlighter
                language={language}
                style={oneDark}
                customStyle={{
                    margin: 0,
                    padding: "1rem",
                    background: "transparent",
                    fontSize: "0.875rem",
                    lineHeight: "1.5",
                }}
            >
                {code}
            </SyntaxHighlighter>
        </div>
    )
}