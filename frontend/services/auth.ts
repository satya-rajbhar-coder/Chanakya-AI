import api from "../lib/axios";

export interface LoginRequest {
    email: string;
    password: string;
}

export interface RegisterRequest {
    name: string;
    email: string;
    password: string;
    confirm_password: string;
}

export interface AuthMessage {
    message: string
}

export interface UserResponse {
    id: string;
    name: string;
    email: string;
}


export const login = async (data: LoginRequest): Promise<AuthMessage> => {
    const response = await api.post<AuthMessage>("/auth/login", data);

    return response.data;
}

export const refresh = async (): Promise<AuthMessage> => {
    const response = await api.post<AuthMessage>("/auth/refresh")

    return response.data;
}

export const register = async (data: RegisterRequest): Promise<AuthMessage> => {
    const response = await api.post<AuthMessage>("/auth/register", data);

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