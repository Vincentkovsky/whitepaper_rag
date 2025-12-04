import React, { useEffect, useState } from 'react';
import { adminService, ChromaDocument, ChromaChunk } from '../../services/adminService';
import { Loader2, FileText, Database } from 'lucide-react';

const ChromaViewer: React.FC = () => {
    const [documents, setDocuments] = useState<ChromaDocument[]>([]);
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
    const [chunks, setChunks] = useState<ChromaChunk[]>([]);
    const [loadingDocs, setLoadingDocs] = useState(false);
    const [loadingChunks, setLoadingChunks] = useState(false);

    useEffect(() => {
        loadDocuments();
    }, []);

    useEffect(() => {
        if (selectedDocId) {
            loadChunks(selectedDocId);
        } else {
            setChunks([]);
        }
    }, [selectedDocId]);

    const loadDocuments = async () => {
        setLoadingDocs(true);
        try {
            const data = await adminService.listChromaDocuments();
            setDocuments(data);
        } catch (error) {
            console.error('Failed to load documents:', error);
        } finally {
            setLoadingDocs(false);
        }
    };

    const loadChunks = async (docId: string) => {
        setLoadingChunks(true);
        try {
            const data = await adminService.getChromaDocumentChunks(docId);
            setChunks(data);
        } catch (error) {
            console.error('Failed to load chunks:', error);
        } finally {
            setLoadingChunks(false);
        }
    };

    return (
        <div className="h-[calc(100vh-8rem)] flex flex-col gap-6">
            <div className="flex justify-between items-center">
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">Vector Store Inspector</h2>
                    <p className="text-gray-500">View documents and chunks stored in ChromaDB</p>
                </div>
                <button
                    onClick={loadDocuments}
                    className="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                    Refresh
                </button>
            </div>

            <div className="flex-1 flex gap-6 min-h-0">
                {/* Document List */}
                <div className="w-1/3 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col overflow-hidden">
                    <div className="p-4 border-b bg-gray-50">
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2">
                            <Database className="w-4 h-4" />
                            Documents ({documents.length})
                        </h3>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-2">
                        {loadingDocs ? (
                            <div className="flex justify-center p-8">
                                <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
                            </div>
                        ) : documents.length === 0 ? (
                            <div className="text-center p-8 text-gray-500">No documents found</div>
                        ) : (
                            documents.map((doc) => (
                                <div
                                    key={doc.document_id}
                                    onClick={() => setSelectedDocId(doc.document_id)}
                                    className={`p-3 rounded-lg cursor-pointer border transition-all ${selectedDocId === doc.document_id
                                        ? 'bg-indigo-50 border-indigo-200 shadow-sm'
                                        : 'bg-white border-transparent hover:bg-gray-50 hover:border-gray-200'
                                        }`}
                                >
                                    <div className="flex justify-between items-start mb-1">
                                        <span className="font-medium text-gray-900 truncate" title={doc.document_id}>
                                            {doc.document_id.slice(0, 8)}...
                                        </span>
                                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">
                                            {doc.chunk_count} chunks
                                        </span>
                                    </div>
                                    <div className="text-xs text-gray-500 truncate">User: {doc.user_id}</div>
                                    <div className="text-xs text-gray-400 mt-1">
                                        {new Date(doc.created_at).toLocaleString()}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Chunk Details */}
                <div className="flex-1 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col overflow-hidden">
                    <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
                        <h3 className="font-semibold text-gray-700 flex items-center gap-2">
                            <FileText className="w-4 h-4" />
                            Chunks {selectedDocId && `for ${selectedDocId.slice(0, 8)}...`}
                        </h3>
                        {chunks.length > 0 && (
                            <span className="text-xs text-gray-500">{chunks.length} items</span>
                        )}
                    </div>
                    <div className="flex-1 overflow-y-auto p-4">
                        {!selectedDocId ? (
                            <div className="h-full flex flex-col items-center justify-center text-gray-400">
                                <Database className="w-12 h-12 mb-4 opacity-20" />
                                <p>Select a document to view its chunks</p>
                            </div>
                        ) : loadingChunks ? (
                            <div className="flex justify-center p-8">
                                <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
                            </div>
                        ) : chunks.length === 0 ? (
                            <div className="text-center p-8 text-gray-500">No chunks found for this document</div>
                        ) : (
                            <div className="space-y-4">
                                {chunks.map((chunk) => (
                                    <div key={chunk.id} className="border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow">
                                        <div className="flex justify-between items-center mb-2">
                                            <span className="text-xs font-mono text-gray-500 bg-gray-100 px-2 py-1 rounded">
                                                {chunk.id}
                                            </span>
                                        </div>
                                        <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                                            {chunk.text}
                                        </p>
                                        {Object.keys(chunk.metadata).length > 0 && (
                                            <div className="mt-3 pt-3 border-t border-gray-100">
                                                <details className="text-xs">
                                                    <summary className="cursor-pointer text-gray-500 hover:text-indigo-600 font-medium">
                                                        View Metadata
                                                    </summary>
                                                    <pre className="mt-2 bg-gray-50 p-2 rounded text-gray-600 overflow-x-auto">
                                                        {JSON.stringify(chunk.metadata, null, 2)}
                                                    </pre>
                                                </details>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ChromaViewer;
