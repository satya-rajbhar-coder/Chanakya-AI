// "use client"

// import { useEffect, useState } from "react"
// import mermaid from "mermaid"

// interface MermaidDiagramProps {
//     chart: string
// }

// export default function MermaidDiagram({ chart }: MermaidDiagramProps) {
//     const [svg, setSvg] = useState("")
//     const [error, setError] = useState(false)

//     useEffect(() => {
//         let cancelled = false

//         const renderDiagram = async () => {
//             if (!chart.trim()) {
//                 return
//             }

//             try {
//                 setError(false)
//                 setSvg("")

//                 const id = `mermaid-${crypto.randomUUID()}`

//                 mermaid.initialize({
//                     startOnLoad: false,
//                     theme: "default",
//                     securityLevel: "strict",
//                 })

//                 const { svg } = await mermaid.render(id, chart)

//                 if (!cancelled) {
//                     setSvg(svg)
//                 }
//             } catch (error) {
//                 console.error(
//                     "Mermaid rendering error:",
//                     error
//                 )

//                 if (!cancelled) {
//                     setError(true)
//                 }
//             }
//         }

//         renderDiagram()

//         return () => {
//             cancelled = true
//         }
//     }, [chart])

//     if (error) {
//         return (
//             <div className="my-4 overflow-hidden rounded-lg border">
//                 <div className="border-b bg-muted px-4 py-2">
//                     <span className="text-xs font-medium text-muted-foreground">
//                         Mermaid
//                     </span>
//                 </div>

//                 <pre className="overflow-x-auto bg-[#282c34] p-4 text-sm text-white/80">
//                     {chart}
//                 </pre>
//             </div>
//         )
//     }

//     return (
//         <div className="my-4 overflow-x-auto rounded-lg border bg-background p-4">
//             {svg ? (
//                 <div
//                     className="flex min-w-fit justify-center"
//                     dangerouslySetInnerHTML={{
//                         __html: svg,
//                     }}
//                 />
//             ) : (
//                 <div className="flex justify-center py-8 text-sm text-muted-foreground">
//                     Rendering diagram...
//                 </div>
//             )}
//         </div>
//     )
// }

"use client"

import { useEffect, useState } from "react"
import mermaid from "mermaid"

interface MermaidDiagramProps {
    chart: string
}

interface MermaidRenderResult {
    svg: string
    error?: string
}


let mermaidInitialized = false

const initializeMermaid = () => {
    if (mermaidInitialized) {
        return
    }

    mermaid.initialize({
        startOnLoad: false,
        theme: "default",
        securityLevel: "strict",
        flowchart: {
            useMaxWidth: true,
            htmlLabels: true,
        },
    })

    mermaidInitialized = true
}


const normalizeMermaid = (chart: string): string => {
    return chart
        .replace(/\r\n/g, "\n")
        .replace(/\r/g, "\n")
        .trim()
}


const sanitizeMermaid = (chart: string): string => {
    let result = normalizeMermaid(chart)

    result = result
        .replace(/^```mermaid\s*/i, "")
        .replace(/^```\s*/i, "")
        .replace(/\s*```$/i, "")
        .trim()

    return result
}


const generateMermaidId = (): string => {
    if (
        typeof crypto !== "undefined" &&
        typeof crypto.randomUUID === "function"
    ) {
        return `mermaid-${crypto.randomUUID()}`
    }

    return `mermaid-${Date.now()}-${Math.random()
        .toString(36)
        .slice(2)}`
}


const renderMermaid = async (
    chart: string
): Promise<MermaidRenderResult> => {
    initializeMermaid()

    const cleanChart = sanitizeMermaid(chart)

    if (!cleanChart) {
        return {
            svg: "",
            error: "Empty Mermaid diagram",
        }
    }

    try {
        const id = generateMermaidId()

        const result = await mermaid.render(
            id,
            cleanChart
        )

        return {
            svg: result.svg,
        }
    } catch (error) {
        console.error(
            "Mermaid rendering error:",
            error
        )

        return {
            svg: "",
            error:
                error instanceof Error
                    ? error.message
                    : "Failed to render Mermaid diagram",
        }
    }
}

export default function MermaidDiagram({
    chart,
}: MermaidDiagramProps) {
    const [svg, setSvg] = useState("")
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        let cancelled = false

        const renderDiagram = async () => {
            setSvg("")
            setError(null)

            if (!chart.trim()) {
                return
            }

            const result = await renderMermaid(chart)

            if (cancelled) {
                return
            }

            if (result.error) {
                setError(result.error)
                return
            }

            setSvg(result.svg)
        }

        renderDiagram()

        return () => {
            cancelled = true
        }
    }, [chart])


    if (error) {
        return (
            <div className="my-4 overflow-hidden rounded-lg border">
                <div className="flex items-center justify-between border-b bg-muted px-4 py-2">
                    <span className="text-xs font-medium text-muted-foreground">
                        Mermaid
                    </span>

                    <span className="text-xs text-destructive">
                        Unable to render diagram
                    </span>
                </div>

                <pre className="overflow-x-auto bg-[#282c34] p-4 text-sm text-white/80">
                    {chart}
                </pre>
            </div>
        )
    }

    /**
     * Rendering successful
     */
    if (svg) {
        return (
            <div className="my-4 overflow-x-auto rounded-lg border bg-background p-4">
                <div
                    className="flex min-w-fit justify-center"
                    dangerouslySetInnerHTML={{
                        __html: svg,
                    }}
                />
            </div>
        )
    }

    /**
     * Loading state
     */
    return (
        <div className="my-4 rounded-lg border bg-background p-6">
            <div className="flex justify-center text-sm text-muted-foreground">
                Rendering diagram...
            </div>
        </div>
    )
}