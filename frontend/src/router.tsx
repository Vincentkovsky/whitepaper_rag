/**
 * Router Configuration
 * Defines application routes and protection logic
 * Requirements: 1.1
 */

import { createBrowserRouter, Navigate } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AuthGuard } from './components/AuthGuard';
import { Login } from './pages/Login';
import { ChatWorkbench } from './pages/ChatWorkbench';
import { Documents } from './pages/Documents';
import { Subscription } from './pages/Subscription';

export const router = createBrowserRouter([
    {
        path: '/login',
        element: <Login />,
    },
    {
        path: '/',
        element: (
            <AuthGuard>
                <Layout />
            </AuthGuard>
        ),
        children: [
            {
                index: true,
                element: <Navigate to="/chat" replace />,
            },
            {
                path: 'chat',
                element: <ChatWorkbench />,
            },
            {
                path: 'chat/:sessionId',
                element: <ChatWorkbench />,
            },
            {
                path: 'documents',
                element: <Documents />,
            },
            {
                path: 'subscription',
                element: <Subscription />,
            },
        ],
    },
    {
        path: '*',
        element: <Navigate to="/" replace />,
    },
]);
