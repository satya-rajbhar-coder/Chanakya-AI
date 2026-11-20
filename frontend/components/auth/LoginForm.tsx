"use client"

import React, { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import {
    Mail,
    Lock,
    Eye,
    EyeOff,
    AlertCircle,
    Loader2,
    ShieldCheck,
    ArrowRight,
    ArrowLeft,
} from "lucide-react"

import {
    Card,
    CardHeader,
    CardTitle,
    CardDescription,
    CardContent,
    CardFooter,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"

import { login } from "@/services/auth"
import { getApiErrorMessage } from "@/services/error"

const LoginForm = () => {
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [showPassword, setShowPassword] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState("")

    const router = useRouter()

    const handleSubmit = useCallback(
        async (event: React.FormEvent<HTMLFormElement>) => {
            event.preventDefault()

            setError("")

            if (!email.trim() || !password.trim()) {
                setError("Email and password are required")
                return
            }

            setLoading(true)

            try {
                await login({ email, password })

                router.replace("/")
            } catch (err) {
                setError(getApiErrorMessage(err))
            } finally {
                setLoading(false)
            }
        },
        [email, password, router]
    )

    return (
        <div className="w-full min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/5 via-background to-secondary/5 px-4 sm:px-6 lg:px-8">
            <Card className="w-full max-w-md shadow-xl border border-border/50">
                <CardHeader className="text-center pb-8">
                    <div className="flex items-center justify-center gap-2 mb-4">
                        <div className="p-3 rounded-2xl bg-primary text-primary-foreground">
                            <ShieldCheck className="size-6" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight text-foreground">
                                Chanakya AI
                            </h1>
                            <p className="text-xs text-muted-foreground tracking-wider uppercase">
                                Political Campaign Intelligence
                            </p>
                        </div>
                    </div>
                    <CardTitle className="text-2xl font-black text-foreground">
                        Sign in
                    </CardTitle>
                    <CardDescription className="text-sm text-muted-foreground">
                        Access your campaign dashboard and voter intelligence tools.
                    </CardDescription>
                </CardHeader>

                <form onSubmit={handleSubmit}>
                    <CardContent className="space-y-5">
                        <div className="space-y-2">
                            <Label htmlFor="email" className="text-sm font-medium text-foreground">
                                Email Address
                            </Label>
                            <div className="relative">
                                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                                <Input
                                    id="email"
                                    type="email"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="name@example.com"
                                    required
                                    disabled={loading}
                                    autoComplete="email"
                                    className="pl-10"
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="password" className="text-sm font-medium text-foreground">
                                Password
                            </Label>
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                                <Input
                                    id="password"
                                    type={showPassword ? "text" : "password"}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    required
                                    disabled={loading}
                                    autoComplete="current-password"
                                    className="pl-10 pr-10"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-primary transition-colors"
                                    aria-label={showPassword ? "Hide password" : "Show password"}
                                >
                                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                                </button>
                            </div>
                        </div>

                        {error && (
                            <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-destructive">
                                <AlertCircle className="size-4 shrink-0" />
                                <span className="text-sm">{error}</span>
                            </div>
                        )}

                        <Button
                            variant="default"
                            size="lg"
                            className="w-full"
                            type="submit"
                            disabled={loading}
                        >
                            {loading ? (
                                <>
                                    <Loader2 className="size-4 animate-spin mr-2" />
                                    Signing in…
                                </>
                            ) : (
                                <>
                                    Sign in <ArrowRight className="ml-2 size-4" />
                                </>
                            )}
                        </Button>
                    </CardContent>
                </form>

                <CardFooter className="pt-6">
                    <div className="flex flex-col gap-4">
                        <p className="text-sm text-muted-foreground">
                            Don't have an account? Contact your administrator to
                            create one.
                        </p>
                        <div className="pt-2 border-t border-border/50">
                            <p className="text-xs text-muted-foreground mb-2">
                                Need help?
                            </p>
                            <button
                                type="button"
                                className="text-sm text-primary underline underline-offset-4 hover:text-primary/80 transition-colors"
                                onClick={() => router.replace("/forgot-password")}
                            >
                                Forgot password?
                            </button>
                        </div>
                    </div>
                </CardFooter>
            </Card>
        </div >
    )
}

export default LoginForm
