"use client"

import React, {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
} from "react"

import {
    ConversationResponse,
    deleteConversation,
    getAllConversations,
} from "@/services/conversations"
import { DocumentResponse, getAllDocuments } from "@/services/documents"
import { getApiErrorMessage } from "@/services/error"

interface WorkspaceContextValue {
    conversations: ConversationResponse[]
    documents: DocumentResponse[]

    flashError: string | null
    setFlashError: (message: string | null) => void

    refreshConversations: () => Promise<void>
    removeConversation: (id: string) => Promise<void>

    refreshDocuments: () => Promise<void>
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

export const WorkspaceProvider = ({
    children,
}: {
    children: React.ReactNode
}) => {
    const [conversations, setConversations] = useState<ConversationResponse[]>([])
    const [documents, setDocuments] = useState<DocumentResponse[]>([])
    const [flashError, setFlashError] = useState<string | null>(null)

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

    const value = useMemo<WorkspaceContextValue>(
        () => ({
            conversations,
            documents,
            flashError,
            setFlashError,
            refreshConversations,
            removeConversation,
            refreshDocuments,
        }),
        [
            conversations,
            documents,
            flashError,
            refreshConversations,
            removeConversation,
            refreshDocuments,
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
