"use client"

import { cn } from "@/lib/utils"
import { createContext, useCallback, useContext, useMemo, useState } from "react"

export type ToastType = "success" | "error" | "info" | "loading"

export interface Toast {
    id: string
    title: string
    description?: string
    type: ToastType
    duration?: number
}

interface ToastContextValue {
    toasts: Toast[]
    showToast: (toast: Omit<Toast, "id">) => void
    dismissToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const TOAST_AUTO_DISMISS_MS = 5000

export const ToastProvider = ({
    children,
}: {
    children: React.ReactNode
}) => {
    const [toasts, setToasts] = useState<Toast[]>([])

    const showToast = useCallback(
        (toast: Omit<Toast, "id">) => {
            const id = crypto.randomUUID()
            const newToast: Toast = { ...toast, id }

            setToasts((prev) => [...prev, newToast])

            if (toast.duration !== 0) {
                setTimeout(() => {
                    setToasts((prev) => prev.filter((t) => t.id !== id))
                }, toast.duration ?? TOAST_AUTO_DISMISS_MS)
            }
        },
        []
    )

    const dismissToast = useCallback((id: string) => {
        setToasts((prev) => prev.filter((t) => t.id !== id))
    }, [])

    const value = useMemo<ToastContextValue>(
        () => ({ toasts, showToast, dismissToast }),
        [toasts, showToast, dismissToast]
    )

    return (
        <ToastContext.Provider value={value}>
            {children}
            <ToastContainer />
        </ToastContext.Provider>
    )
}

export const useToast = () => {
    const context = useContext(ToastContext)
    if (!context) {
        throw new Error("useToast must be used within <ToastProvider>")
    }
    return context
}

const ToastContent = ({
    toast,
    onDismiss,
}: {
    toast: Toast
    onDismiss: () => void
}) => {
    const icons: Record<ToastType, React.ReactNode> = {
        success: (
            <svg
                className="h-4 w-4 text-emerald-500"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            >
                <polyline points="20 6 9 17 4 12" />
            </svg>
        ),
        error: (
            <svg
                className="h-4 w-4 text-destructive"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            >
                <circle cx="12" cy="12" r="10" />
                <line x1="15" y1="9" x2="9" y2="15" />
                <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
        ),
        info: (
            <svg
                className="h-4 w-4 text-primary"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
        ),
        loading: (
            <svg
                className="h-4 w-4 text-muted-foreground animate-spin"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            >
                <line x1="12" y1="2" x2="12" y2="6" />
                <line x1="12" y1="18" x2="12" y2="22" />
                <line x1="2" y1="12" x2="6" y2="12" />
                <line x1="18" y1="12" x2="22" y2="12" />
            </svg>
        ),
    }

    const typeColors: Record<ToastType, string> = {
        success: "border-emerald-500/50 bg-emerald-500/5 text-emerald-900",
        error: "border-destructive/50 bg-destructive/5 text-destructive",
        info: "border-primary/50 bg-primary/5 text-primary",
        loading: "border-muted/50 bg-muted/5 text-muted-foreground",
    }

    return (
        <div
            className={cn(
                "flex items-center gap-3 overflow-hidden rounded-xl border p-3 text-sm shadow-lg animate-in fade-in slide-in-from-top-2",
                typeColors[toast.type]
            )}
        >
            <div className="shrink-0">{icons[toast.type]}</div>
            <div className="grid gap-0.5">
                <p className="font-semibold">{toast.title}</p>
                {toast.description && (
                    <p className="text-xs text-muted-foreground">{toast.description}</p>
                )}
            </div>
            <button
                type="button"
                onClick={onDismiss}
                className="shrink-0 opacity-50 hover:opacity-100 transition-opacity"
                aria-label="Dismiss"
            >
                <svg
                    className="h-4 w-4"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                >
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
            </button>
        </div>
    )
}

const ToastContainer = () => {
    const { toasts, dismissToast } = useToast()

    return (
        <div className="fixed top-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:max-w-sm pointer-events-none">
            {toasts.map((toast) => (
                <div
                    key={toast.id}
                    className="pointer-events-auto"
                >
                    <ToastContent
                        toast={toast}
                        onDismiss={() => dismissToast(toast.id)}
                    />
                </div>
            ))}
        </div>
    )
}