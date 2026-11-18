"use client"

import { useState } from "react"
import { Maximize2, Minimize2, Download } from "lucide-react"
import { Button } from "@/components/ui/button"

interface ImageWithZoomProps {
    src: string
    alt?: string
    title?: string
    [key: string]: unknown
}

export default function ImageWithZoom({ src, alt, title, ...props }: ImageWithZoomProps) {
    const [zoomed, setZoomed] = useState(false)
    const [loaded, setLoaded] = useState(false)
    const [error, setError] = useState(false)

    const handleZoom = () => {
        setZoomed(!zoomed)
    }

    const handleDownload = () => {
        const link = document.createElement("a")
        link.href = src
        link.download = alt || "image"
        link.target = "_blank"
        link.rel = "noopener noreferrer"
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    }

    if (error) {
        return (
            <div className="my-4 rounded-lg border bg-destructive/10 p-4 text-center text-sm text-destructive">
                Failed to load image: {alt || src}
            </div>
        )
    }

    return (
        <figure className="my-4">
            <div className="relative group">
                <div className="overflow-hidden rounded-lg border bg-muted/50">
                    <img
                        {...props}
                        src={src}
                        alt={alt}
                        title={title}
                        onLoad={() => setLoaded(true)}
                        onError={() => setError(true)}
                        className={`transition-all duration-200 w-full ${zoomed ? "cursor-zoom-out" : "cursor-zoom-in"
                            } ${!loaded ? "opacity-0" : "opacity-100"}`}
                        style={{ maxHeight: zoomed ? "none" : "500px" }}
                        onClick={handleZoom}
                    />
                    {!loaded && (
                        <div className="absolute inset-0 flex items-center justify-center bg-muted/50">
                            <div className="animate-spin rounded-full border-4 border-primary border-t-transparent size-8" />
                        </div>
                    )}
                </div>

                {/* Zoom controls */}
                <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                            e.stopPropagation()
                            handleZoom()
                        }}
                        className="size-8 rounded-full bg-background/80 backdrop-blur-sm"
                        aria-label={zoomed ? "Zoom out" : "Zoom in"}
                    >
                        {zoomed ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                            e.stopPropagation()
                            handleDownload()
                        }}
                        className="size-8 rounded-full bg-background/80 backdrop-blur-sm"
                        aria-label="Download image"
                    >
                        <Download className="size-4" />
                    </Button>
                </div>
            </div>

            {(alt || title) && (
                <figcaption className="mt-2 text-center text-sm text-muted-foreground">
                    {alt || title}
                </figcaption>
            )}

            {/* Fullscreen modal */}
            {zoomed && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm"
                    onClick={() => setZoomed(false)}
                    role="dialog"
                    aria-modal="true"
                    aria-label="Zoomed image"
                >
                    <button
                        onClick={() => setZoomed(false)}
                        className="absolute top-4 right-4 z-10 size-10 rounded-full bg-background/80 backdrop-blur-sm text-foreground hover:bg-background"
                        aria-label="Close zoom"
                    >
                        <Minimize2 className="size-5" />
                    </button>
                    <img
                        src={src}
                        alt={alt}
                        className="max-h-[90vh] max-w-[90vw] object-contain"
                        onClick={(e) => e.stopPropagation()}
                    />
                </div>
            )}
        </figure>
    )
}