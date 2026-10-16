import api from "../lib/axios";

export interface LoginRequest {
    email: string;
    password: string;
}

export interface AuthMessage {
    message: string
}

export type UserRole = "admin" | "user";

export interface UserResponse {
    id: string;
    name: string;
    email: string;
    role: UserRole;
    is_active: boolean;
}


export const login = async (data: LoginRequest): Promise<AuthMessage> => {
    const response = await api.post<AuthMessage>("/auth/login", data);

    return response.data;
}

export const refresh = async (): Promise<AuthMessage> => {
    const response = await api.post<AuthMessage>("/auth/refresh")

    return response.data;
}

export const getCurrentUser = async (): Promise<UserResponse> => {
    const response = await api.get<UserResponse>("/users/me");

    return response.data;
}

export const logout = async () => {
    const response = await api.post("/auth/logout");

    return response.data;
}