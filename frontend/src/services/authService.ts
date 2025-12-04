import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

interface LoginCredentials {
    email: string;
    password: string;
}

interface RegisterData {
    email: string;
    password: string;
    name?: string;
}

interface TokenResponse {
    access_token: string;
    token_type: string;
}

interface UserResponse {
    id: string;
    email: string;
    name?: string;
    avatar_url?: string;
}

class AuthService {
    private TOKEN_KEY = 'auth_token';

    getToken(): string | null {
        return localStorage.getItem(this.TOKEN_KEY);
    }

    setToken(token: string): void {
        localStorage.setItem(this.TOKEN_KEY, token);
    }

    clearToken(): void {
        localStorage.removeItem(this.TOKEN_KEY);
    }

    async register(data: RegisterData): Promise<TokenResponse> {
        const response = await axios.post<TokenResponse>(`${API_BASE}/auth/register`, data);
        this.setToken(response.data.access_token);
        return response.data;
    }

    async login(credentials: LoginCredentials): Promise<TokenResponse> {
        const response = await axios.post<TokenResponse>(`${API_BASE}/auth/login`, credentials);
        this.setToken(response.data.access_token);
        return response.data;
    }

    async loginWithGoogle(): Promise<void> {
        // Redirect to backend Google OAuth endpoint
        window.location.href = `${API_BASE}/auth/google/login`;
    }

    async handleGoogleCallback(token: string): Promise<void> {
        this.setToken(token);
    }

    async getCurrentUser(): Promise<UserResponse> {
        const token = this.getToken();
        if (!token) {
            throw new Error('Not authenticated');
        }

        const response = await axios.get<UserResponse>(`${API_BASE}/auth/me`, {
            headers: {
                Authorization: `Bearer ${token}`,
            },
        });
        return response.data;
    }

    logout(): void {
        this.clearToken();
    }

    isAuthenticated(): boolean {
        return !!this.getToken();
    }
}

export const authService = new AuthService();
export default authService;
