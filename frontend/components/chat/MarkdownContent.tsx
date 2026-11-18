"use client"

import { useState, useMemo } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import remarkMath from "remark-math"
import rehypeKatex from "rehype-katex"
import type { Pluggable } from "unified"
import { Check, Copy } from "lucide-react"

import { markdownComponents } from "../markdown/MarkdownComponents"
import { copyToClipboard } from "../markdown/markdown-utils"
import { Button } from "@/components/ui/button"

interface MarkdownContentProps {
    content: string
    timestamp?: string
    isStreaming?: boolean
}

const MarkdownContent = ({
    content,
    timestamp,
    isStreaming = false,
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

    // Memoize plugins to prevent re-creation on each render
    const plugins = useMemo(
        () => [
            remarkGfm,
            remarkMath,
        ],
        []
    )

    const rehypePlugins = useMemo<Pluggable[]>(
        () => [
            [rehypeKatex, { strict: false, trust: true }] as Pluggable,
        ],
        []
    )

    return (
        <div className="group w-full">
            <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                <ReactMarkdown
                    remarkPlugins={plugins}
                    rehypePlugins={rehypePlugins}
                    components={markdownComponents}
                    // Allow HTML for KaTeX output
                    allowedElements={[
                        "h1", "h2", "h3", "h4", "h5", "h6",
                        "p", "br", "hr",
                        "ul", "ol", "li",
                        "table", "thead", "tbody", "tr", "th", "td",
                        "blockquote", "pre", "code",
                        "a", "strong", "em", "del", "ins", "sup", "sub",
                        "img", "figure", "figcaption",
                        "span", "div", "section",
                        // KaTeX elements
                        "math", "mi", "mo", "mn", "ms", "mtext", "mspace",
                        "mrow", "mfrac", "msqrt", "mroot", "mfenced",
                        "menclose", "msub", "msup", "msubsup", "munder",
                        "mover", "munderover", "mmultiscripts", "mtable",
                        "mtr", "mtd", "mlabeledtr", "maction",
                        // MathML
                        "annotation", "annotation-xml", "semantics",
                    ]}
                >
                    {content}
                </ReactMarkdown>
            </div>

            <div className="mt-1 flex h-7 items-center gap-1">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleCopy}
                    className="size-7 text-muted-foreground"
                    aria-label={copied ? "Copied" : "Copy response"}
                    disabled={isStreaming}
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

                {isStreaming && (
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <span className="size-1.5 rounded-full bg-primary animate-pulse" />
                        Streaming...
                    </span>
                )}
            </div>
        </div>
    )
}

export default MarkdownContent