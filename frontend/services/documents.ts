import api from "@/lib/axios";

export interface DocumentResponse {
    id: string;
    user_id: string;
    filename: string;
    content_type: string;
    size_bytes: number;
    chunk_count: number;
    created_at: string;
}

export const getAllDocuments = async (): Promise<DocumentResponse[]> => {
    const response = await api.get<DocumentResponse[]>("/documents");

    return response.data;
}

// Loads, chunks and embeds the file server-side; resolves once it is searchable.
export const uploadDocument = async (file: File): Promise<DocumentResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await api.post<DocumentResponse>("/documents", formData);

    return response.data;
}

export const deleteDocument = async (id: string): Promise<void> => {
    await api.delete(`/documents/${id}`);
}
