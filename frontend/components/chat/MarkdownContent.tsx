"use client"

import React, { useState } from "react"
import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism"
import { Check, Copy } from "lucide-react"

interface MarkdownContentProps {
    content: string
    timestamp?: string
}

const copyToClipboard = async (text: string): Promise<boolean> => {
    try {
        await navigator.clipboard.writeText(text)
        return true
    } catch {
        return false
    }
}

const CodeBlock = ({ language, code }: { language: string; code: string }) => {
    const [copied, setCopied] = useState(false)

    const handleCopy = async () => {
        if (await copyToClipboard(code)) {
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        }
    }

    return (
        <div className="my-4 overflow-hidden rounded-lg border bg-[#282c34]">
            <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
                <span className="text-xs font-medium text-white/60">
                    {language}
                </span>

                <button
                    type="button"
                    onClick={handleCopy}
                    className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-white/60 transition-colors hover:bg-white/10 hover:text-white"
                >
                    {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
                    {copied ? "Copied" : "Copy"}
                </button>
            </div>

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

// Defined once, outside the component, so ReactMarkdown isn't handed a new
// components object on every render. Tailwind's preflight strips default
// element styling, so every element is styled explicitly (no `prose` plugin).
const components: Components = {
    h1: ({ children }) => (
        <h1 className="mb-4 mt-6 text-2xl font-bold first:mt-0">{children}</h1>
    ),
    h2: ({ children }) => (
        <h2 className="mb-3 mt-5 text-xl font-semibold first:mt-0">{children}</h2>
    ),
    h3: ({ children }) => (
        <h3 className="mb-2 mt-4 text-lg font-semibold first:mt-0">{children}</h3>
    ),
    h4: ({ children }) => (
        <h4 className="mb-2 mt-3 font-semibold first:mt-0">{children}</h4>
    ),
    p: ({ children }) => (
        <p className="mb-4 leading-7 last:mb-0">{children}</p>
    ),
    ul: ({ children }) => (
        <ul className="mb-4 ml-6 list-disc space-y-1">{children}</ul>
    ),
    ol: ({ children }) => (
        <ol className="mb-4 ml-6 list-decimal space-y-1">{children}</ol>
    ),
    li: ({ children }) => <li className="leading-7">{children}</li>,
    a: ({ href, children }) => (
        <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium underline underline-offset-2"
        >
            {children}
        </a>
    ),
    blockquote: ({ children }) => (
        <blockquote className="my-4 border-l-4 border-primary pl-4 italic">
            {children}
        </blockquote>
    ),
    // react-markdown wraps fenced code in <pre>; CodeBlock renders its own.
    pre: ({ children }) => <>{children}</>,
    code: ({ className, children }) => {
        const code = String(children).replace(/\n$/, "")
        const match = /language-(\w+)/.exec(className ?? "")

        if (!match && !code.includes("\n")) {
            return (
                <code className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[0.9em]">
                    {children}
                </code>
            )
        }

        return <CodeBlock language={match?.[1] ?? "text"} code={code} />
    },
    table: ({ children }) => (
        <div className="my-4 overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">{children}</table>
        </div>
    ),
    thead: ({ children }) => <thead className="bg-background/60">{children}</thead>,
    th: ({ children }) => (
        <th className="border-b px-4 py-2 text-left font-semibold">{children}</th>
    ),
    td: ({ children }) => <td className="border-b px-4 py-2">{children}</td>,
    hr: () => <hr className="my-4 border-border" />,
}

const MarkdownContent = ({ content, timestamp }: MarkdownContentProps) => {
    const [copied, setCopied] = useState(false)

    const handleCopy = async () => {
        if (await copyToClipboard(content)) {
            setCopied(true)
            setTimeout(() => setCopied(false), 2000)
        }
    }

    return (
        <div className="flex w-full justify-start">
            <div className="min-w-0 max-w-[85%] rounded-lg bg-muted px-4 py-3">
                <div className="break-words text-sm">
                    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
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
                        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
                    </button>
                </div>
            </div>
        </div>
    )
}

export default MarkdownContent
