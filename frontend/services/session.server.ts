import "server-only";
import { cookies } from "next/headers";

import { UserResponse } from "@/services/auth";

const API_URL = process.env.BACKEND_API_URL ?? "http://localhost:8000";

export interface Session {
    user: UserResponse | null;
    authenticated: boolean;
}

export const getSession = async (): Promise<Session> => {
    try {
        const cookieStore = await cookies();

        // Build cookie header from all available cookies
        const allCookies = cookieStore.getAll();
        const cookieHeader = allCookies
            .map((c) => `${c.name}=${c.value}`)
            .join("; ");

        if (!cookieHeader) {
            return { user: null, authenticated: false };
        }

        const response = await fetch(`${API_URL}/api/users/me`, {
            headers: {
                Cookie: cookieHeader,
            },
            cache: "no-store",
        });

        if (!response.ok) {
            return { user: null, authenticated: false };
        }

        const user: UserResponse = await response.json();

        return {
            user,
            authenticated: true,
        };
    } catch {
        return {
            user: null,
            authenticated: false,
        };
    }
};
