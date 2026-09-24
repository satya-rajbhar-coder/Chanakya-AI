import api from "@/lib/axios";

export type MessageRole = "user" | "assistant";

export interface MessageRequest {
    content: string;
}

export interface MessageResponse {
    id: string;
    user_id: string | null;
    conversation_id: string;
    role: MessageRole;
    content: string;
    created_at: string;
    updated_at: string;
}

export interface MessagePage {
    items: MessageResponse[]; // newest first
    next_cursor: string | null;
}

export interface ChatResponse {
    user_message: MessageResponse;
    assistant_message: MessageResponse;
}

// The API returns a cursor page ({ items, next_cursor }), not a bare array.
export const getAllConversationMessages = async ({
    conversation_id,
    cursor,
    limit = 50,
}: {
    conversation_id: string;
    cursor?: string | null;
    limit?: number;
}): Promise<MessagePage> => {
    const response = await api.get<MessagePage>(
        `/conversations/${conversation_id}/messages`,
        { params: { limit, cursor: cursor ?? undefined } }
    );

    return response.data;
}

export const sendMessage = async (
    conversation_id: string,
    data: MessageRequest
): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>(
        `/conversations/${conversation_id}/messages`,
        data
    );

    return response.data;
}
