import api from "@/lib/axios";

export interface ConversationRequest {
    title: string;
}

export interface ConversationResponse {
    id: string;
    user_id: string;
    title: string;
    created_at: string;
    updated_at: string;
}

export const getAllConversations = async (
    limit = 100
): Promise<ConversationResponse[]> => {
    const response = await api.get<ConversationResponse[]>("/conversations", {
        params: { limit },
    });

    return response.data;
}

export const createConversation = async (
    data: ConversationRequest
): Promise<ConversationResponse> => {
    const response = await api.post<ConversationResponse>("/conversations", data);

    return response.data;
}

export const deleteConversation = async (id: string): Promise<void> => {
    await api.delete(`/conversations/${id}`);
}
