/**
 * Document Store - Manages document state and upload progress
 * Requirements: 2.1, 2.3
 */

import { create } from 'zustand';
import type { Document } from '../types';

interface DocumentState {
  documents: Document[];
  selectedDocumentId: string | null;
  uploadProgress: Map<string, number>;
  isLoading: boolean;
}

interface DocumentActions {
  // Document CRUD actions
  setDocuments: (documents: Document[]) => void;
  addDocument: (document: Document) => void;
  updateDocument: (id: string, updates: Partial<Document>) => void;
  deleteDocument: (id: string) => void;

  // Selection actions
  setSelectedDocument: (id: string | null) => void;

  // Upload progress actions
  setUploadProgress: (fileId: string, progress: number) => void;
  clearUploadProgress: (fileId: string) => void;

  // Loading state
  setLoading: (isLoading: boolean) => void;
}

interface DocumentStore extends DocumentState, DocumentActions {
  selectedDocument: Document | null;
}

export const useDocumentStore = create<DocumentStore>((set, get) => ({
  // State
  documents: [],
  selectedDocumentId: null,
  uploadProgress: new Map(),
  isLoading: false,

  // Computed
  get selectedDocument() {
    const state = get();
    return state.documents.find(d => d.id === state.selectedDocumentId) ?? null;
  },

  // Document CRUD actions
  setDocuments: (documents: Document[]) => {
    set({ documents });
  },

  addDocument: (document: Document) => {
    set(state => ({
      documents: [...state.documents, document],
    }));
  },

  updateDocument: (id: string, updates: Partial<Document>) => {
    set(state => ({
      documents: state.documents.map(d =>
        d.id === id ? { ...d, ...updates } : d
      ),
    }));
  },

  deleteDocument: (id: string) => {
    set(state => ({
      documents: state.documents.filter(d => d.id !== id),
      selectedDocumentId: state.selectedDocumentId === id ? null : state.selectedDocumentId,
    }));
  },

  // Selection actions
  setSelectedDocument: (id: string | null) => {
    set({ selectedDocumentId: id });
  },

  // Upload progress actions
  setUploadProgress: (fileId: string, progress: number) => {
    set(state => {
      const newProgress = new Map(state.uploadProgress);
      newProgress.set(fileId, progress);
      return { uploadProgress: newProgress };
    });
  },

  clearUploadProgress: (fileId: string) => {
    set(state => {
      const newProgress = new Map(state.uploadProgress);
      newProgress.delete(fileId);
      return { uploadProgress: newProgress };
    });
  },

  // Loading state
  setLoading: (isLoading: boolean) => {
    set({ isLoading });
  },
}));
