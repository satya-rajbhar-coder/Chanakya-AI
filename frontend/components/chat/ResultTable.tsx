"use client"

import { useState, useMemo, useEffect } from "react"
import { 
  Bookmark, ChevronLeft, ChevronRight, Code2, Download, Loader2, Database, 
  Copy, Check, Table, BarChart2, Search, Filter, Eye, EyeOff, Expand, Shrink,
  AlertCircle, X
} from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

import {
    AnalysisResponse,
    ResultPage,
    MultiClientResult,
    errorMessage,
    fetchRows,
    saveAnalysis,
} from "@/services/analysis"
import { copyToClipboard } from "../markdown/markdown-utils"

const format = (value: unknown): string => {
    if (value === null || value === undefined) return "∅"
    if (typeof value === "object") return JSON.stringify(value)
    return String(value)
}

interface ResultTableProps {
    data: AnalysisResponse
    question: string
    onSaved?: () => void
}

// Column Filter Component
const ColumnFilter = ({ 
    columns, 
    visibleColumns, 
    onToggleColumn 
}: { 
    columns: string[]
    visibleColumns: Set<string>
    onToggleColumn: (col: string) => void
}) => (
    <Tooltip>
        <TooltipTrigger>
            <Button variant="ghost" size="sm" className="gap-1">
                <Filter className="h-4 w-4" />
                <span className="hidden sm:inline">{visibleColumns.size}/{columns.length}</span>
            </Button>
        </TooltipTrigger>
        <TooltipContent side="bottom" align="end" className="tooltip-premium w-64 p-2">
            <div className="space-y-1 max-h-64 overflow-auto">
                {columns.map((col) => (
                    <label key={col} className="flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-accent cursor-pointer">
                        <input
                            type="checkbox"
                            checked={visibleColumns.has(col)}
                            onChange={() => onToggleColumn(col)}
                            className="h-4 w-4 rounded border-input"
                        />
                        <span className="text-sm truncate">{col}</span>
                    </label>
                ))}
            </div>
        </TooltipContent>
    </Tooltip>
)

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
                            className="whitespace-nowrap border-b border-border px-3 py-2.5 text-left font-medium text-xs uppercase tracking-wide text-muted-foreground bg-muted/50 sticky top-0"
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
    expandedRows, 
    toggleRow,
    format 
}: {
    displayColumns: string[]
    allColumns: string[]
    filteredRows: unknown[][]
    expandedRows: Set<number>
    toggleRow: (index: number) => void
    format: (value: unknown) => string
}) {
    return (
        <tbody>
            {filteredRows.length === 0 ? (
                <tr>
                    <td colSpan={displayColumns.length} className="p-8 text-center">
                        <div className="flex flex-col items-center gap-2 text-muted-foreground">
                            <Table className="h-10 w-10 text-muted-foreground/30" />
                            <span className="text-sm">No rows returned</span>
                        </div>
                    </td>
                </tr>
            ) : (
                filteredRows.map((row, i) => (
                    <tr
                        key={i}
                        className="hover:bg-accent/30 transition-colors cursor-pointer"
                        onClick={() => toggleRow(i)}
                    >
                        {displayColumns.map((column, j) => {
                            const cellIndex = allColumns.indexOf(column)
                            const cell = row[cellIndex]
                            const isExpanded = expandedRows.has(i)
                            return (
                                <td
                                    key={j}
                                    className={cn(
                                        "whitespace-nowrap border-b border-border/50 px-3 py-2 text-sm transition-colors",
                                        isExpanded && "bg-accent/50"
                                    )}
                                >
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

const ResultTable = ({ data, question, onSaved }: ResultTableProps) => {
    const [result, setResult] = useState<ResultPage>(data.result)
    const [loading, setLoading] = useState(false)
    const [showSql, setShowSql] = useState(false)
    const [saved, setSaved] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [activeDb, setActiveDb] = useState<string>("all")
    const [searchQuery, setSearchQuery] = useState("")
    const [visibleColumns, setVisibleColumns] = useState<Set<string>>(new Set())
    const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())

    const multiResult = data.multi_result as MultiClientResult | undefined

    // Initialize visible columns
    useEffect(() => {
        const displayColumns = multiResult?.merged_result?.columns ?? result.columns
        if (visibleColumns.size === 0) {
            setVisibleColumns(new Set(displayColumns))
        }
    }, [data, multiResult])

    const goTo = async (page: number) => {
        setLoading(true)
        setError(null)
        try {
            setResult(await fetchRows(data.token, page, result.page_size))
        } catch (err) {
            setError(errorMessage(err))
        } finally {
            setLoading(false)
        }
    }

    const download = async () => {
        setError(null)
        try {
            // Export exactly what is displayed (already de-duplicated and filtered),
            // so the CSV matches the on-screen result instead of the raw UNION ALL.
            const escape = (value: unknown) => {
                const s = value === null || value === undefined ? "" : String(value)
                return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
            }

            const indices = displayColumns.map((c) => allColumns.indexOf(c))
            const lines = [
                displayColumns.map(escape).join(","),
                ...filteredRows.map((row) => indices.map((i) => escape(row[i])).join(",")),
            ]

            const blob = new Blob(["\uFEFF" + lines.join("\r\n")], {
                type: "text/csv;charset=utf-8",
            })
            const url = URL.createObjectURL(blob)
            const link = document.createElement("a")
            link.href = url
            link.download = (data.title || "result") + ".csv"
            link.click()
            URL.revokeObjectURL(url)
        } catch (err) {
            setError(errorMessage(err))
        }
    }

    const save = async () => {
        setError(null)
        try {
            await saveAnalysis(data.token, question, data.title)
            setSaved(true)
            onSaved?.()
        } catch (err) {
            setError(errorMessage(err))
        }
    }

    const [sqlCopied, setSqlCopied] = useState(false)

    const copySql = async () => {
        const success = await copyToClipboard(data.sql)

        if (success) {
            setSqlCopied(true)
            setTimeout(() => setSqlCopied(false), 2000)
        } else {
            setError("Could not copy to clipboard")
        }
    }

    const toggleColumn = (col: string) => {
        setVisibleColumns(prev => {
            const next = new Set(prev)
            if (next.has(col)) next.delete(col)
            else next.add(col)
            return next
        })
    }

    const toggleRow = (index: number) => {
        setExpandedRows(prev => {
            const next = new Set(prev)
            if (next.has(index)) next.delete(index)
            else next.add(index)
            return next
        })
    }

    const start = multiResult ? 0 : result.page * result.page_size
    const canPaginate = !multiResult

    const clientEntries = multiResult ? Object.entries(multiResult.clients) : []
    const hasMerged = Boolean(multiResult?.merged_result)

    // Columns for the active view
    const allColumns = multiResult
        ? (activeDb !== "all" && multiResult.clients[activeDb]
            ? multiResult.clients[activeDb].columns
            : (multiResult.merged_result?.columns ?? clientEntries[0]?.[1].columns ?? []))
        : result.columns
    const displayColumns = allColumns.filter(c => visibleColumns.has(c))

    // Base rows for the active view:
    // - "all" tab: server-merged rows when available, otherwise combine every client's rows
    // - per-client tab: that client's rows
    const baseRows: unknown[][] = multiResult
        ? (activeDb !== "all" && multiResult.clients[activeDb]
            ? multiResult.clients[activeDb].rows
            : (multiResult.merged_result?.rows ?? clientEntries.flatMap(([, rp]) => rp.rows)))
        : result.rows

    // Global queries UNION ALL the same query against every assigned database,
    // so identical rows show up duplicated. Collapse exact duplicates in all
    // multi-client views.
    const displayRows = multiResult
        ? baseRows.filter((row, i) =>
            baseRows.findIndex((r) => JSON.stringify(r) === JSON.stringify(row)) === i
        )
        : baseRows
    const dedupedCount = multiResult ? baseRows.length - displayRows.length : 0

    // Filter rows by search query
    const filteredRows = displayRows.filter(row => 
        row.some(cell => 
            String(cell).toLowerCase().includes(searchQuery.toLowerCase())
        )
    )

    return (
        <TooltipProvider>
            <div className="w-full rounded-2xl border border-border/50 bg-card shadow-sm overflow-hidden">
                {/* Header */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/50 px-4 py-3">
                    <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold">{data.title}</p>
                    </div>

                    <div className="flex items-center gap-2">
                        {/* Search */}
                        <div className="relative hidden sm:block">
                            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground/50" />
                            <Input
                                type="search"
                                placeholder="Filter rows..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                className="h-9 w-56 pl-8 pr-3 text-xs"
                            />
                        </div>

                        {/* Column Filter */}
                        <ColumnFilter
                            columns={allColumns}
                            visibleColumns={visibleColumns}
                            onToggleColumn={toggleColumn}
                        />

                        {/* Actions */}
                        <Tooltip>
                            <TooltipTrigger>
                                <Button 
                                    variant="ghost" 
                                    size="sm" 
                                    onClick={() => setShowSql(!showSql)}
                                    className="gap-1"
                                >
                                    <Code2 className="h-4 w-4" />
                                    <span className="hidden sm:inline">SQL</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="bottom">View SQL query</TooltipContent>
                        </Tooltip>

                        <Tooltip>
                            <TooltipTrigger>
                                <Button variant="ghost" size="sm" onClick={download} className="gap-1">
                                    <Download className="h-4 w-4" />
                                    <span className="hidden sm:inline">CSV</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="bottom">Download as CSV</TooltipContent>
                        </Tooltip>

                        <Tooltip>
                            <TooltipTrigger>
                                <Button 
                                    variant={saved ? "default" : "ghost"} 
                                    size="sm" 
                                    onClick={save} 
                                    disabled={saved}
                                    className="gap-1"
                                >
                                    <Bookmark className="h-4 w-4" />
                                    <span className="hidden sm:inline">{saved ? "Saved" : "Save"}</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="bottom">Save this analysis</TooltipContent>
                        </Tooltip>
                    </div>
                </div>

                {/* SQL Display */}
                {showSql && (
                    <div className="border-b border-border/50 overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-2 bg-muted/50">
                            <span className="text-xs font-medium text-muted-foreground">Generated SQL</span>
                            <Tooltip>
                                <TooltipTrigger>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={copySql}
                                        className="size-7"
                                        aria-label={sqlCopied ? "Copied" : "Copy SQL"}
                                    >
                                        {sqlCopied ? (
                                            <Check className="size-3.5 text-emerald-500" />
                                        ) : (
                                            <Copy className="size-3.5" />
                                        )}
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="bottom">{sqlCopied ? "Copied" : "Copy SQL"}</TooltipContent>
                            </Tooltip>
                        </div>
                        <pre className="max-h-40 overflow-auto p-4 text-xs font-mono bg-muted/30"><code>{data.sql}</code></pre>
                    </div>
                )}

                {/* Multi-Client Tabs */}
                {multiResult && (
                    <div className="border-b border-border/50 px-3 py-2">
                        <Tabs value={activeDb} onValueChange={setActiveDb}>
                            <TabsList className="h-8 w-fit gap-1 p-0.5">
                                <TabsTrigger value="all" className="h-7 gap-1 px-3 text-xs">
                                    <Table className="size-3" />
                                    {hasMerged ? "Merged" : "All clients"}
                                    <span className="text-muted-foreground">({displayRows.length})</span>
                                </TabsTrigger>
                                {clientEntries.map(([db, dbResult]) => (
                                    <TabsTrigger key={db} value={db} className="h-7 gap-1 px-3 text-xs">
                                        <Database className="size-3" />
                                        {db}
                                        <span className="text-muted-foreground">({dbResult.rows.length})</span>
                                    </TabsTrigger>
                                ))}
                            </TabsList>
                        </Tabs>
                    </div>
                )}

                {/* Data Table */}
                <div className="relative">
                    <div className="max-h-[65vh] overflow-auto">
                        <table className="w-full text-sm table-premium">
                            <TableHeader 
                                displayColumns={displayColumns} 
                            />
                            <TableBody
                                displayColumns={displayColumns}
                                allColumns={allColumns}
                                filteredRows={filteredRows}
                                expandedRows={expandedRows}
                                toggleRow={toggleRow}
                                format={format}
                            />
                        </table>
                    </div>

                    {/* Empty state overlay for search */}
                    {searchQuery && filteredRows.length === 0 && displayRows.length > 0 && (
                        <div className="absolute inset-0 flex items-center justify-center bg-background/95 z-20">
                            <div className="flex flex-col items-center gap-2 text-muted-foreground">
                                <Search className="size-6" />
                                <span className="text-sm">No matches for "{searchQuery}"</span>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/50 px-4 py-3 text-xs text-muted-foreground">
                    <div className="flex items-center gap-3">
                        <span className="whitespace-nowrap">
                            {filteredRows.length > 0
                                ? "Showing " + String(Math.min(start + 1, start + filteredRows.length)) + "–" + String(start + filteredRows.length) + (canPaginate && result.has_more ? " of many" : "")
                                : "0 rows"}
                            {dedupedCount > 0 && ` · ${dedupedCount} identical row${dedupedCount === 1 ? "" : "s"} collapsed`}
                            {multiResult && activeDb !== "all" && <span className="ml-2 font-mono text-foreground/70">{activeDb}</span>}
                        </span>

                        {searchQuery && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 gap-1 px-2 text-xs text-muted-foreground"
                                onClick={() => setSearchQuery("")}
                            >
                                <X className="size-3" />
                                Clear filter
                            </Button>
                        )}
                    </div>

                    <div className="flex items-center gap-1">
                        {loading && <Loader2 className="size-4 animate-spin text-primary" />}
                        {canPaginate && (
                            <>
                                <span className="mr-1 whitespace-nowrap">Rows</span>
                                <Select value={result.page_size.toString()} onValueChange={async (v) => {
                                    setResult(await fetchRows(data.token, 0, parseInt(v)))
                                }}>
                                    <SelectTrigger className="h-8 w-[72px] whitespace-nowrap">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="25">25</SelectItem>
                                        <SelectItem value="50">50</SelectItem>
                                        <SelectItem value="100">100</SelectItem>
                                        <SelectItem value="200">200</SelectItem>
                                    </SelectContent>
                                </Select>
                            </>
                        )}

                        <Button
                            size="icon"
                            variant="ghost"
                            className="size-8"
                            disabled={loading || !canPaginate || result.page === 0}
                            onClick={() => goTo(result.page - 1)}
                            aria-label="Previous page"
                        >
                            <ChevronLeft className="size-4" />
                        </Button>
                        <Button
                            size="icon"
                            variant="ghost"
                            className="size-8"
                            disabled={loading || !canPaginate || !result.has_more}
                            onClick={() => goTo(result.page + 1)}
                            aria-label="Next page"
                        >
                            <ChevronRight className="size-4" />
                        </Button>
                    </div>
                </div>

                {error && (
                    <p role="alert" className="px-4 pb-3 text-xs text-destructive flex items-center gap-2">
                        <AlertCircle className="h-4 w-4 shrink-0" />
                        {error}
                    </p>
                )}
            </div>
        </TooltipProvider>
    )
}

export default ResultTable