"use client"

import { ChartLine, File } from "lucide-react"

import {
    Tabs,
    TabsList,
    TabsTrigger,
} from "@/components/ui/tabs"

export type ChatMode = "documents" | "analysis"

interface ChatTabsProps {
    value: ChatMode
    onChange: (value: ChatMode) => void
}

const ChatTabs = ({
    value,
    onChange,
}: ChatTabsProps) => {
    return (
        <div className="flex shrink-0 justify-center border-b bg-muted/30 px-4 py-3">
            <Tabs
                value={value}
                onValueChange={(value) =>
                    onChange(value as ChatMode)
                }
            >
                <TabsList className="h-10 rounded-xl bg-background p-1 shadow-sm">
                    <TabsTrigger
                        value="documents"
                        className="
                            h-8 gap-2 rounded-lg px-4 text-sm font-medium
                            text-muted-foreground
                            data-[state=active]:bg-primary
                            data-[state=active]:text-primary-foreground
                            data-[state=active]:shadow-sm
                        "
                    >
                        <File className="size-4" />
                        Documents
                    </TabsTrigger>

                    <TabsTrigger
                        value="analysis"
                        className="
                            h-8 gap-2 rounded-lg px-4 text-sm font-medium
                            text-muted-foreground
                            data-[state=active]:bg-primary
                            data-[state=active]:text-primary-foreground
                            data-[state=active]:shadow-sm
                        "
                    >
                        <ChartLine className="size-4" />
                        Analysis
                    </TabsTrigger>
                </TabsList>
            </Tabs>
        </div>
    )
}

export default ChatTabs