"use client"

import Link from "next/link"
import { FileText, Settings } from "lucide-react"

import { SidebarGroup, SidebarGroupLabel } from "@/components/ui/sidebar"
import { useWorkspace } from "@/components/workspace-provider"

interface DocumentsPanelProps {
    isAdmin?: boolean
}

export const DocumentsPanel = ({ isAdmin = false }: DocumentsPanelProps) => {
    const { documents } = useWorkspace()

    return (
        <SidebarGroup className="group-data-[collapsible=icon]:hidden">
            <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5">
                    <FileText className="size-3.5 shrink-0 text-muted-foreground" />
                    <SidebarGroupLabel className="text-sm">Documents</SidebarGroupLabel>
                </div>

                {isAdmin && (
                    <Link
                        href="/admin"
                        className="rounded-md p-1.5"
                        title="Manage documents"
                        aria-label="Manage documents"
                    >
                        <Settings className="size-4" />
                    </Link>
                )}
            </div>

            {documents.length === 0 ? (
                <p className="px-2 py-1.5 text-xs text-muted-foreground">
                    No documents available.
                </p>
            ) : (
                documents.map((doc) => (
                    <div
                        key={doc.id}
                        className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm"
                        title={`${doc.filename} · ${doc.chunk_count} chunks`}
                    >
                        <FileText className="size-4 shrink-0 text-muted-foreground" />

                        <span className="min-w-0 flex-1 truncate">
                            {doc.filename}
                        </span>
                    </div>
                ))
            )}
        </SidebarGroup>
    )
}
