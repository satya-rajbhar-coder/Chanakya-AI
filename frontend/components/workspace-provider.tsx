"use client"

import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
} from "react"

import {
    ConversationResponse,
    deleteConversation,
    getAllConversations,
} from "@/services/conversations"
import {
    DocumentResponse,
    deleteDocument,
    getAllDocuments,
    uploadDocument,
} from "@/services/documents"
import { getApiErrorMessage } from "@/services/error"

/**
 * Shared state for everything that lives outside a single chat: the sidebar's
 * conversation list and the user's indexed documents. Before this, the
 * sidebar fetched conversations once on mount, so a newly created chat never
 * showed up until a full reload.
 */
interface WorkspaceContextValue {
    conversations: ConversationResponse[]
    documents: DocumentResponse[]

    uploadingName: string | null
    uploadError: string | null

    flashError: string | null
    setFlashError: (message: string | null) => void

    refreshConversations: () => Promise<void>
    removeConversation: (id: string) => Promise<void>

    refreshDocuments: () => Promise<void>
    uploadFiles: (files: File[]) => Promise<void>
    removeDocument: (id: string) => Promise<void>
    clearUploadError: () => void
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

export const WorkspaceProvider = ({
    children,
}: {
    children: React.ReactNode
}) => {
    const [conversations, setConversations] = useState<ConversationResponse[]>([])
    const [documents, setDocuments] = useState<DocumentResponse[]>([])
    const [uploadingName, setUploadingName] = useState<string | null>(null)
    const [uploadError, setUploadError] = useState<string | null>(null)
    const [flashError, setFlashError] = useState<string | null>(null)

    const uploadingRef = useRef(false)

    const refreshConversations = useCallback(async () => {
        try {
            setConversations(await getAllConversations())
        } catch (error) {
            console.error(getApiErrorMessage(error))
        }
    }, [])

    const refreshDocuments = useCallback(async () => {
        try {
            setDocuments(await getAllDocuments())
        } catch (error) {
            console.error(getApiErrorMessage(error))
        }
    }, [])

    useEffect(() => {
        void refreshConversations()
        void refreshDocuments()
    }, [refreshConversations, refreshDocuments])

    const removeConversation = useCallback(async (id: string) => {
        await deleteConversation(id)
        setConversations((prev) => prev.filter((c) => c.id !== id))
    }, [])

    const uploadFiles = useCallback(
        async (files: File[]) => {
            if (files.length === 0 || uploadingRef.current) {
                return
            }

            uploadingRef.current = true
            setUploadError(null)

            const errors: string[] = []

            for (const file of files) {
                setUploadingName(file.name)

                try {
                    await uploadDocument(file)
                } catch (error) {
                    errors.push(`${file.name}: ${getApiErrorMessage(error)}`)
                }

                await refreshDocuments()
            }

            setUploadingName(null)
            uploadingRef.current = false

            if (errors.length > 0) {
                setUploadError(errors.join(" "))
            }
        },
        [refreshDocuments]
    )

    const removeDocument = useCallback(async (id: string) => {
        await deleteDocument(id)
        setDocuments((prev) => prev.filter((d) => d.id !== id))
    }, [])

    const clearUploadError = useCallback(() => setUploadError(null), [])

    const value = useMemo<WorkspaceContextValue>(
        () => ({
            conversations,
            documents,
            uploadingName,
            uploadError,
            flashError,
            setFlashError,
            refreshConversations,
            removeConversation,
            refreshDocuments,
            uploadFiles,
            removeDocument,
            clearUploadError,
        }),
        [
            conversations,
            documents,
            uploadingName,
            uploadError,
            flashError,
            refreshConversations,
            removeConversation,
            refreshDocuments,
            uploadFiles,
            removeDocument,
            clearUploadError,
        ]
    )

    return (
        <WorkspaceContext.Provider value={value}>
            {children}
        </WorkspaceContext.Provider>
    )
}

export const useWorkspace = (): WorkspaceContextValue => {
    const context = useContext(WorkspaceContext)

    if (!context) {
        throw new Error("useWorkspace must be used inside <WorkspaceProvider>")
    }

    return context
}
