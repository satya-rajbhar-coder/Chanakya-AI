"use client"

import React, { useState, useCallback } from "react"
import { useRouter } from "next/navigation"
import {
    Mail,
    AlertCircle,
    Loader2,
    ShieldAlert,
    ArrowLeft,
    CheckCircle,
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

import { forgotPassword } from "@/services/auth"
import { getApiErrorMessage } from "@/services/error"

interface ForgotPasswordFormProps {
    onBackToLogin?: () => void
}

const ForgotPasswordForm = ({ onBackToLogin }: ForgotPasswordFormProps = {}) => {
    const [email, setEmail] = useState("")
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState("")
    const [success, setSuccess] = useState(false)
    const [rateLimitReset, setRateLimitReset] = useState<number | null>(null)

    const router = useRouter()

    const handleSubmit = useCallback(
        async (event: React.FormEvent<HTMLFormElement>) => {
            event.preventDefault()

            setError("")
            setSuccess(false)

            if (!email.trim()) {
                setError("Email address is required")
                return
            }

            setLoading(true)

            try {
                await forgotPassword({ email })
                setSuccess(true)
            } catch (err) {
                const message = getApiErrorMessage(err)
                // Check if it's a rate limit error (429)
                if (message.includes("too quickly") || message.includes("429")) {
                    setRateLimitReset(Date.now() + 60000) // Retry after 1 minute
                }
                setError(message)
            } finally {
                setLoading(false)
            }
        },
        [email]
    )

    const isRateLimited = rateLimitReset !== null && Date.now() < rateLimitReset

    if (success) {
        return (
            <div className="w-full min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/5 via-background to-secondary/5 px-4 sm:px-6 lg:px-8">
                <Card className="w-full max-w-md shadow-xl border border-border/50">
                    <CardHeader className="text-center pb-8">
                        <div className="flex items-center justify-center gap-2 mb-4">
                            <div className="p-3 rounded-2xl bg-emerald-500 text-emerald-500">
                                <CheckCircle className="size-6" />
                            </div>
                            <div>
                                <h1 className="text-2xl font-bold tracking-tight text-foreground">
                                    Reset Link Sent
                                </h1>
                                <p className="text-xs text-muted-foreground tracking-wider uppercase">
                                    Check your inbox
                                </p>
                            </div>
                        </div>
                    </CardHeader>

                    <CardContent className="space-y-5">
                        <p className="text-sm text-muted-foreground">
                            If an account exists for
                            <span className="font-medium text-foreground">{email}</span>,
                            a password reset link has been sent to that email address.
                        </p>
                    </CardContent>

                    <CardFooter className="pt-6">
                        <Button
                            variant="default"
                            size="lg"
                            className="w-full"
                            onClick={() => {
                                setSuccess(false)
                                setEmail("")
                                if (onBackToLogin) onBackToLogin()
                                else router.replace("/login")
                            }}
                        >
                            <ArrowLeft className="mr-2 size-4" />
                            Back to Sign In
                        </Button>
                    </CardFooter>
                </Card>
            </div>
        )
    }

    return (
        <div className="w-full min-h-screen flex items-center justify-center bg-gradient-to-br from-primary/5 via-background to-secondary/5 px-4 sm:px-6 lg:px-8">
            <Card className="w-full max-w-md shadow-xl border border-border/50">
                <CardHeader className="text-center pb-8">
                    <div className="flex items-center justify-center gap-2 mb-4">
                        <div className="p-3 rounded-2xl bg-primary text-primary-foreground">
                            <ShieldAlert className="size-6" />
                        </div>
                        <div>
                            <h1 className="text-2xl font-bold tracking-tight text-foreground">
                                Forgot Password
                            </h1>
                            <p className="text-xs text-muted-foreground tracking-wider uppercase">
                                Reset your password
                            </p>
                        </div>
                    </div>
                    <CardTitle className="text-2xl font-black text-foreground">
                        Reset your password
                    </CardTitle>
                    <CardDescription className="text-sm text-muted-foreground">
                        Enter your email and we'll send you a reset link.
                    </CardDescription>
                </CardHeader>

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
                                disabled={loading || isRateLimited}
                                autoComplete="email"
                                className="pl-10"
                            />
                        </div>
                    </div>

                    {isRateLimited && (
                        <div className="flex items-center gap-2 rounded-lg border border-orange-200 bg-orange-50 p-3 text-orange-800">
                            <AlertCircle className="size-4 shrink-0 text-orange-600" />
                            <span className="text-sm">
                                Too many requests. Please try again in
                                {" "}
                                <span className="font-medium">
                                    {Math.ceil((rateLimitReset! - Date.now()) / 1000)}
                                    seconds
                                </span>
                                .
                            </span>
                        </div>
                    )}

                    {error && !isRateLimited && (
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
                        disabled={loading || isRateLimited || !email.trim()}
                    >
                        {loading ? (
                            <>
                                <Loader2 className="size-4 animate-spin mr-2" />
                                Sending…
                            </>
                        ) : (
                            <>
                                Send Reset Link <Mail className="ml-2 size-4" />
                            </>
                        )}
                    </Button>
                </CardContent>

                <CardFooter className="pt-6">
                    <div className="flex flex-col gap-4">
                        <p className="text-sm text-muted-foreground">
                            Remember your password?
                        </p>
                        <Button
                            variant="link"
                            size="sm"
                            className="w-full text-left text-primary"
                            onClick={() => {
                                if (onBackToLogin) onBackToLogin()
                                else router.replace("/login")
                            }}
                        >
                            <ArrowLeft className="mr-2 size-4" />
                            Back to Sign In
                        </Button>
                    </div>
                </CardFooter>
            </Card>
        </div>
    )
}

export default ForgotPasswordForm
