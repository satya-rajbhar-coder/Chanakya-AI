import "server-only";
import { cookies } from "next/headers";

import api from "@/lib/axios";
import { UserResponse } from "@/services/auth";

export interface Session {
    user: UserResponse | null;
    authenticated: boolean;
}

export const getSession = async (): Promise<Session> => {
    try {
        const cookieStore = await cookies();

        const response = await api.get<UserResponse>("/users/me", {
            headers: {
                Cookie: cookieStore.toString(),
            },
        });

        return {
            user: response.data,
            authenticated: true,
        };
    } catch {
        return {
            user: null,
            authenticated: false,
        };
    }
};
