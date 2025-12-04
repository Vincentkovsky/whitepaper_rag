import { createBrowserRouter, Navigate } from 'react-router-dom';
import Login from "./pages/Login";
import Register from "./pages/Register";
import AuthCallback from "./pages/AuthCallback";
import Layout from "./components/Layout";
import Documents from "./pages/Documents";
import ChatWorkbench from "./pages/ChatWorkbench";
import authService from "./services/authService";
import AdminLayout from './components/admin/AdminLayout';
import ChromaViewer from './pages/admin/ChromaViewer';

// Auth guard component
function AuthGuard({ children }: { children: React.ReactNode }) {
    if (!authService.isAuthenticated()) {
        return <Navigate to="/login" replace />;
    }
    return <>{children}</>;
}

export const router = createBrowserRouter([
    {
        path: '/',
        element: <Layout />,
        children: [
            {
                index: true,
                element: <Navigate to="/documents" replace />,
            },
            {
                path: 'documents',
                element: (
                    <AuthGuard>
                        <Documents />
                    </AuthGuard>
                ),
            },
            {
                path: 'chat/:documentId',
                element: (
                    <AuthGuard>
                        <ChatWorkbench />
                    </AuthGuard>
                ),
            },
            {
                path: '/login',
                element: <Login />,
            },
            {
                path: '/register',
                element: <Register />,
            },
            {
                path: '/auth/callback',
                element: <AuthCallback />,
            },
        ],
    },
    {
        path: '/admin',
        element: (
            <AuthGuard>
                <AdminLayout />
            </AuthGuard>
        ),
        children: [
            {
                path: 'chroma',
                element: <ChromaViewer />,
            },
            {
                index: true,
                element: <Navigate to="chroma" replace />,
            },
        ],
    },
]);
