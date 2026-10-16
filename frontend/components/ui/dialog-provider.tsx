"use client"

import { createContext, useCallback, useContext, useState } from "react"

import { Button } from "@/components/ui/button"
import Modal from "@/components/ui/modal"

interface ConfirmOptions {
    title: string
    description?: string
    confirmLabel?: string
    cancelLabel?: string
    destructive?: boolean
}

interface AlertOptions {
    title: string
    description?: string
}

interface DialogContextValue {
    confirm: (options: ConfirmOptions) => Promise<boolean>
    alert: (options: AlertOptions) => Promise<void>
}

interface DialogRequest {
    kind: "confirm" | "alert"
    options: ConfirmOptions
    resolve: (value: boolean) => void
}

const DialogContext = createContext<DialogContextValue | null>(null)

/** App-wide custom confirm/alert; never opens browser dialogs. */
export const DialogProvider = ({ children }: { children: React.ReactNode }) => {
    const [request, setRequest] = useState<DialogRequest | null>(null)

    const confirm = useCallback(
        (options: ConfirmOptions) =>
            new Promise<boolean>((resolve) => setRequest({ kind: "confirm", options, resolve })),
        []
    )

    const alert = useCallback(
        (options: AlertOptions) =>
            new Promise<void>((resolve) =>
                setRequest({ kind: "alert", options, resolve: () => resolve() })
            ),
        []
    )

    const close = (value: boolean) => {
        if (!request) return
        request.resolve(value)
        setRequest(null)
    }

    const isConfirm = request?.kind === "confirm"

    return (
        <DialogContext.Provider value={{ confirm, alert }}>
            {children}

            <Modal
                open={request !== null}
                onClose={() => close(false)}
                title={request?.options.title ?? ""}
                footer={
                    <>
                        {isConfirm && (
                            <Button variant="outline" onClick={() => close(false)}>
                                {request?.options.cancelLabel ?? "Cancel"}
                            </Button>
                        )}
                        <Button
                            variant={request?.options.destructive ? "destructive" : "default"}
                            onClick={() => close(true)}
                        >
                            {request?.options.confirmLabel ?? (isConfirm ? "Confirm" : "OK")}
                        </Button>
                    </>
                }
            >
                {request?.options.description && (
                    <p className="text-sm text-muted-foreground">{request.options.description}</p>
                )}
            </Modal>
        </DialogContext.Provider>
    )
}

export const useDialogs = (): DialogContextValue => {
    const context = useContext(DialogContext)

    if (!context) {
        throw new Error("useDialogs must be used inside <DialogProvider>")
    }

    return context
}

export const useConfirm = () => useDialogs().confirm
export const useAlert = () => useDialogs().alert
