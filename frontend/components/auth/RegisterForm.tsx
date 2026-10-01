"use client"

import React, { useState } from "react"
import type { ChangeEvent, Dispatch, SetStateAction } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { Input } from "../ui/input"
import { Button } from "../ui/button"
import { Field, FieldLabel, FieldDescription } from "../ui/field"
import {
    Card, CardHeader,
    CardTitle, CardContent,
    CardDescription, CardFooter,
} from "../ui/card"

import { register } from "@/services/auth"
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


const RegisterForm = () => {
    const [name, setName] = useState("")
    const [email, setEmail] = useState("")
    const [password, setPassword] = useState("")
    const [confirmPassword, setConfirmPassword] = useState("")
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState("")

    const router = useRouter()

    const handleSubmit = async (
        event: React.SubmitEvent<HTMLFormElement>
    ) => {
        event.preventDefault()

        setError("")

        const trimmedName = name.trim()
        const trimmedEmail = email.trim()

        if (!trimmedName) {
            setError("Please enter your name")
            return
        }

        if (!trimmedEmail) {
            setError("Please enter your email")
            return
        }

        if (!password) {
            setError("Please enter a password")
            return
        }

        if (password.length < 8) {
            setError("Password must contain at least 8 characters")
            return
        }

        if (!confirmPassword) {
            setError("Please confirm your password")
            return
        }

        if (password !== confirmPassword) {
            setError("Passwords do not match")
            return
        }

        setLoading(true)

        try {
            await register({
                name: trimmedName,
                email: trimmedEmail,
                password,
                confirm_password: confirmPassword,
            })
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
            className="w-full h-screen flex items-center justify-center bg-transparent"
        >
            <Card className="w-full max-w-sm">
                <CardHeader className="text-center">
                    <CardTitle className="text-xl font-black">
                        Register
                    </CardTitle>

                    <CardDescription>
                        Upload & ask anything from your PDF
                    </CardDescription>
                </CardHeader>

                <CardContent>
                    <Field>
                        <FieldLabel htmlFor="register-input-field-name">
                            Full Name
                        </FieldLabel>

                        <Input
                            id="register-input-field-name"
                            type="text" value={name}
                            onChange={(e) => handleChange(e, setName, setError)}
                            placeholder="Enter your name" required
                            disabled={loading}
                        />

                        <FieldLabel htmlFor="register-input-field-email">
                            Email
                        </FieldLabel>

                        <Input
                            id="register-input-field-email"
                            type="email" value={email}
                            onChange={(e) => handleChange(e, setEmail, setError)}
                            placeholder="Enter your email" required
                            disabled={loading}
                        />

                        <FieldLabel htmlFor="register-input-field-password">
                            Password
                        </FieldLabel>

                        <Input
                            id="register-input-field-password"
                            type="password" value={password} required
                            onChange={(e) => handleChange(e, setPassword, setError)}
                            placeholder="Enter password" disabled={loading}
                        />

                        <FieldLabel htmlFor="register-input-field-confirm-password">
                            Confirm Password
                        </FieldLabel>

                        <Input
                            id="register-input-field-confirm-password"
                            type="password" value={confirmPassword} required
                            onChange={(e) => handleChange(e, setConfirmPassword, setError)}
                            placeholder="Enter confirm password" disabled={loading}
                        />

                        {error && (
                            <FieldDescription className="text-center text-red-400 font-semibold">
                                {error}
                            </FieldDescription>
                        )}

                        <Button
                            variant="outline"
                            size="lg"
                            className="w-full mt-4"
                            type="submit"
                            disabled={loading}
                        >
                            {loading
                                ? "Creating..."
                                : "Create Account"}
                        </Button>
                    </Field>
                </CardContent>

                <CardFooter className="justify-center">
                    <p className="text-center">
                        Already have an account?{" "}
                        <Link
                            href="/login"
                            className="text-sky-500 hover:text-sky-600"
                        >
                            Login
                        </Link>
                    </p>
                </CardFooter>
            </Card>
        </form>
    )
}

export default RegisterForm
