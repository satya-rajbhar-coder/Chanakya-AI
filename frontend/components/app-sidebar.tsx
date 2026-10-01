"use client"

import { LogOut, SquarePen, Trash2, Moon, Sun } from "lucide-react"
import { useParams, useRouter } from "next/navigation"

import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarTrigger,
} from "@/components/ui/sidebar"

import { useTheme } from "next-themes"

import { DocumentsPanel } from "@/components/documents-panel"
import { useWorkspace } from "@/components/workspace-provider"

import { logout, UserResponse } from "@/services/auth"
import { getApiErrorMessage } from "@/services/error"
import { cn } from "@/lib/utils"

interface AppSidebarProps {
    user: UserResponse | null
}

export const AppSidebar = ({ user }: AppSidebarProps) => {
    const router = useRouter()
    const params = useParams<{ id?: string }>()

    const { theme,  setTheme } = useTheme()

    const { conversations, removeConversation } = useWorkspace()

    const handleNewChat = () => {
        router.push("/")
    }

    const handleConversationClick = (conversationId: string) => {
        router.push(`/chat/${conversationId}`)
    }

    const handleDeleteConversation = async (
        event: React.MouseEvent,
        conversationId: string,
        title: string
    ) => {
        event.stopPropagation()

        if (!window.confirm(`Delete "${title}"?`)) {
            return
        }

        try {
            await removeConversation(conversationId)

            if (params?.id === conversationId) {
                router.replace("/")
            }
        } catch (error) {
            window.alert(getApiErrorMessage(error))
        }
    }

    const handleLogout = async () => {
        try {
            await logout()
        } catch (error) {
            console.error(getApiErrorMessage(error))
        }

        router.replace("/login")
        router.refresh()
    }

    return (
        <Sidebar collapsible="icon">
            <SidebarHeader>
                <div className="flex items-center justify-between p-2">
                    <span className="text-lg font-semibold group-data-[collapsible=icon]:hidden">
                        Chanakya AI
                    </span>

                    <SidebarTrigger />
                </div>
            </SidebarHeader>

            <SidebarContent>
                <SidebarGroup>
                    <button
                        onClick={handleNewChat}
                        className="flex w-full items-center gap-2 rounded-md px-3 py-2 hover:bg-accent"
                    >
                        <SquarePen className="size-4 min-h-4 min-w-4 shrink-0" />
                        <span className="group-data-[collapsible=icon]:hidden text-sm">
                            New chat
                        </span>
                    </button>
                </SidebarGroup>

                <DocumentsPanel />

                <SidebarGroup className="group-data-[collapsible=icon]:hidden">
                    <SidebarGroupLabel className="text-sm">Chats</SidebarGroupLabel>

                    {conversations.length === 0 && (
                        <p className="px-2 py-1.5 text-xs text-muted-foreground">
                            No conversations yet.
                        </p>
                    )}

                    {conversations.map((conversation) => {
                        const isActive = params?.id === conversation.id

                        return (
                            <div
                                key={conversation.id}
                                className={cn(
                                    "group/chat flex items-center rounded-md hover:bg-accent",
                                    isActive && "bg-accent font-medium"
                                )}
                            >
                                <button
                                    onClick={() => handleConversationClick(conversation.id)}
                                    className="min-w-0 flex-1 truncate px-2 py-2 text-left text-sm"
                                    title={conversation.title}
                                >
                                    {conversation.title}
                                </button>

                                <button
                                    type="button"
                                    onClick={(event) =>
                                        handleDeleteConversation(
                                            event,
                                            conversation.id,
                                            conversation.title
                                        )
                                    }
                                    className="mr-1 rounded p-1 text-muted-foreground hover:text-destructive md:opacity-0 md:group-hover/chat:opacity-100 focus:opacity-100"
                                    aria-label={`Delete ${conversation.title}`}
                                >
                                    <Trash2 className="size-3.5" />
                                </button>
                            </div>
                        )
                    })}
                </SidebarGroup>
            </SidebarContent>

            <SidebarFooter>
                {user && (
                    <div className="px-3 py-1 group-data-[collapsible=icon]:hidden">
                        <p className="truncate text-sm font-medium">{user.name}</p>
                        <p className="truncate text-xs text-muted-foreground">
                            {user.email}
                        </p>
                    </div>
                )}

                <button
                    type="button"
                    onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                    className="flex items-center justify-between rounded-md px-3 py-2 text-sm hover:bg-accent"
                    aria-label="Toggle theme"
                >
                    <div className="flex items-center gap-2">
                        {theme === "dark" ? (
                            <Moon className="size-4 shrink-0" />
                        ) : (
                            <Sun className="size-4 shrink-0" />
                        )}

                        <span className="group-data-[collapsible=icon]:hidden">
                            {theme === "dark" ? "Dark mode" : "Light mode"}
                        </span>
                    </div>
                </button>

                <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-accent"
                >
                    <LogOut className="size-4 shrink-0" />
                    <span className="group-data-[collapsible=icon]:hidden">
                        Log out
                    </span>
                </button>
            </SidebarFooter>
        </Sidebar>
    )
}
