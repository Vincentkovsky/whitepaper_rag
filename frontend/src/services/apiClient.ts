/**
 * API Client - Centralized HTTP client with auth headers and error handling
 * Requirements: 5.3
 */

import { useAuthStore } from '../stores/authStore';

export interface ApiError {
  status: number;
  message: string;
  details?: unknown;
}

export class ApiClientError extends Error {
  status: number;
  details?: unknown;

  constructor(status: number, message: string, details?: unknown) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.details = details;
  }
}

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  retries?: number;
  retryDelay?: number;
}

const DEFAULT_RETRIES = 3;
const DEFAULT_RETRY_DELAY = 1000;
const RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504];

/**
 * Sleep utility for retry delays
 */
const sleep = (ms: number): Promise<void> => 
  new Promise(resolve => setTimeout(resolve, ms));

/**
 * Get the base URL for API requests
 */
const getBaseUrl = (): string => {
  return import.meta.env.VITE_API_BASE_URL || '/api';
};

/**
 * Get authorization headers from auth store
 */
const getAuthHeaders = (): Record<string, string> => {
  const { accessToken } = useAuthStore.getState();
  if (accessToken) {
    return { Authorization: `Bearer ${accessToken}` };
  }
  return {};
};


/**
 * Parse response based on content type
 */
const parseResponse = async <T>(response: Response): Promise<T> => {
  const contentType = response.headers.get('content-type');
  
  if (contentType?.includes('application/json')) {
    return response.json() as Promise<T>;
  }
  
  // Return text for non-JSON responses
  return response.text() as unknown as T;
};

/**
 * Handle error responses
 */
const handleErrorResponse = async (response: Response): Promise<never> => {
  let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
  let details: unknown;

  try {
    const errorBody = await response.json();
    errorMessage = errorBody.message || errorBody.error || errorMessage;
    details = errorBody;
  } catch {
    // Response body is not JSON, use default message
  }

  throw new ApiClientError(response.status, errorMessage, details);
};

/**
 * Determine if a request should be retried
 */
const shouldRetry = (error: unknown, attempt: number, maxRetries: number): boolean => {
  if (attempt >= maxRetries) return false;
  
  if (error instanceof ApiClientError) {
    return RETRYABLE_STATUS_CODES.includes(error.status);
  }
  
  // Retry on network errors
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return true;
  }
  
  return false;
};

/**
 * Make an HTTP request with retry logic
 */
async function request<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const {
    retries = DEFAULT_RETRIES,
    retryDelay = DEFAULT_RETRY_DELAY,
    body,
    headers = {},
    ...fetchOptions
  } = options;

  const url = `${getBaseUrl()}${endpoint}`;
  
  const requestHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getAuthHeaders(),
    ...(headers as Record<string, string>),
  };

  const config: RequestInit = {
    ...fetchOptions,
    headers: requestHeaders,
  };

  if (body !== undefined) {
    config.body = JSON.stringify(body);
  }

  let lastError: unknown;
  
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        await handleErrorResponse(response);
      }
      
      return await parseResponse<T>(response);
    } catch (error) {
      lastError = error;
      
      if (shouldRetry(error, attempt, retries)) {
        // Exponential backoff
        const delay = retryDelay * Math.pow(2, attempt);
        await sleep(delay);
        continue;
      }
      
      throw error;
    }
  }

  throw lastError;
}


/**
 * API Client with convenience methods for common HTTP verbs
 */
export const apiClient = {
  /**
   * Get the base URL for API requests
   */
  getBaseUrl,

  /**
   * GET request
   */
  get: <T>(endpoint: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> => {
    return request<T>(endpoint, { ...options, method: 'GET' });
  },

  /**
   * POST request
   */
  post: <T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> => {
    return request<T>(endpoint, { ...options, method: 'POST', body });
  },

  /**
   * PUT request
   */
  put: <T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> => {
    return request<T>(endpoint, { ...options, method: 'PUT', body });
  },

  /**
   * PATCH request
   */
  patch: <T>(endpoint: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> => {
    return request<T>(endpoint, { ...options, method: 'PATCH', body });
  },

  /**
   * DELETE request
   */
  delete: <T>(endpoint: string, options?: Omit<RequestOptions, 'method' | 'body'>): Promise<T> => {
    return request<T>(endpoint, { ...options, method: 'DELETE' });
  },

  /**
   * Upload file with progress tracking
   */
  upload: async <T>(
    endpoint: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<T> => {
    const url = `${getBaseUrl()}${endpoint}`;
    const formData = new FormData();
    formData.append('file', file);

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = Math.round((event.loaded / event.total) * 100);
          onProgress(progress);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response as T);
          } catch {
            resolve(xhr.responseText as unknown as T);
          }
        } else {
          reject(new ApiClientError(xhr.status, xhr.statusText || 'Upload failed'));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new ApiClientError(0, 'Network error during upload'));
      });

      xhr.addEventListener('abort', () => {
        reject(new ApiClientError(0, 'Upload aborted'));
      });

      xhr.open('POST', url);
      
      // Add auth headers
      const authHeaders = getAuthHeaders();
      Object.entries(authHeaders).forEach(([key, value]) => {
        xhr.setRequestHeader(key, value);
      });

      xhr.send(formData);
    });
  },
};

export default apiClient;
