import React, { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import clsx from "clsx";
import CitationViewer from "./CitationViewer";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  loading?: boolean;
}

interface Citation {
  doc_id: string;
  filename: string;
  chunk_id: string;
  page_number?: number;
  section?: string;
  text_excerpt: string;
  relevance_score: number;
}

interface Props {
  activeDocIds?: string[];
}

const WS_URL =
  typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/chat`
    : "ws://localhost:8000/ws/chat";

export default function ChatWithDocs({ activeDocIds }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [wsReady, setWsReady] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const pendingMsgIdRef = useRef<string | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function connectWS() {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    setConnecting(true);
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsReady(true);
      setConnecting(false);
    };

    ws.onclose = () => {
      setWsReady(false);
      setConnecting(false);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      const pendingId = pendingMsgIdRef.current;

      if (data.type === "answer_chunk" && pendingId) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === pendingId ? { ...m, content: m.content + data.content, loading: false } : m
          )
        );
      } else if (data.type === "done" && pendingId) {
        const citations: Citation[] = data.citations || [];
        setMessages((prev) =>
          prev.map((m) => (m.id === pendingId ? { ...m, citations, loading: false } : m))
        );
        pendingMsgIdRef.current = null;
      } else if (data.type === "error") {
        if (pendingId) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === pendingId
                ? { ...m, content: `Error: ${data.message}`, loading: false }
                : m
            )
          );
        }
      }
    };
  }

  async function sendMessage(e: React.FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question) return;

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connectWS();
      // Small delay to allow connection
      await new Promise((r) => setTimeout(r, 800));
    }

    const userMsgId = crypto.randomUUID();
    const asstMsgId = crypto.randomUUID();
    pendingMsgIdRef.current = asstMsgId;

    setMessages((prev) => [
      ...prev,
      { id: userMsgId, role: "user", content: question },
      { id: asstMsgId, role: "assistant", content: "", loading: true },
    ]);
    setInput("");

    wsRef.current?.send(
      JSON.stringify({ question, doc_ids: activeDocIds?.length ? activeDocIds : undefined })
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 p-4">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <Bot size={40} className="mx-auto text-gray-700 mb-3" />
            <p className="text-gray-500 text-sm">
              Ask anything about your documents. OmniRAG will retrieve relevant context and cite its sources.
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={clsx("flex gap-3", msg.role === "user" ? "flex-row-reverse" : "flex-row")}
          >
            <div
              className={clsx(
                "w-7 h-7 rounded-full flex items-center justify-center shrink-0 mt-1",
                msg.role === "user" ? "bg-brand-600" : "bg-gray-700"
              )}
            >
              {msg.role === "user" ? <User size={14} /> : <Bot size={14} />}
            </div>
            <div className={clsx("max-w-[80%] space-y-2", msg.role === "user" ? "items-end" : "items-start")}>
              <div
                className={clsx(
                  "rounded-xl px-4 py-3 text-sm",
                  msg.role === "user"
                    ? "bg-brand-600 text-white"
                    : "bg-gray-800 text-gray-200 border border-gray-700"
                )}
              >
                {msg.loading ? (
                  <div className="flex items-center gap-2 text-gray-400">
                    <Loader size={14} className="animate-spin" />
                    <span>Thinking...</span>
                  </div>
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]} className="prose prose-invert prose-sm max-w-none">
                    {msg.content || " "}
                  </ReactMarkdown>
                )}
              </div>
              {msg.citations && msg.citations.length > 0 && (
                <CitationViewer citations={msg.citations} />
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-800 p-4">
        {!wsReady && (
          <div className="mb-2 text-center">
            <button
              className="btn-secondary text-xs"
              onClick={connectWS}
              disabled={connecting}
            >
              {connecting ? "Connecting..." : "Connect to chat"}
            </button>
          </div>
        )}
        <form onSubmit={sendMessage} className="flex gap-2">
          <input
            className="input"
            placeholder="Ask about your documents..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!wsReady && !connecting}
          />
          <button
            className="btn-primary shrink-0"
            disabled={!input.trim() || (!wsReady && !connecting)}
          >
            <Send size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
