"use client"

import React, { useState } from "react"
import type { ChangeEvent, Dispatch, SetStateAction } from "react"
import { useRouter } from "next/navigation"
import { ShieldCheck } from "lucide-react"

import {
    Card,
    CardHeader,
    CardTitle,
    CardContent,
    CardDescription,
    CardFooter,
} from "../ui/card"

import { Input } from "../ui/input"
import { Button } from "../ui/button"
import { Field, FieldLabel, FieldDescription } from "../ui/field"

import { login } from "@/services/auth"
import { getApiErrorMessage } from "@/services/error"


const handleChange = (
    event: ChangeEvent<HTMLInputElement>,
    setValue: Dispatch<SetStateAction<string>>,
    setError: Dispatch<SetStateAction<string>>
) => {
    const input = event.target.value;

    if (/\p{Extended_Pictographic}/u.test(input)) {
        setError("Emojis are not allowed");
        return;
    }
    setError("");
    setValue(input);
}


const LoginForm = () => {
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")

    const [loading, setLoading] = useState(false)
    const [error, setError] = useState("")

    const router = useRouter()

    const handleSubmit = async (event: React.SubmitEvent<HTMLFormElement>) => {
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
            router.refresh()
        } catch (error) {
            setError(getApiErrorMessage(error))
        } finally {
            setLoading(false)
        }
    }

    return (
        <form
            onSubmit={handleSubmit}
            className="w-full min-h-screen flex items-center justify-center bg-transparent px-4 sm:px-0"
        >
            <Card className="w-full max-w-sm">
                <CardHeader className="text-center">
                    <div className="flex items-center justify-center gap-2 mb-2">
                        <div className="p-2 rounded-xl bg-primary/10 text-primary">
                            <ShieldCheck className="size-5" />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-foreground">Chanakya AI</h1>
                    </div>
                    <CardTitle className="text-2xl font-black">
                        Sign in to your account
                    </CardTitle>

                    <CardDescription className="text-sm">
                        Access your campaign intelligence dashboard
                    </CardDescription>
                </CardHeader>

                <CardContent className="space-y-4">
                    <Field>
                        <FieldLabel htmlFor="login-input-field-email">
                            Email
                        </FieldLabel>

                        <Input
                            id="login-input-field-email"
                            type="email"
                            value={email}
                            onChange={(e) => handleChange(e, setEmail, setError)}
                            placeholder="Enter your email"
                            required
                            disabled={loading}
                            autoComplete="email"
                        />
                    </Field>

                    <Field>
                        <FieldLabel htmlFor="login-input-field-password">
                            Password
                        </FieldLabel>

                        <Input
                            id="login-input-field-password"
                            type="password"
                            value={password}
                            onChange={(e) => handleChange(e, setPassword, setError)}
                            placeholder="Enter password"
                            required
                            disabled={loading}
                            autoComplete="current-password"
                        />
                    </Field>

                    {error && (
                        <FieldDescription className="text-sm text-destructive">
                            {error}
                        </FieldDescription>
                    )}

                    <Button
                        variant="default"
                        size="lg"
                        className="w-full mt-2"
                        type="submit"
                        disabled={loading}
                    >
                        {loading ? "Signing in…" : "Sign in"}
                    </Button>
                </CardContent>

                <CardFooter className="flex flex-col gap-3">
                    <div className="flex items-center justify-between text-sm">
                        <p className="text-muted-foreground">
                            Accounts are created by an administrator.
                        </p>
                        <button
                            type="button"
                            className="text-primary underline underline-offset-4 hover:text-primary/80"
                            onClick={() => setError("Contact your administrator to reset your password.")}
                        >
                            Forgot password?
                        </button>
                    </div>
                </CardFooter>
            </Card>
        </form>
    )
}

export default LoginForm
