"use client"

import { renderToString } from "katex"

interface InlineMathProps {
    math: string
}

export default function InlineMath({ math }: InlineMathProps) {
    let rendered: string
    let error: string | null = null

    try {
        rendered = renderToString(math, {
            displayMode: false,
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
            <span className="font-mono text-sm text-destructive" title={`Render error: ${error}`}>
                {math}
            </span>
        )
    }

    return <span dangerouslySetInnerHTML={{ __html: rendered }} className="inline" />
}