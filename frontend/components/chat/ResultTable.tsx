"use client"

import { useState } from "react"
import {
    Code2, Download, Loader2, Copy, Check, Table, Search, AlertCircle, X, Sparkles
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

import {
    AnalysisResponse,
    errorMessage,
    exportCsv,
} from "@/services/analysis"
import { copyToClipboard } from "../markdown/markdown-utils"

const format = (value: unknown): string => {
    if (value === null || value === undefined) return "∅"
    if (typeof value === "object") return JSON.stringify(value)
    return String(value)
}

interface ResultTableProps {
    data: AnalysisResponse
    question?: string
    refreshedAt?: string
}

// Table Header Component
function TableHeader({
    displayColumns
}: {
    displayColumns: string[]
}) {
    return (
        <thead className="sticky top-0 z-10">
            <tr>
                {displayColumns.map((column) => {
                    return (
                        <th
                            key={column}
                            className="whitespace-nowrap border-b border-border/50 px-3 py-2.5 text-left font-medium text-xs uppercase tracking-wide text-muted-foreground bg-muted/30 sticky top-0"
                        >
                            {column}
                        </th>
                    )
                })}
            </tr>
        </thead>
    )
}

// Table Body Component
function TableBody({
    displayColumns,
    allColumns,
    filteredRows,
    format
}: {
    displayColumns: string[]
    allColumns: string[]
    filteredRows: unknown[][]
    format: (value: unknown) => string
}) {
    return (
        <tbody>
            {filteredRows.length === 0 ? (
                <tr>
                    <td colSpan={displayColumns.length} className="p-8 text-center">
                        <div className="flex flex-col items-center gap-3 text-muted-foreground">
                            <div className="p-2 rounded-full bg-muted/50 text-muted-foreground/50">
                                <Table className="h-8 w-8" />
                            </div>
                            <span className="text-sm font-medium">No rows returned</span>
                        </div>
                    </td>
                </tr>
            ) : (
                filteredRows.map((row, i) => (
                    <tr key={i} className="whitespace-nowrap border-b border-border/50 px-3 py-2.5 text-sm hover:bg-muted/30 transition-colors">
                        {displayColumns.map((column, j) => {
                            const cellIndex = allColumns.indexOf(column)
                            const cell = row[cellIndex]
                            return (
                                <td key={j} className="whitespace-nowrap border-b border-border/50 px-3 py-2.5 text-sm">
                                    <span className="font-mono text-muted-foreground/70">{format(cell)}</span>
                                </td>
                            )
                        })}
                    </tr>
                ))
            )}
        </tbody>
    )
}

const ResultTable = ({ data, question, refreshedAt }: ResultTableProps) => {
    const result = data.result
    const [showSql, setShowSql] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [downloadLoading, setDownloadLoading] = useState(false)
    const [searchQuery, setSearchQuery] = useState("")
    const [visibleRowCount, setVisibleRowCount] = useState(100)
    const [sqlCopied, setSqlCopied] = useState(false)

    const allColumns = result.columns
    const displayColumns = allColumns

    const filteredRows = result.rows.filter(row =>
        row.some(cell =>
            String(cell).toLowerCase().includes(searchQuery.toLowerCase())
        )
    )
    const displayedRows = filteredRows.slice(0, visibleRowCount)

    const copySql = async () => {
        const success = await copyToClipboard(data.sql)

        if (success) {
            setSqlCopied(true)
            setTimeout(() => setSqlCopied(false), 2000)
        } else {
            setError("Could not copy to clipboard")
        }
    }

    const download = async () => {
        setDownloadLoading(true)
        setError(null)
        try {
            const blob = await exportCsv(data.token)
            const url = URL.createObjectURL(blob)
            const link = document.createElement("a")
            link.href = url
            link.download = (data.title || "result") + ".csv"
            link.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            setError(errorMessage(err))
        } finally {
            setDownloadLoading(false)
        }
    }

    return (
        <div
            role="region"
            aria-label={question ? `Database results for: ${question}` : undefined}
            className="w-full rounded-2xl border border-border/50 bg-card shadow-sm overflow-hidden flex flex-col"
        >
            {/* Header */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/50 px-4 py-3 bg-muted/30">
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <Sparkles className="size-3.5 text-primary" />
                        <p className="truncate text-sm font-semibold text-foreground">{data.title}</p>
                    </div>
                    {refreshedAt && (
                        <p className="text-xs text-muted-foreground">
                            Database results refreshed {new Date(refreshedAt).toLocaleTimeString()}
                        </p>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <div className="relative hidden sm:block">
                        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                        <Input
                            type="search"
                            placeholder="Filter rows..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="h-9 w-56 pl-8 pr-3 text-xs border-border/50 focus:border-primary"
                        />
                    </div>

                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setShowSql(!showSql)}
                        className="gap-2 bg-background hover:bg-primary/5 hover:text-primary border-border"
                        title="View SQL query"
                    >
                        <Code2 className="h-4 w-4" />
                        <span className="hidden sm:inline font-medium text-sm">SQL</span>
                    </Button>

                    <Button
                        variant="outline"
                        size="sm"
                        onClick={download}
                        disabled={downloadLoading}
                        className="gap-2 bg-background hover:bg-primary/5 hover:text-primary border-border"
                        title="Download as CSV"
                    >
                        {downloadLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Download className="h-4 w-4" />
                        )}
                        <span className="hidden sm:inline font-medium text-sm">CSV</span>
                    </Button>
                </div>
            </div>

            {/* SQL Display */}
            {showSql && (
                <div className="border-b border-border/50 overflow-hidden bg-muted/20">
                    <div className="flex items-center justify-between px-4 py-2.5">
                        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Generated SQL</span>
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={copySql}
                            className="size-8 hover:bg-primary/10"
                            title={sqlCopied ? "Copied" : "Copy SQL"}
                        >
                            {sqlCopied ? (
                                <Check className="size-3.5 text-emerald-500" />
                            ) : (
                                <Copy className="size-3.5" />
                            )}
                        </Button>
                    </div>
                    <pre className="max-h-48 overflow-auto p-4 text-xs font-mono bg-muted/50 border border-border/50 rounded-lg"><code className="text-foreground">{data.sql}</code></pre>
                </div>
            )}

            {/* Data Table */}
            <div className="relative flex-1 min-h-0">
                <div className="max-h-[65vh] overflow-auto">
                    <table className="w-full text-sm">
                        <TableHeader
                            displayColumns={displayColumns}
                        />
                        <TableBody
                            displayColumns={displayColumns}
                            allColumns={allColumns}
                            filteredRows={displayedRows}
                            format={format}
                        />
                    </table>
                </div>

                {searchQuery && filteredRows.length === 0 && result.rows.length > 0 && (
                    <div className="absolute inset-0 flex items-center justify-center bg-background/95 z-20">
                        <div className="flex flex-col items-center gap-3 text-muted-foreground">
                            <Search className="size-6" />
                            <span className="text-sm font-medium">No matches for: &quot;{searchQuery}&quot;</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/50 px-4 py-3 text-xs text-muted-foreground bg-muted/30">
                <div className="flex items-center gap-3">
                    <span className="whitespace-nowrap font-medium text-foreground">
                        Showing {displayedRows.length} of {filteredRows.length} matching rows
                    </span>
                </div>

                <div className="flex items-center gap-2">
                    {displayedRows.length < filteredRows.length && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-7"
                            onClick={() => setVisibleRowCount((count) => count + 100)}
                        >
                            Load more rows
                        </Button>
                    )}
                    {searchQuery && (
                        <Button
                            variant="outline"
                            size="sm"
                            className="h-6 gap-1 px-2 text-xs border-border"
                            onClick={() => setSearchQuery("")}
                        >
                            <X className="size-3" />
                            Clear filter
                        </Button>
                    )}
                </div>
            </div>

            {error && (
                <p role="alert" className="px-4 pb-3 text-xs text-destructive flex items-center gap-2 bg-destructive/5 border-b border-destructive/10">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                </p>
            )}
        </div>
    )
}

export default ResultTable
