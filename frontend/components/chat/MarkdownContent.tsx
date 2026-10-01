"use client"

import { useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import rehypeRaw from "rehype-raw"
import { Check, Copy } from "lucide-react"

import { markdownComponents } from "../markdown/MarkdownComponents"
import { copyToClipboard } from "../markdown/markdown-utils"

interface MarkdownContentProps {
    content: string
    timestamp?: string
}

const MarkdownContent = ({
    content,
    timestamp,
}: MarkdownContentProps) => {
    const [copied, setCopied] = useState(false)

    const handleCopy = async () => {
        const success = await copyToClipboard(content)

        if (!success) {
            return
        }

        setCopied(true)

        setTimeout(() => {
            setCopied(false)
        }, 2000)
    }

    return (
        <div className="flex w-full justify-start">
            <div className="min-w-0 max-w-[85%] rounded-lg bg-transparent px-4 py-3">

                <div className="wrap-break-word text-sm">
                    <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        rehypePlugins={[rehypeRaw]}
                        components={markdownComponents}
                    >
                        {content}
                    </ReactMarkdown>
                </div>

                <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">

                    {timestamp && (
                        <span>
                            {new Date(timestamp).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                            })}
                        </span>
                    )}

                    <button
                        type="button"
                        onClick={handleCopy}
                        className="rounded p-1 transition-colors hover:bg-background hover:text-foreground"
                        title="Copy message"
                        aria-label="Copy message"
                    >
                        {copied ? (
                            <Check className="size-3.5" />
                        ) : (
                            <Copy className="size-3.5" />
                        )}
                    </button>

                </div>
            </div>
        </div>
    )
}

export default MarkdownContent
