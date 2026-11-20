"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"

type Theme = "light" | "dark" | "system"

interface ThemeContextType {
    theme: Theme
    setTheme: (theme: Theme) => void
    mounted: boolean
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({
    children,
    defaultTheme = "system",
    enableSystem = true,
    disableTransitionOnChange = false,
    ...props
}: {
    children: ReactNode
    defaultTheme?: Theme
    enableSystem?: boolean
    disableTransitionOnChange?: boolean
    [key: string]: unknown
}) {
    const [mounted, setMounted] = useState(false)
    const [theme, setThemeState] = useState<Theme>(defaultTheme)

    useEffect(() => {
        setMounted(true)
        const stored = localStorage.getItem("theme")
        if (stored && (stored === "light" || stored === "dark" || stored === "system")) {
            setThemeState(stored)
        }
    }, [])

    const setTheme = (nextTheme: Theme) => {
        setThemeState(nextTheme)
        localStorage.setItem("theme", nextTheme)
        applyTheme(nextTheme)
    }

    const applyTheme = (nextTheme: Theme) => {
        if (nextTheme === "system") {
            const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
            document.documentElement.classList.toggle("dark", systemTheme === "dark")
        } else {
            document.documentElement.classList.toggle("dark", nextTheme === "dark")
        }
    }

    useEffect(() => {
        if (!mounted) return
        applyTheme(theme)
    }, [theme, mounted])

    // Listen for system theme changes
    useEffect(() => {
        if (!mounted || theme !== "system") return
        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)")
        const handler = () => {
            document.documentElement.classList.toggle("dark", mediaQuery.matches)
        }
        mediaQuery.addEventListener("change", handler)
        return () => mediaQuery.removeEventListener("change", handler)
    }, [mounted, theme])

    return (
        <ThemeContext.Provider value={{ theme, setTheme, mounted }}>
            {children}
        </ThemeContext.Provider>
    )
}

export function useTheme() {
    const context = useContext(ThemeContext)
    if (!context) {
        throw new Error("useTheme must be used within a ThemeProvider")
    }
    return context
}