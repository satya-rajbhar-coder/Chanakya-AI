"use client"

import type { Components } from "react-markdown"

import CodeBlock from "./CodeBlock"
import MermaidDiagram from "./MermaidDiagram"

export const markdownComponents: Components = {
    h1: ({ children }) => (
        <h1 className="mb-4 mt-6 text-2xl font-bold first:mt-0">
            {children}
        </h1>
    ),

    h2: ({ children }) => (
        <h2 className="mb-3 mt-5 text-xl font-semibold first:mt-0">
            {children}
        </h2>
    ),

    h3: ({ children }) => (
        <h3 className="mb-2 mt-4 text-lg font-semibold first:mt-0">
            {children}
        </h3>
    ),

    h4: ({ children }) => (
        <h4 className="mb-2 mt-3 font-semibold first:mt-0">
            {children}
        </h4>
    ),

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

    pre: ({ children }) => (<>{children}</>),

    code: ({ className, children }) => {
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

        if (!match && !code.includes("\n")) {
            return (
                <code className="rounded bg-background/70 px-1.5 py-0.5 font-mono text-[0.9em]">
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
            <table className="w-full text-sm">
                {children}
            </table>
        </div>
    ),

    thead: ({ children }) => (
        <thead className="bg-background/60">
            {children}
        </thead>
    ),

    th: ({ children }) => (
        <th className="border-b px-4 py-2 text-left font-semibold">
            {children}
        </th>
    ),

    td: ({ children }) => (
        <td className="border-b px-4 py-2">
            {children}
        </td>
    ),

    hr: () => (
        <hr className="my-4 border-border" />
    ),

    br: () => <br />,
}