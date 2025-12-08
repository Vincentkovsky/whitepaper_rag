import axios from 'axios';

const API_URL = '/api/admin';

// Create a configured axios instance if not already available globally
const api = axios.create({
    baseURL: API_URL,
});

// Add interceptor to inject token (simplified, ideally reuse existing api client)
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

export interface ChromaDocument {
    document_id: string;
    user_id: string;
    chunk_count: number;
    created_at: string;
}

export interface ChromaChunk {
    id: string;
    text: string;
    metadata: Record<string, any>;
}

export interface AdminUser {
    id: string;
    email: string;
    name: string | null;
    avatar_url: string | null;
    google_id: string | null;
    is_active: boolean;
    is_superuser: boolean;
    created_at: string;
    updated_at: string;
}

export interface UserUpdateData {
    is_active?: boolean;
    is_superuser?: boolean;
}

export const adminService = {
    // ChromaDB
    listChromaDocuments: async (): Promise<ChromaDocument[]> => {
        const response = await api.get('/chroma/documents');
        return response.data;
    },

    getChromaDocumentChunks: async (documentId: string): Promise<ChromaChunk[]> => {
        const response = await api.get(`/chroma/documents/${documentId}`);
        return response.data;
    },

    // User Management
    listUsers: async (): Promise<AdminUser[]> => {
        const response = await api.get('/users');
        return response.data;
    },

    updateUser: async (userId: string, data: UserUpdateData): Promise<AdminUser> => {
        const response = await api.patch(`/users/${userId}`, data);
        return response.data;
    },
};
