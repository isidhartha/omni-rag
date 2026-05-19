export interface OmniRAGOptions { host?: string; timeout?: number; }
export interface ChatResponse { answer: string; sources: Array<{ document: string; page?: number; excerpt: string }>; }
export declare class OmniRAGClient {
  constructor(options?: OmniRAGOptions);
  ingest(filePath: string, metadata?: object): Promise<{ id: string; chunks: number }>;
  chat(query: string, conversationId?: string | null): Promise<ChatResponse>;
  listDocuments(): Promise<any[]>;
  deleteDocument(id: string): Promise<void>;
  health(): Promise<{ status: string }>;
}
export default OmniRAGClient;
