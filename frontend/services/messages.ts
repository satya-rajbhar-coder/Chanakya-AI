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
    analysis_query_id?: string | null;
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

// Safety cap so a misbehaving cursor can never loop forever.
const MAX_MESSAGE_PAGES = 1000

export const getEntireConversationMessages = async (
    conversation_id: string,
): Promise<MessageResponse[]> => {
    const messages: MessageResponse[] = []
    let cursor: string | null = null
    let pages = 0

    do {
        if (++pages > MAX_MESSAGE_PAGES) {
            throw new Error("Conversation history is too large to load")
        }
        const page = await getAllConversationMessages({
            conversation_id,
            cursor,
            limit: 100,
        })
        messages.push(...page.items)
        cursor = page.next_cursor
    } while (cursor)

    return messages
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
