/**
 * Layout Component
 * Main application layout with responsive navigation
 * Requirements: 5.1
 */

import React, { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { UserMenu } from './UserMenu';
import { ToastContainer } from './Toast';
import { ConversationList } from './ConversationList';
import { useChatStore } from '../stores/chatStore';
import { storageService } from '../services/storageService';
import type { Conversation } from '../types';

/**
 * Generate a unique ID
 */
function generateId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

interface NavItem {
    label: string;
    path: string;
    icon: React.ReactNode;
    hasSubmenu?: boolean;
}

const NAV_ITEMS: NavItem[] = [
    {
        label: 'Chat',
        path: '/chat',
        hasSubmenu: true,
        icon: (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
        ),
    },
    {
        label: 'Documents',
        path: '/documents',
        icon: (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
        ),
    },
    {
        label: 'Subscription',
        path: '/subscription',
        icon: (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
            </svg>
        ),
    },
];

const Sidebar: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const {
        conversations,
        currentSessionId,
        setConversations,
        addConversation,
        setCurrentSession,
        deleteConversation
    } = useChatStore();

    const [isChatExpanded, setIsChatExpanded] = useState(true);

    // Load conversations on mount
    useEffect(() => {
        const savedConversations = storageService.loadConversations();
        if (savedConversations.length > 0) {
            setConversations(savedConversations);
        }
    }, [setConversations]);

    const handleNewChat = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();

        const newConversation: Conversation = {
            id: generateId(),
            title: 'New conversation',
            documentIds: [],
            messages: [],
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
        };
        addConversation(newConversation);
        setCurrentSession(newConversation.id);
        setIsChatExpanded(true);
        navigate(`/chat/${newConversation.id}`);
    };

    const handleSelectConversation = (id: string) => {
        setCurrentSession(id);
        navigate(`/chat/${id}`);
    };

    const handleDeleteConversation = (id: string) => {
        deleteConversation(id);
        if (currentSessionId === id) {
            navigate('/chat');
        }
    };

    const toggleChat = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsChatExpanded(!isChatExpanded);
    };

    return (
        <aside className="hidden md:flex flex-col w-64 h-screen bg-[var(--bg-secondary)] border-r border-[var(--border-color)]">
            {/* Logo */}
            <div className="flex items-center h-16 px-6 border-b border-[var(--border-color)]">
                <img src="/logo.png" alt="Kiro Logo" className="w-12 h-12 mr-3" />
                <span className="text-lg font-bold text-[var(--text-primary)]">Prism</span>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
                {NAV_ITEMS.map((item) => (
                    <div key={item.path}>
                        {item.hasSubmenu ? (
                            <div className="space-y-1">
                                <div className="flex items-center justify-between px-3 py-2 rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)] cursor-pointer group">
                                    <NavLink
                                        to={item.path}
                                        className={({ isActive }) =>
                                            `flex items-center gap-3 flex-1 ${isActive || location.pathname.startsWith('/chat')
                                                ? 'text-primary-600 dark:text-primary-400 font-medium'
                                                : ''
                                            }`
                                        }
                                        onClick={(e) => {
                                            // If clicking Chat link itself, just navigate to /chat (new chat)
                                            if (location.pathname.startsWith('/chat')) {
                                                e.preventDefault();
                                            }
                                            setIsChatExpanded(true);
                                        }}
                                    >
                                        {item.icon}
                                        <span>{item.label}</span>
                                    </NavLink>

                                    <div className="flex items-center gap-1">
                                        {/* New Chat Button (Small) */}
                                        <button
                                            onClick={handleNewChat}
                                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-primary-500 transition-colors"
                                            title="New Chat"
                                        >
                                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                            </svg>
                                        </button>

                                        {/* Expand/Collapse Toggle */}
                                        <button
                                            onClick={toggleChat}
                                            className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 transition-colors"
                                        >
                                            <svg
                                                className={`w-4 h-4 transition-transform duration-200 ${isChatExpanded ? 'rotate-180' : ''}`}
                                                fill="none"
                                                stroke="currentColor"
                                                viewBox="0 0 24 24"
                                            >
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                            </svg>
                                        </button>
                                    </div>
                                </div>

                                {/* Submenu (Conversation List) */}
                                {isChatExpanded && (
                                    <div className="pl-2 pr-1 pb-2">
                                        <ConversationList
                                            conversations={conversations}
                                            currentSessionId={currentSessionId}
                                            onSelectConversation={handleSelectConversation}
                                            onDeleteConversation={handleDeleteConversation}
                                        />
                                    </div>
                                )}
                            </div>
                        ) : (
                            <NavLink
                                to={item.path}
                                className={({ isActive }) =>
                                    `flex items-center gap-3 px-3 py-2 rounded-lg transition-colors duration-200 ${isActive
                                        ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/20 dark:text-primary-300'
                                        : 'text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-primary)]'
                                    }`
                                }
                            >
                                {item.icon}
                                <span className="font-medium">{item.label}</span>
                            </NavLink>
                        )}
                    </div>
                ))}
            </nav>

            {/* User Menu */}
            <div className="p-4 border-t border-[var(--border-color)]">
                <div className="flex items-center justify-between px-2">
                    <UserMenu />
                </div>
            </div>
        </aside>
    );
};

const BottomNav: React.FC = () => {
    return (
        <nav className="md:hidden fixed bottom-0 left-0 right-0 h-16 bg-[var(--bg-secondary)] border-t border-[var(--border-color)] flex items-center justify-around px-2 z-40">
            {NAV_ITEMS.map((item) => (
                <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) =>
                        `flex flex-col items-center justify-center w-full h-full space-y-1 ${isActive
                            ? 'text-primary-600 dark:text-primary-400'
                            : 'text-[var(--text-secondary)]'
                        }`
                    }
                >
                    {item.icon}
                    <span className="text-xs font-medium">{item.label}</span>
                </NavLink>
            ))}
            <div className="flex flex-col items-center justify-center w-full h-full">
                <UserMenu />
            </div>
        </nav>
    );
};

export const Layout: React.FC = () => {
    return (
        <div className="flex h-screen bg-[var(--bg-primary)] text-[var(--text-primary)] overflow-hidden">
            <Sidebar />

            <main className="flex-1 flex flex-col min-w-0 overflow-hidden relative">
                {/* Mobile Header */}
                <header className="md:hidden flex items-center justify-between h-14 px-4 border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
                    <div className="flex items-center">
                        <img src="/logo.png" alt="Kiro Logo" className="w-6 h-6 mr-2" />
                        <span className="font-bold text-[var(--text-primary)]">Kiro</span>
                    </div>
                </header>

                {/* Content Area */}
                <div className="flex-1 overflow-hidden">
                    <Outlet />
                </div>

                {/* Bottom Navigation for Mobile */}
                <div className="md:hidden h-16" /> {/* Spacer for fixed bottom nav */}
                <BottomNav />
            </main>

            <ToastContainer />
        </div>
    );
};

export default Layout;
