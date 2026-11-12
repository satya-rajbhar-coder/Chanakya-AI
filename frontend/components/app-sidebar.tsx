"use client"

import { LogOut, SquarePen, Trash2, Moon, Sun, ShieldCheck, Menu, MessageCircle } from "lucide-react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarGroup,
    SidebarGroupLabel,
    SidebarHeader,
    SidebarTrigger,
    SidebarMenu,
    SidebarMenuItem,
    SidebarMenuButton,
} from "@/components/ui/sidebar"

import { useTheme } from "next-themes"

import { useWorkspace } from "@/components/workspace-provider"

import { logout, UserResponse } from "@/services/auth"
import { getApiErrorMessage } from "@/services/error"
import { cn } from "@/lib/utils"
import { useDialogs } from "@/components/ui/dialog-provider"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Badge } from "@/components/ui/badge"

interface AppSidebarProps {
    user: UserResponse | null
}

export const AppSidebar = ({ user }: AppSidebarProps) => {
    const router = useRouter()
    const params = useParams<{ id?: string }>()

    const { theme, setTheme } = useTheme()

    const { conversations, removeConversation } = useWorkspace()

    const isAdmin = user?.role === "admin"

    const { confirm, alert } = useDialogs()

    const handleNewChat = () => { router.push("/") }

    const handleConversationClick = (conversationId: string) => {
        router.push(`/chat/${conversationId}`)
    }

    const handleDeleteConversation = async (event: React.MouseEvent, conversationId: string, title: string) => {
        event.stopPropagation()

        const approved = await confirm({
            title: "Delete conversation?",
            description: `"${title}" and all of its messages will be removed.`,
            confirmLabel: "Delete",
            destructive: true,
        })

        if (!approved) {
            return
        }

        try {
            await removeConversation(conversationId)

            if (params?.id === conversationId) {
                router.replace("/")
            }
        } catch (error) {
            await alert({
                title: "Could not delete conversation",
                description: getApiErrorMessage(error),
            })
        }
    }

    const handleLogout = async () => {
        const approved = await confirm({
            title: "Log out?",
            description: "You will be signed out and returned to the login page.",
            confirmLabel: "Log out",
            destructive: true,
        })
        if (!approved) {
            return
        }
        try {
            await logout()
        } catch (error) {
            await alert({
                title: "Could not log out",
                description: getApiErrorMessage(error),
            })
            return
        }

        router.replace("/login")
        router.refresh()
    }

    return (
        <TooltipProvider>
            <Sidebar collapsible="icon">
                <SidebarHeader>
                    <div className="flex items-center justify-between group-data-[collapsible=icon]:justify-center p-3">
                        <div className="flex items-center gap-3">
                            <span className="text-lg font-bold group-data-[collapsible=icon]:hidden">
                                Chanakya AI
                            </span>
                        </div>
                        <SidebarTrigger />
                    </div>
                </SidebarHeader>

                <SidebarContent>
                    <SidebarGroup>
                        <SidebarMenu>
                            <SidebarMenuItem>
                                <SidebarMenuButton
                                    onClick={handleNewChat}
                                    className="gap-3"
                                >
                                    <SquarePen className="h-4 w-4" />
                                    <span className="group-data-[collapsible=icon]:hidden">
                                        New Chat
                                    </span>
                                </SidebarMenuButton>
                            </SidebarMenuItem>

                            {isAdmin && (
                                <SidebarMenuItem>
                                    <SidebarMenuButton>
                                        <Link
                                            href="/admin"
                                            className="flex w-full items-center gap-3"
                                        >
                                            <ShieldCheck className="h-4 w-4" />
                                            <span className="group-data-[collapsible=icon]:hidden">
                                                Admin Panel
                                            </span>
                                        </Link>
                                    </SidebarMenuButton>
                                </SidebarMenuItem>
                            )}
                        </SidebarMenu>
                    </SidebarGroup>


                    <SidebarGroup className="group-data-[collapsible=icon]:hidden">
                        <div className="flex items-center gap-1.5 px-2 py-1">
                            <MessageCircle className="size-3 shrink-0 text-muted-foreground" />
                            <SidebarGroupLabel className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Conversations</SidebarGroupLabel>
                        </div>

                        <SidebarMenu>
                            {conversations.length === 0 ? (
                                <div className="px-2 py-3 text-center text-xs text-muted-foreground">
                                    No conversations yet. Start a new chat!
                                </div>
                            ) : (
                                conversations.map((conversation) => {
                                    const isActive = params?.id === conversation.id

                                    return (
                                        <SidebarMenuItem key={conversation.id}>
                                            <div
                                                className={cn(
                                                    "group/chat flex w-full items-center gap-1 rounded-md pr-1",
                                                    isActive
                                                        ? "bg-sidebar-accent text-sidebar-accent-foreground"
                                                        : ""
                                                )}
                                            >
                                                <button
                                                    type="button"
                                                    onClick={() => handleConversationClick(conversation.id)}
                                                    className="min-w-0 flex-1 truncate rounded-md px-2 py-2 text-left text-sm outline-none"
                                                >
                                                    {conversation.title}
                                                </button>

                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="size-6 shrink-0 text-destructive"
                                                    onClick={(event) => handleDeleteConversation(event, conversation.id, conversation.title)}
                                                    aria-label={`Delete ${conversation.title}`}
                                                >
                                                    <Trash2 className="h-3.5 w-3.5" />
                                                </Button>
                                            </div>
                                        </SidebarMenuItem>
                                    )
                                })
                            )}
                        </SidebarMenu>
                    </SidebarGroup>
                </SidebarContent>

                <SidebarFooter>
                    <div className="flex flex-col gap-2 px-2 py-2">
                        {user && (
                            <div
                                className={cn(
                                    "flex items-center gap-2 rounded-lg px-2 py-1.5",
                                    "group-data-[collapsible=icon]:flex group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:py-1",
                                    "group-data-[collapsible=icon]:flex"
                                )}
                            >
                                <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-medium">
                                    {user.name?.charAt(0).toUpperCase() || 'U'}
                                </div>
                                <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
                                    <p className="truncate text-sm font-medium">{user.name}</p>
                                    <p className="truncate text-xs text-muted-foreground">{user.email}</p>
                                    {isAdmin && (
                                        <Badge variant="secondary" className="mt-1 w-fit gap-1">
                                            <ShieldCheck className="h-2.5 w-2.5" />
                                            Admin
                                        </Badge>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className="flex flex-col gap-1">
                            <Button
                                variant="ghost"
                                className={cn(
                                    "w-full justify-start gap-3",
                                    "group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
                                )}
                                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                            >
                                {theme === "dark" ? (
                                    <Moon className="h-4 w-4" />
                                ) : (
                                    <Sun className="h-4 w-4" />
                                )}
                                <span className="group-data-[collapsible=icon]:hidden">
                                    {theme === "dark" ? "Dark mode" : "Light mode"}
                                </span>
                            </Button>

                            <Button
                                variant="ghost"
                                className={cn(
                                    "w-full justify-start gap-3 text-destructive",
                                    "group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
                                )}
                                onClick={handleLogout}
                            >
                                <LogOut className="h-4 w-4" />
                                <span className="group-data-[collapsible=icon]:hidden">Log out</span>
                            </Button>
                        </div>
                    </div>
                </SidebarFooter>
            </Sidebar>
        </TooltipProvider>
    )
}

export default AppSidebar