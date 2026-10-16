import api from "@/lib/axios";
import { UserRole } from "@/services/auth";

export interface Client {
    id: string;
    code: string;
    name: string;
    database_name: string;
    client_identifier: string;
    description: string | null;
    is_active: boolean;
    created_at: string;
}

export interface ClientCreate {
    code: string;
    name: string;
    database_name: string;
    client_identifier: string;
    description?: string;
}

export interface ClientUpdate {
    name?: string;
    description?: string;
    is_active?: boolean;
}

export interface AdminUser {
    id: string;
    name: string;
    email: string;
    role: UserRole;
    is_active: boolean;
    client_ids: string[];
}

export interface AdminUserCreate {
    name: string;
    email: string;
    password: string;
    client_ids: string[];
}

export interface AdminUserUpdate {
    name?: string;
    password?: string;
    is_active?: boolean;
}

export const listAdminClients = async (): Promise<Client[]> =>
    (await api.get<Client[]>("/admin/clients")).data;

export const createClient = async (data: ClientCreate): Promise<Client> =>
    (await api.post<Client>("/admin/clients", data)).data;

export const updateClient = async (clientId: string, data: ClientUpdate): Promise<Client> =>
    (await api.patch<Client>(`/admin/clients/${clientId}`, data)).data;

export const listAdminUsers = async (): Promise<AdminUser[]> =>
    (await api.get<AdminUser[]>("/admin/users")).data;

export const createAdminUser = async (data: AdminUserCreate): Promise<AdminUser> =>
    (await api.post<AdminUser>("/admin/users", data)).data;

export const setUserAssignments = async (userId: string, clientIds: string[]): Promise<AdminUser> =>
    (await api.put<AdminUser>(`/admin/users/${userId}/assignments`, { client_ids: clientIds })).data;

export const updateAdminUser = async (userId: string, data: AdminUserUpdate): Promise<AdminUser> =>
    (await api.patch<AdminUser>(`/admin/users/${userId}`, data)).data;