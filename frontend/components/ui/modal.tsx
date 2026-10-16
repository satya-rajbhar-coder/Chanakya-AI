"use client"

import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

interface ModalProps {
    open: boolean
    onClose: () => void
    title: string
    children?: React.ReactNode
    footer?: React.ReactNode
    widthClass?: string
}

/** Modal built on shadcn Dialog primitives - replaces browser dialogs and window.prompt flows. */
const Modal = ({
    open,
    onClose,
    title,
    children,
    footer,
    widthClass = "max-w-md",
}: ModalProps) => {
    return (
        <DialogPrimitive.Root open={open} onOpenChange={(next) => { if (!next) onClose() }}>
            <DialogPrimitive.Portal>
                <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />

                <DialogPrimitive.Content
                    className={cn(
                        "fixed left-1/2 top-1/2 z-50 flex max-h-[85vh] w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-xl border bg-background shadow-lg",
                        widthClass
                    )}
                >
                    <div className="flex shrink-0 items-center justify-between border-b px-4 py-3">
                        <DialogPrimitive.Title className="text-sm font-semibold">
                            {title}
                        </DialogPrimitive.Title>

                        <DialogPrimitive.Close
                            className="rounded p-1 text-muted-foreground hover:bg-accent"
                            aria-label="Close"
                        >
                            <X className="size-4" />
                        </DialogPrimitive.Close>
                    </div>

                    <DialogPrimitive.Description className="sr-only">
                        {title}
                    </DialogPrimitive.Description>

                    {children && <div className="min-h-0 flex-1 overflow-y-auto p-4">{children}</div>}

                    {footer && (
                        <div className="flex shrink-0 justify-end gap-2 border-t px-4 py-3">
                            {footer}
                        </div>
                    )}
                </DialogPrimitive.Content>
            </DialogPrimitive.Portal>
        </DialogPrimitive.Root>
    )
}

export default Modal