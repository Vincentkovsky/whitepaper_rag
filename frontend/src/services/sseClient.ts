/**
 * SSE Client - Server-Sent Events client for streaming agent responses
 * Requirements: 3.2
 */

import { useAuthStore } from '../stores/authStore';
import type { Citation } from '../types';

/**
 * SSE Event Types
 */
export type SSEEventType = 'thinking' | 'tool_call' | 'tool_result' | 'answer' | 'error' | 'done';

export interface SSEThinkingEvent {
  type: 'thinking';
  content: string;
}

export interface SSEToolCallEvent {
  type: 'tool_call';
  tool: string;
  input: unknown;
}

export interface SSEToolResultEvent {
  type: 'tool_result';
  tool: string;
  result: unknown;
}

export interface SSEAnswerEvent {
  type: 'answer';
  content: string;
  sources?: Citation[];
}

export interface SSEErrorEvent {
  type: 'error';
  message: string;
}

export interface SSEDoneEvent {
  type: 'done';
}

export type SSEEvent =
  | SSEThinkingEvent
  | SSEToolCallEvent
  | SSEToolResultEvent
  | SSEAnswerEvent
  | SSEErrorEvent
  | SSEDoneEvent;

/**
 * SSE Client Options
 */
export interface SSEClientOptions {
  onThinking?: (content: string) => void;
  onToolCall?: (tool: string, input: unknown) => void;
  onToolResult?: (tool: string, result: unknown) => void;
  onAnswer?: (content: string, sources?: Citation[]) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
  onConnectionError?: (error: Error) => void;
}


/**
 * Parse SSE event data
 */
export const parseSSEEvent = (data: string): SSEEvent | null => {
  try {
    const parsed = JSON.parse(data);

    // Backend sends 'event_type' not 'type'
    const eventType = parsed.event_type || parsed.type;
    if (!eventType) {
      return null;
    }

    switch (eventType) {
      case 'thinking':
        return { type: 'thinking', content: parsed.content || '' };
      case 'tool_call':
        return { type: 'tool_call', tool: parsed.tool || parsed.metadata?.tool || '', input: parsed.metadata?.input || parsed.input };
      case 'tool_result':
        return { type: 'tool_result', tool: parsed.tool || parsed.metadata?.tool || '', result: parsed.result || parsed.content };
      case 'answer':
        return { type: 'answer', content: parsed.content || '', sources: parsed.sources || parsed.metadata?.sources };
      case 'error':
        return { type: 'error', message: parsed.message || parsed.content || 'Unknown error' };
      case 'done':
        return { type: 'done' };
      default:
        return null;
    }
  } catch {
    return null;
  }
};

/**
 * SSE Client Class
 */
export class SSEClient {
  private abortController: AbortController | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 3;
  private baseReconnectDelay = 1000;
  private isAborted = false;

  /**
   * Connect to SSE endpoint
   */
  async connect(
    url: string,
    body: object,
    options: SSEClientOptions
  ): Promise<void> {
    this.isAborted = false;
    this.reconnectAttempts = 0;
    await this.doConnect(url, body, options);
  }

  private async doConnect(
    url: string,
    body: object,
    options: SSEClientOptions
  ): Promise<void> {
    if (this.isAborted) return;

    this.abortController = new AbortController();
    const { accessToken } = useAuthStore.getState();

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
    };

    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      await this.processStream(response.body, options);
    } catch (error) {
      if (this.isAborted) return;

      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }

      // Attempt reconnection with exponential backoff
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        await new Promise(resolve => setTimeout(resolve, delay));
        await this.doConnect(url, body, options);
        return;
      }

      options.onConnectionError?.(error instanceof Error ? error : new Error(String(error)));
    }
  }


  /**
   * Process the SSE stream
   */
  private async processStream(
    body: ReadableStream<Uint8Array>,
    options: SSEClientOptions
  ): Promise<void> {
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        if (this.isAborted) break;

        const { done, value } = await reader.read();

        if (done) {
          options.onDone?.();
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE messages
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();

            if (data === '[DONE]') {
              options.onDone?.();
              return;
            }

            const event = parseSSEEvent(data);
            if (event) {
              this.dispatchEvent(event, options);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  /**
   * Dispatch parsed event to appropriate handler
   */
  private dispatchEvent(event: SSEEvent, options: SSEClientOptions): void {
    switch (event.type) {
      case 'thinking':
        options.onThinking?.(event.content);
        break;
      case 'tool_call':
        options.onToolCall?.(event.tool, event.input);
        break;
      case 'tool_result':
        options.onToolResult?.(event.tool, event.result);
        break;
      case 'answer':
        options.onAnswer?.(event.content, event.sources);
        break;
      case 'error':
        options.onError?.(event.message);
        break;
      case 'done':
        options.onDone?.();
        break;
    }
  }

  /**
   * Abort the current connection
   */
  abort(): void {
    this.isAborted = true;
    this.abortController?.abort();
    this.abortController = null;
  }

  /**
   * Check if client is currently connected
   */
  isConnected(): boolean {
    return this.abortController !== null && !this.isAborted;
  }
}

/**
 * Create a new SSE client instance
 */
export const createSSEClient = (): SSEClient => new SSEClient();

export default SSEClient;
