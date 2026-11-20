import api from "@/lib/axios";
import { UserRole } from "@/services/auth";

export interface AvailableDatabase {
    name: string;
    is_assigned: boolean;
    assigned_client_id: string | null;
    assigned_client_name: string | null;
}

export const ROLE_HIERARCHY: Record<string, number> = {
    karyakarta: 1,
    corporator: 2,
    aamdar: 3,
    khasdar: 4,
    admin: 5,
};

export const ROLE_LABELS: Record<string, string> = {
    karyakarta: "Karyakarta (Grassroots Worker)",
    corporator: "Corporator (Ward Councilor)",
    aamdar: "Aamdar (MLA)",
    khasdar: "Khasdar (MP)",
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
    corporation: string | null;
    ward_no: number | null;
    assembly_no: string | null;
    parliamentary_constituency: string | null;
}

export interface AdminUserCreate {
    name: string;
    email: string;
    password: string;
    role: UserRole;
    party_name?: string;
    corporation?: string;
    ward_no?: number;
    assembly_no?: string;
    parliamentary_constituency?: string;
    database_name?: string;
}

export interface AdminUserUpdate {
    name?: string;
    password?: string;
    is_active?: boolean;
    role?: UserRole;
    party_name?: string;
    corporation?: string;
    ward_no?: number;
    assembly_no?: string;
    parliamentary_constituency?: string;
    database_name?: string;
}

export const getAvailableDatabases = async (): Promise<AvailableDatabase[]> =>
    (await api.get<AvailableDatabase[]>("/admin/databases")).data;

export const listAdminUsers = async (): Promise<AdminUser[]> =>
    (await api.get<AdminUser[]>("/admin/users")).data;

export const createAdminUser = async (data: AdminUserCreate): Promise<AdminUser> =>
    (await api.post<AdminUser>("/admin/users", data)).data;

export const assignUserToDatabase = async (userId: string, databaseName: string): Promise<AdminUser> =>
    (await api.put<AdminUser>(`/admin/users/${userId}/assignments`, { database_name: databaseName })).data;

export const updateAdminUser = async (userId: string, data: AdminUserUpdate): Promise<AdminUser> =>
    (await api.patch<AdminUser>(`/admin/users/${userId}`, data)).data;

export const deleteAdminUser = async (userId: string, confirm: boolean = false): Promise<void> =>
    (await api.delete(`/admin/users/${userId}`, { params: { confirm } })).data;

export const deactivateAdminUser = async (userId: string): Promise<AdminUser> =>
    (await api.post<AdminUser>(`/admin/users/${userId}/deactivate`)).data;