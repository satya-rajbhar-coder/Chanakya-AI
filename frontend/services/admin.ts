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
    database_name?: string;
}

export interface AvailableDatabase {
    name: string;
    is_assigned: boolean;
    assigned_client_id: string | null;
    assigned_client_name: string | null;
}

// Political role hierarchy (lowest to highest authority)
export const ROLE_HIERARCHY: Record<string, number> = {
    karyakarta: 1,
    corporator: 2,
    aamdar: 3,
    khasdar: 4,
    user: 5,
    admin: 6,
};

export const ROLE_LABELS: Record<string, string> = {
    karyakarta: "Karyakarta (Grassroots Worker)",
    corporator: "Corporator (Ward Councilor)",
    aamdar: "Aamdar (MLA)",
    khasdar: "Khasdar (MP)",
    user: "Dashboard User",
    admin: "Administrator",
};

export interface AdminUser {
    id: string;
    name: string;
    email: string;
    role: UserRole;
    hierarchy_level: number | null;
    is_active: boolean;
    party_name: string | null;
    ward_no: number | null;
    assembly_no: string | null;
    parliamentary_constituency: string | null;
    client_ids: string[];
}

export interface AdminUserCreate {
    name: string;
    email: string;
    password: string;
    role: UserRole;
    party_name?: string;
    ward_no?: number;
    assembly_no?: string;
    parliamentary_constituency?: string;
    client_ids: string[];
    database_name?: string;
}

export interface AdminUserUpdate {
    name?: string;
    password?: string;
    is_active?: boolean;
    role?: UserRole;
    party_name?: string;
    ward_no?: number;
    assembly_no?: string;
    parliamentary_constituency?: string;
    client_ids?: string[];
}

export const listAdminClients = async (): Promise<Client[]> =>
    (await api.get<Client[]>("/admin/clients")).data;

export const getAvailableDatabases = async (): Promise<AvailableDatabase[]> =>
    (await api.get<AvailableDatabase[]>("/admin/databases")).data;

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

export const deleteClient = async (clientId: string): Promise<void> =>
    (await api.delete(`/admin/clients/${clientId}`)).data;

export const deleteAdminUser = async (userId: string, confirm: boolean = false): Promise<void> =>
    (await api.delete(`/admin/users/${userId}`, { params: { confirm } })).data;

export const deactivateAdminUser = async (userId: string): Promise<AdminUser> =>
    (await api.post<AdminUser>(`/admin/users/${userId}/deactivate`)).data;