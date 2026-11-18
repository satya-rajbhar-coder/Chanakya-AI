"use client"

import { useState, useEffect } from "react"
import { Check, Copy, Minimize, Maximize } from "lucide-react"

import { copyToClipboard } from "./markdown-utils"
import { Button } from "@/components/ui/button"

interface CodeBlockProps {
    language: string
    code: string
}

const LANGUAGE_LABELS: Record<string, string> = {
    js: "JavaScript",
    ts: "TypeScript",
    jsx: "JavaScript (JSX)",
    tsx: "TypeScript (TSX)",
    py: "Python",
    rs: "Rust",
    go: "Go",
    java: "Java",
    cpp: "C++",
    c: "C",
    cs: "C#",
    php: "PHP",
    rb: "Ruby",
    swift: "Swift",
    kt: "Kotlin",
    scala: "Scala",
    clj: "Clojure",
    hs: "Haskell",
    ml: "OCaml",
    fs: "F#",
    vb: "Visual Basic",
    sql: "SQL",
    sh: "Shell",
    bash: "Bash",
    zsh: "Zsh",
    fish: "Fish",
    ps1: "PowerShell",
    bat: "Batch",
    cmd: "Command Prompt",
    dockerfile: "Dockerfile",
    yaml: "YAML",
    yml: "YAML",
    json: "JSON",
    xml: "XML",
    html: "HTML",
    css: "CSS",
    scss: "SCSS",
    sass: "Sass",
    less: "Less",
    md: "Markdown",
    mdx: "MDX",
    txt: "Text",
    toml: "TOML",
    ini: "INI",
    cfg: "Config",
    conf: "Config",
    properties: "Properties",
    env: "Environment",
    gitignore: "Git Ignore",
    dockerignore: "Docker Ignore",
    makefile: "Makefile",
    cmake: "CMake",
    gradle: "Gradle",
    maven: "Maven",
    sbt: "SBT",
    proto: "Protocol Buffers",
    graphql: "GraphQL",
    gql: "GraphQL",
    vim: "Vim Script",
    lua: "Lua",
    r: "R",
    m: "MATLAB",
    julia: "Julia",
    perl: "Perl",
    pl: "Perl",
    pm: "Perl Module",
    tcl: "Tcl",
    expect: "Expect",
    awk: "AWK",
    sed: "Stream Editor",
}

export default function CodeBlock({ language, code }: CodeBlockProps) {
    const [copied, setCopied] = useState(false)
    const [expanded, setExpanded] = useState(false)
    const [highlightedCode, setHighlightedCode] = useState<string | null>(null)
    const [isHighlighting, setIsHighlighting] = useState(true)

    const displayLanguage = LANGUAGE_LABELS[language.toLowerCase()] || language

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

    const handleExpand = () => {
        setExpanded(!expanded)
    }

    // Syntax highlighting with shiki
    useEffect(() => {
        let cancelled = false

        const highlight = async () => {
            try {
                // Dynamic import to avoid SSR issues
                const { codeToHtml } = await import("shiki")

                const html = await codeToHtml(code, {
                    lang: language,
                    theme: "github-light",
                })

                if (!cancelled) {
                    setHighlightedCode(html)
                    setIsHighlighting(false)
                }
            } catch (error) {
                console.warn("Syntax highlighting failed:", error)
                if (!cancelled) {
                    setIsHighlighting(false)
                }
            }
        }

        highlight()

        return () => {
            cancelled = true
        }
    }, [code, language])

    // If highlighting failed or not ready, show plain code
    if (isHighlighting || !highlightedCode) {
        return (
            <div className="my-4 overflow-hidden rounded-lg border bg-muted/50">
                <div className="flex items-center justify-between border-b px-4 py-2">
                    <span className="text-xs font-medium text-muted-foreground">
                        {displayLanguage}
                    </span>
                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleCopy}
                            className="size-7 text-muted-foreground"
                            aria-label={copied ? "Copied" : "Copy code"}
                        >
                            {copied ? (
                                <Check className="size-3.5 text-emerald-500" />
                            ) : (
                                <Copy className="size-3.5" />
                            )}
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={handleExpand}
                            className="size-7 text-muted-foreground"
                            aria-label={expanded ? "Collapse" : "Expand"}
                        >
                            {expanded ? <Minimize className="size-3.5" /> : <Maximize className="size-3.5" />}
                        </Button>
                    </div>
                </div>
                <pre className="overflow-x-auto p-4 text-sm leading-relaxed" style={{ maxHeight: expanded ? "none" : "500px" }}>
                    <code className="font-mono text-sm">{code}</code>
                </pre>
            </div>
        )
    }

    return (
        <div className="my-4 overflow-hidden rounded-lg border bg-muted/50">
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-2">
                <span className="text-xs font-medium text-muted-foreground">
                    {displayLanguage}
                </span>

                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={handleCopy}
                        className="size-7 text-muted-foreground"
                        aria-label={copied ? "Copied" : "Copy code"}
                    >
                        {copied ? (
                            <Check className="size-3.5 text-emerald-500" />
                        ) : (
                            <Copy className="size-3.5" />
                        )}
                    </Button>

                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={handleExpand}
                        className="size-7 text-muted-foreground"
                        aria-label={expanded ? "Collapse" : "Expand"}
                    >
                        {expanded ? <Minimize className="size-3.5" /> : <Maximize className="size-3.5" />}
                    </Button>
                </div>
            </div>

            {/* Code with syntax highlighting */}
            <div
                className="overflow-x-auto p-4 text-sm leading-relaxed"
                style={{ maxHeight: expanded ? "none" : "500px" }}
            >
                <pre className="shiki github-light" dangerouslySetInnerHTML={{ __html: highlightedCode }} />
            </div>
        </div>
    )
}