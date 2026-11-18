"use client"

import type { Components } from "react-markdown"
import { useId } from "react"
import { Hash } from "lucide-react"

import CodeBlock from "./CodeBlock"
import MermaidDiagram from "./MermaidDiagram"
import MathBlock from "./MathBlock"
import InlineMath from "./InlineMath"
import ImageWithZoom from "./ImageWithZoom"

export const markdownComponents: Components = {
    h1: ({ children, ...props }) => {
        const id = useId()
        const headingId = props.id || id
        return (
            <h1 id={headingId} className="mb-4 mt-6 text-2xl font-bold first:mt-0 group relative">
                <a
                    href={`#${headingId}`}
                    className="absolute -left-6 opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground hover:text-primary"
                    aria-label="Link to heading"
                >
                    <Hash className="size-4" />
                </a>
                <span className="pl-2">{children}</span>
            </h1>
        )
    },

    h2: ({ children, ...props }) => {
        const id = useId()
        const headingId = props.id || id
        return (
            <h2 id={headingId} className="mb-3 mt-5 text-xl font-semibold first:mt-0 group relative">
                <a
                    href={`#${headingId}`}
                    className="absolute -left-6 opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground hover:text-primary"
                    aria-label="Link to heading"
                >
                    <Hash className="size-4" />
                </a>
                <span className="pl-2">{children}</span>
            </h2>
        )
    },

    h3: ({ children, ...props }) => {
        const id = useId()
        const headingId = props.id || id
        return (
            <h3 id={headingId} className="mb-2 mt-4 text-lg font-semibold first:mt-0 group relative">
                <a
                    href={`#${headingId}`}
                    className="absolute -left-6 opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground hover:text-primary"
                    aria-label="Link to heading"
                >
                    <Hash className="size-4" />
                </a>
                <span className="pl-2">{children}</span>
            </h3>
        )
    },

    h4: ({ children, ...props }) => {
        const id = useId()
        const headingId = props.id || id
        return (
            <h4 id={headingId} className="mb-2 mt-3 font-semibold first:mt-0 group relative">
                <a
                    href={`#${headingId}`}
                    className="absolute -left-6 opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground hover:text-primary"
                    aria-label="Link to heading"
                >
                    <Hash className="size-4" />
                </a>
                <span className="pl-2">{children}</span>
            </h4>
        )
    },

    h5: ({ children, ...props }) => {
        const id = useId()
        const headingId = props.id || id
        return (
            <h5 id={headingId} className="mb-2 mt-3 font-semibold first:mt-0 group relative">
                <a
                    href={`#${headingId}`}
                    className="absolute -left-6 opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground hover:text-primary"
                    aria-label="Link to heading"
                >
                    <Hash className="size-4" />
                </a>
                <span className="pl-2">{children}</span>
            </h5>
        )
    },

    h6: ({ children, ...props }) => {
        const id = useId()
        const headingId = props.id || id
        return (
            <h6 id={headingId} className="mb-2 mt-3 font-semibold first:mt-0 group relative">
                <a
                    href={`#${headingId}`}
                    className="absolute -left-6 opacity-0 transition-opacity group-hover:opacity-100 text-muted-foreground hover:text-primary"
                    aria-label="Link to heading"
                >
                    <Hash className="size-4" />
                </a>
                <span className="pl-2">{children}</span>
            </h6>
        )
    },

    p: ({ children }) => (
        <p className="mb-4 leading-7 last:mb-0">
            {children}
        </p>
    ),

    ul: ({ children }) => (
        <ul className="mb-4 ml-6 list-disc space-y-1">
            {children}
        </ul>
    ),

    ol: ({ children }) => (
        <ol className="mb-4 ml-6 list-decimal space-y-1">
            {children}
        </ol>
    ),

    li: ({ children }) => (
        <li className="leading-7">
            {children}
        </li>
    ),

    a: ({ href, children, ...props }) => (
        <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="font-medium underline underline-offset-2 text-primary hover:text-primary/80 transition-colors"
            {...props}
        >
            {children}
        </a>
    ),

    blockquote: ({ children }) => (
        <blockquote className="my-4 border-l-4 border-primary pl-4 italic text-muted-foreground">
            {children}
        </blockquote>
    ),

    pre: ({ children }) => (<>{children}</>),

    code: ({ className, children, ...props }) => {
        const code = String(children).replace(
            /\n$/,
            ""
        )

        const match = /language-([\w-]+)/.exec(
            className ?? ""
        )

        const language = match?.[1]?.toLowerCase()

        /* Mermaid */
        if (language === "mermaid") {
            return (
                <MermaidDiagram
                    chart={code}
                />
            )
        }

        /* Math blocks */
        if (language === "math" || language === "latex" || language === "katex") {
            return <MathBlock math={code} />
        }

        if (!match && !code.includes("\n")) {
            return (
                <code className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[0.9em] border border-border/50" {...props}>
                    {children}
                </code>
            )
        }

        return (
            <CodeBlock
                language={language ?? "text"}
                code={code}
            />
        )
    },

    table: ({ children }) => (
        <div className="my-4 overflow-x-auto rounded-lg border">
            <table className="w-full text-sm border-collapse">
                {children}
            </table>
        </div>
    ),

    thead: ({ children }) => (
        <thead className="bg-muted/50">
            {children}
        </thead>
    ),

    th: ({ children }) => (
        <th className="border border-border/50 px-4 py-2 text-left font-semibold whitespace-nowrap">
            {children}
        </th>
    ),

    td: ({ children }) => (
        <td className="border border-border/50 px-4 py-2 whitespace-nowrap">
            {children}
        </td>
    ),

    tr: ({ children }) => (
        <tr className="hover:bg-muted/50 transition-colors">
            {children}
        </tr>
    ),

    hr: () => (
        <hr className="my-6 border-border" />
    ),

    br: () => <br />,

    // Image with zoom
    img: ({ src, alt, title, ...props }) => (
            <ImageWithZoom src={src as string} alt={alt} title={title} {...props} />
    ),
}