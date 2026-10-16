"use client"

import { useState } from "react"

import AnalysisChat from "./AnalysisChat"
import DocumentsChat from "./DocumentsChat"
import ChatTabs, { type ChatMode } from "./ChatTabs"

const ChatHome = () => {
    const [mode, setMode] = useState<ChatMode>("documents")

    return (
        <div className="flex min-h-0 flex-1 flex-col">
            <ChatTabs value={mode} onChange={setMode} />

            <div className={mode === "documents" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
                <DocumentsChat />
            </div>

            <div className={mode === "analysis" ? "flex min-h-0 flex-1 flex-col" : "hidden"}>
                <AnalysisChat />
            </div>
        </div>
    )
}

export default ChatHome