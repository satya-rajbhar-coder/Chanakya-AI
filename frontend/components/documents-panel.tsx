"use client"

import { useRef } from "react"
import { FileText, Loader2, Plus, Trash2 } from "lucide-react"

import { SidebarGroup, SidebarGroupLabel } from "@/components/ui/sidebar"
import { useWorkspace } from "@/components/workspace-provider"
import { getApiErrorMessage } from "@/services/error"

export const ACCEPTED_FILES = ".pdf,.txt,.md"

export const DocumentsPanel = () => {
    const {
        documents,
        uploadingName,
        uploadError,
        uploadFiles,
        removeDocument,
    } = useWorkspace()

    const inputRef = useRef<HTMLInputElement>(null)
    const uploading = uploadingName !== null

    const handleFiles = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = Array.from(event.target.files ?? [])
        event.target.value = ""

        void uploadFiles(files)
    }

    const handleDelete = async (id: string, filename: string) => {
        if (!window.confirm(`Remove "${filename}" from your documents?`)) {
            return
        }

        try {
            await removeDocument(id)
        } catch (error) {
            window.alert(getApiErrorMessage(error))
        }
    }

    return (
        <SidebarGroup className="group-data-[collapsible=icon]:hidden">
            <div className="flex items-center justify-between">
                <SidebarGroupLabel className="text-sm">Documents</SidebarGroupLabel>

                <input
                    ref={inputRef}
                    type="file"
                    accept={ACCEPTED_FILES}
                    multiple
                    onChange={handleFiles}
                    className="hidden"
                />

                <button
                    type="button"
                    onClick={() => inputRef.current?.click()}
                    disabled={uploading}
                    className="rounded-md p-1.5 hover:bg-accent disabled:opacity-50"
                    title="Upload PDF, TXT or Markdown"
                    aria-label="Upload documents"
                >
                    <Plus className="size-4" />
                </button>
            </div>

            {uploading && (
                <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground">
                    <Loader2 className="size-3.5 shrink-0 animate-spin" />
                    <span className="truncate">Indexing {uploadingName}…</span>
                </div>
            )}

            {uploadError && (
                <p className="px-2 py-1.5 text-xs text-destructive" role="alert">
                    {uploadError}
                </p>
            )}

            {documents.length === 0 && !uploading ? (
                <p className="px-2 py-1.5 text-xs text-muted-foreground">
                    Upload a PDF to ask questions about it.
                </p>
            ) : (
                documents.map((doc) => (
                    <div
                        key={doc.id}
                        className="group/doc flex items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent"
                        title={`${doc.filename} · ${doc.chunk_count} chunks`}
                    >
                        <FileText className="size-4 shrink-0 text-muted-foreground" />

                        <span className="min-w-0 flex-1 truncate">
                            {doc.filename}
                        </span>

                        <button
                            type="button"
                            onClick={() => handleDelete(doc.id, doc.filename)}
                            className="rounded p-1 text-muted-foreground hover:text-destructive md:opacity-0 md:group-hover/doc:opacity-100 focus:opacity-100"
                            aria-label={`Remove ${doc.filename}`}
                        >
                            <Trash2 className="size-3.5" />
                        </button>
                    </div>
                ))
            )}
        </SidebarGroup>
    )
}
