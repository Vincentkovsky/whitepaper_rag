import React, { useEffect, useState } from 'react';
import { adminService, AdminUser } from '../../services/adminService';
import { Loader2, Users, Shield, ShieldOff, UserCheck, UserX } from 'lucide-react';

const UserManagement: React.FC = () => {
    const [users, setUsers] = useState<AdminUser[]>([]);
    const [loading, setLoading] = useState(false);
    const [updating, setUpdating] = useState<string | null>(null);

    useEffect(() => {
        loadUsers();
    }, []);

    const loadUsers = async () => {
        setLoading(true);
        try {
            const data = await adminService.listUsers();
            setUsers(data);
        } catch (error) {
            console.error('Failed to load users:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleToggleActive = async (user: AdminUser) => {
        setUpdating(user.id);
        try {
            const updated = await adminService.updateUser(user.id, {
                is_active: !user.is_active,
            });
            setUsers(users.map(u => u.id === user.id ? updated : u));
        } catch (error) {
            console.error('Failed to update user:', error);
        } finally {
            setUpdating(null);
        }
    };

    const handleToggleSuperuser = async (user: AdminUser) => {
        setUpdating(user.id);
        try {
            const updated = await adminService.updateUser(user.id, {
                is_superuser: !user.is_superuser,
            });
            setUsers(users.map(u => u.id === user.id ? updated : u));
        } catch (error) {
            console.error('Failed to update user:', error);
        } finally {
            setUpdating(null);
        }
    };

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    };

    return (
        <div className="h-[calc(100vh-8rem)] flex flex-col gap-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">User Management</h2>
                    <p className="text-gray-500">Manage user accounts and permissions</p>
                </div>
                <button
                    onClick={loadUsers}
                    className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                    Refresh
                </button>
            </div>

            <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                <div className="p-4 border-b bg-gray-50">
                    <h3 className="font-semibold text-gray-700 flex items-center gap-2">
                        <Users className="w-4 h-4" />
                        Users ({users.length})
                    </h3>
                </div>

                {loading ? (
                    <div className="flex justify-center p-8">
                        <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
                    </div>
                ) : users.length === 0 ? (
                    <div className="text-center p-8 text-gray-500">No users found</div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead className="bg-gray-50 text-left text-sm text-gray-600">
                                <tr>
                                    <th className="px-6 py-3 font-medium">User</th>
                                    <th className="px-6 py-3 font-medium">Email</th>
                                    <th className="px-6 py-3 font-medium">Created</th>
                                    <th className="px-6 py-3 font-medium text-center">Active</th>
                                    <th className="px-6 py-3 font-medium text-center">Admin</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {users.map((user) => (
                                    <tr key={user.id} className="hover:bg-gray-50">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center gap-3">
                                                {user.avatar_url ? (
                                                    <img
                                                        src={user.avatar_url}
                                                        alt={user.name || user.email}
                                                        className="w-8 h-8 rounded-full object-cover"
                                                    />
                                                ) : (
                                                    <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-medium text-sm">
                                                        {(user.name || user.email)[0].toUpperCase()}
                                                    </div>
                                                )}
                                                <div>
                                                    <div className="font-medium text-gray-900">
                                                        {user.name || '-'}
                                                    </div>
                                                    <div className="text-xs text-gray-500">
                                                        {user.id.slice(0, 8)}...
                                                    </div>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-gray-600">{user.email}</td>
                                        <td className="px-6 py-4 text-gray-500 text-sm">
                                            {user.created_at ? formatDate(user.created_at) : '-'}
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <button
                                                onClick={() => handleToggleActive(user)}
                                                disabled={updating === user.id}
                                                className={`p-2 rounded-lg transition-colors ${user.is_active
                                                        ? 'bg-green-50 text-green-600 hover:bg-green-100'
                                                        : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                                                    } disabled:opacity-50`}
                                                title={user.is_active ? 'Active' : 'Inactive'}
                                            >
                                                {updating === user.id ? (
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                ) : user.is_active ? (
                                                    <UserCheck className="w-4 h-4" />
                                                ) : (
                                                    <UserX className="w-4 h-4" />
                                                )}
                                            </button>
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <button
                                                onClick={() => handleToggleSuperuser(user)}
                                                disabled={updating === user.id}
                                                className={`p-2 rounded-lg transition-colors ${user.is_superuser
                                                        ? 'bg-amber-50 text-amber-600 hover:bg-amber-100'
                                                        : 'bg-gray-100 text-gray-400 hover:bg-gray-200'
                                                    } disabled:opacity-50`}
                                                title={user.is_superuser ? 'Superuser' : 'Normal user'}
                                            >
                                                {updating === user.id ? (
                                                    <Loader2 className="w-4 h-4 animate-spin" />
                                                ) : user.is_superuser ? (
                                                    <Shield className="w-4 h-4" />
                                                ) : (
                                                    <ShieldOff className="w-4 h-4" />
                                                )}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default UserManagement;
