"use client"

import React, { useState } from "react"
import type { ChangeEvent, Dispatch, SetStateAction } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

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
            className="w-full h-screen flex items-center 
            justify-center bg-transparent"
        >
            <Card className="w-full max-w-sm">
                <CardHeader className="text-center">
                    <CardTitle className="text-2xl font-black">
                        Login
                    </CardTitle>

                    <CardDescription>
                        Upload & ask anything from your PDF
                    </CardDescription>
                </CardHeader>

                <CardContent>
                    <Field>
                        <FieldLabel htmlFor="login-input-field-email">
                            Email
                        </FieldLabel>

                        <Input
                            id="login-input-field-email"
                            type="email" value={email}
                            onChange={(e) => handleChange(e, setEmail, setError)}
                            placeholder="Enter your email" required
                            disabled={loading} autoComplete="email"
                        />

                        <FieldLabel htmlFor="login-input-field-password">
                            Password
                        </FieldLabel>

                        <Input
                            id="login-input-field-password"
                            type="password" value={password}
                            onChange={(e) => handleChange(e, setPassword, setError)}
                            placeholder="Enter password"
                            disabled={loading} required
                            autoComplete="current-password"
                        />

                        {error && (
                            <FieldDescription className="text-center text-red-400 font-semibold">
                                {error}
                            </FieldDescription>
                        )}

                    </Field>
                    <Button
                        variant="outline"
                        size="lg"
                        className="w-full mt-4"
                        type="submit"
                        disabled={loading}
                    >
                        {loading ? "Loading..." : "Login"}
                    </Button>
                </CardContent>

                <CardFooter className="flex items-center justify-center">
                    <p className="text-center">Don&apos;t have an account? <Link href="/register" className="text-blue-500">Register</Link></p>
                </CardFooter>
            </Card>
        </form>
    )
}

export default LoginForm
