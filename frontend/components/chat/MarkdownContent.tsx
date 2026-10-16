"use client"

import { useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Check, Copy } from "lucide-react"

import { markdownComponents } from "../markdown/MarkdownComponents"
import { copyToClipboard } from "../markdown/markdown-utils"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

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
        <div className="group w-full">
            <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents}
                >
                    {content}
                </ReactMarkdown>
            </div>

            <div className="mt-1 flex h-7 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleCopy}
                    className="size-7 text-muted-foreground hover:text-foreground"
                    aria-label={copied ? "Copied" : "Copy response"}
                >
                    {copied ? (
                        <Check className="size-3.5 text-emerald-500" />
                    ) : (
                        <Copy className="size-3.5" />
                    )}
                </Button>

                {timestamp && (
                    <span className="text-xs text-muted-foreground">
                        {new Date(timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                        })}
                    </span>
                )}
            </div>
        </div>
    )
}

export default MarkdownContent