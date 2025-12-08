/**
 * Conversation List Component
 * Displays list of conversations grouped by date
 * Requirements: 6.1, 6.2
 */

import React, { useMemo, useState } from 'react';
import type { Conversation } from '../types';

export interface ConversationListProps {
    conversations: Conversation[];
    currentSessionId: string | null;
    onSelectConversation: (conversationId: string) => void;
    onDeleteConversation?: (conversationId: string) => void;
    className?: string;
}

/**
 * Chat Icon
 */
const ChatIcon: React.FC<{ className?: string }> = ({ className = 'w-4 h-4' }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
        />
    </svg>
);

/**
 * Trash Icon
 */
const TrashIcon: React.FC<{ className?: string }> = ({ className = 'w-3.5 h-3.5' }) => (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
        />
    </svg>
);

/**
 * Format relative time
 */
function formatRelativeTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * Group conversations by date
 */
function groupConversationsByDate(conversations: Conversation[]): Map<string, Conversation[]> {
    const groups = new Map<string, Conversation[]>();
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today.getTime() - 86400000);
    const lastWeek = new Date(today.getTime() - 7 * 86400000);

    for (const conv of conversations) {
        const convDate = new Date(conv.updatedAt);
        let group: string;

        if (convDate >= today) {
            group = 'Today';
        } else if (convDate >= yesterday) {
            group = 'Yesterday';
        } else if (convDate >= lastWeek) {
            group = 'Last 7 days';
        } else {
            group = 'Older';
        }

        if (!groups.has(group)) {
            groups.set(group, []);
        }
        groups.get(group)!.push(conv);
    }

    return groups;
}

/**
 * Conversation Item Component
 */
interface ConversationItemProps {
    conversation: Conversation;
    isSelected: boolean;
    onSelect: () => void;
    onDelete?: () => void;
}

const ConversationItem: React.FC<ConversationItemProps> = ({
    conversation,
    isSelected,
    onSelect,
    onDelete,
}) => {
    const [showDelete, setShowDelete] = useState(false);

    const handleDelete = (e: React.MouseEvent) => {
        e.stopPropagation();
        onDelete?.();
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelect();
        }
    };

    return (
        <div
            role="button"
            tabIndex={0}
            onClick={onSelect}
            onKeyDown={handleKeyDown}
            onMouseEnter={() => setShowDelete(true)}
            onMouseLeave={() => setShowDelete(false)}
            className={`
        w-full flex items-center gap-2 px-3 py-2 rounded-md text-left transition-colors group relative text-sm cursor-pointer
        ${isSelected
                    ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300'
                    : 'hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300'
                }
      `}
            title={conversation.title}
        >
            <ChatIcon className={`w-4 h-4 flex-shrink-0 ${isSelected ? 'text-blue-500' : 'text-gray-400'}`} />

            <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                    <span className="font-medium truncate">
                        {conversation.title || 'New conversation'}
                    </span>
                    {showDelete && onDelete && (
                        <button
                            type="button"
                            onClick={handleDelete}
                            className="p-0.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-gray-400 hover:text-red-500 transition-colors"
                            aria-label="Delete conversation"
                        >
                            <TrashIcon />
                        </button>
                    )}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-gray-500 dark:text-gray-400">
                        {formatRelativeTime(conversation.updatedAt)}
                    </span>
                </div>
            </div>
        </div>
    );
};

export const ConversationList: React.FC<ConversationListProps> = ({
    conversations,
    currentSessionId,
    onSelectConversation,
    onDeleteConversation,
    className = '',
}) => {
    // Sort conversations by updatedAt (most recent first)
    const sortedConversations = useMemo(() => {
        return [...conversations].sort(
            (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
        );
    }, [conversations]);

    // Group conversations by date
    const groupedConversations = useMemo(() => {
        return groupConversationsByDate(sortedConversations);
    }, [sortedConversations]);

    if (sortedConversations.length === 0) {
        return (
            <div className={`text-center py-4 ${className}`}>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                    No conversations yet
                </p>
            </div>
        );
    }

    return (
        <div className={`space-y-4 ${className}`}>
            {Array.from(groupedConversations.entries()).map(([group, convs]) => (
                <div key={group}>
                    <h3 className="text-[10px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wider px-3 mb-1">
                        {group}
                    </h3>
                    <div className="space-y-0.5">
                        {convs.map(conv => (
                            <ConversationItem
                                key={conv.id}
                                conversation={conv}
                                isSelected={conv.id === currentSessionId}
                                onSelect={() => onSelectConversation(conv.id)}
                                onDelete={onDeleteConversation ? () => onDeleteConversation(conv.id) : undefined}
                            />
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
};

export default ConversationList;
