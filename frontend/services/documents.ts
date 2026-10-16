import api from "@/lib/axios";

export const ACCEPTED_FILES = ".pdf,.txt,.md";

export interface DocumentResponse {
    id: string;
    user_id: string;
    client_id: string | null;
    assigned_user_ids: string[];
    filename: string;
    content_type: string;
    size_bytes: number;
    chunk_count: number;
    created_at: string;
}

// Scoped server-side: users see documents of their assigned clients, admins see all.
export const getAllDocuments = async (): Promise<DocumentResponse[]> => {
    const response = await api.get<DocumentResponse[]>("/documents");

    return response.data;
};

// Admin only. Loads, chunks and embeds the file server-side; resolves once it is searchable.
export const uploadDocument = async (
    file: File,
    userIds: string[]
): Promise<DocumentResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_ids", JSON.stringify(userIds));

    const response = await api.post<DocumentResponse>("/documents", formData);

    return response.data;
};

// Admin only.
export const deleteDocument = async (id: string): Promise<void> => {
    await api.delete(`/documents/${id}`);
};