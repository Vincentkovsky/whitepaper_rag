import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { authService } from '../services/authService';

export default function AuthCallback() {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { login } = useAuthStore();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const processCallback = async () => {
            const token = searchParams.get('token');

            if (token) {
                try {
                    // Save token to localStorage for persistence
                    localStorage.setItem('auth_token', token);

                    // Fetch user info
                    const userResponse = await authService.getCurrentUser();

                    // Map backend response to frontend User type
                    const user = {
                        id: userResponse.id,
                        email: userResponse.email,
                        name: userResponse.name,
                        avatarUrl: userResponse.avatar_url
                    };

                    // Update authStore with user and token
                    login(user, token);

                    // Redirect to home
                    navigate('/');
                } catch (err) {
                    console.error('Auth callback error:', err);
                    setError('Failed to process authentication');
                    setTimeout(() => navigate('/login'), 2000);
                }
            } else {
                setError('No authentication token received');
                setTimeout(() => navigate('/login'), 2000);
            }
        };

        processCallback();
    }, [searchParams, navigate, login]);

    return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="text-center">
                {error ? (
                    <>
                        <h2 className="text-2xl font-semibold mb-2 text-red-600">Authentication Error</h2>
                        <p className="text-gray-600">{error}</p>
                        <p className="text-sm text-gray-500 mt-2">Redirecting to login...</p>
                    </>
                ) : (
                    <>
                        <h2 className="text-2xl font-semibold mb-2">Authenticating...</h2>
                        <p className="text-gray-600">Please wait while we complete your sign-in.</p>
                    </>
                )}
            </div>
        </div>
    );
}
