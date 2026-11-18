"use client"

import { renderToString } from "katex"

interface MathBlockProps {
    math: string
}

export default function MathBlock({ math }: MathBlockProps) {
    let rendered: string
    let error: string | null = null

    try {
        rendered = renderToString(math, {
            displayMode: true,
            throwOnError: false,
            strict: false,
            trust: true,
        })
    } catch (err) {
        rendered = ""
        error = err instanceof Error ? err.message : "Failed to render math"
    }

    if (error) {
        return (
            <div className="my-4 overflow-x-auto rounded-lg border bg-destructive/10 p-4 text-sm text-destructive font-mono">
                {math}
                <div className="mt-2 text-xs opacity-70">Render error: {error}</div>
            </div>
        )
    }

    return (
        <div className="my-4 overflow-x-auto text-center" dangerouslySetInnerHTML={{ __html: rendered }} />
    )
}