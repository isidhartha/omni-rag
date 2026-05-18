import React, { useState } from "react";
import { Search, SlidersHorizontal, Zap, Brain } from "lucide-react";
import axios from "axios";
import clsx from "clsx";
import CitationViewer from "./CitationViewer";

const API_BASE = "/api/v1";

export interface SearchResult {
  chunk_id: string;
  text: string;
  score: number;
  doc_id: string;
  filename: string;
  doc_type: string;
  metadata: {
    page_number?: number;
    source?: string;
    section?: string;
    language?: string;
  };
}

interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  elapsed_ms: number;
}

type SearchMode = "semantic" | "hybrid";

interface Props {
  activeDocIds?: string[];
}

export default function SearchInterface({ activeDocIds }: Props) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const payload = {
        query: query.trim(),
        top_k: 10,
        doc_ids: activeDocIds?.length ? activeDocIds : undefined,
      };
      const endpoint = mode === "semantic" ? `${API_BASE}/search/semantic` : `${API_BASE}/search/hybrid`;
      const res = await axios.post<SearchResponse>(endpoint, payload);
      setResults(res.data.results);
      setElapsed(res.data.elapsed_ms);
    } catch (err: unknown) {
      setError(axios.isAxiosError(err) ? (err.response?.data?.detail || err.message) : String(err));
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Search Form */}
      <form onSubmit={handleSearch} className="space-y-3">
        <div className="flex gap-2">
          <div className="flex-1 relative">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none"
            />
            <input
              className="input pl-9"
              placeholder="Search across all knowledge sources..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
            />
          </div>
          <button className="btn-primary flex items-center gap-2" disabled={loading || !query.trim()}>
            {loading ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Search size={16} />
            )}
            Search
          </button>
        </div>

        {/* Mode selector */}
        <div className="flex items-center gap-2">
          <SlidersHorizontal size={14} className="text-gray-500" />
          <span className="text-xs text-gray-500">Mode:</span>
          {(["hybrid", "semantic"] as SearchMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              className={clsx(
                "text-xs px-3 py-1 rounded-full border transition-colors",
                mode === m
                  ? "bg-brand-600 border-brand-600 text-white"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              )}
            >
              {m === "hybrid" ? (
                <span className="flex items-center gap-1"><Zap size={10} /> Hybrid</span>
              ) : (
                <span className="flex items-center gap-1"><Brain size={10} /> Semantic</span>
              )}
            </button>
          ))}
        </div>
      </form>

      {/* Error */}
      {error && (
        <div className="bg-red-900/20 border border-red-800 rounded-lg px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500">
            {results.length} results &middot; {elapsed?.toFixed(0)} ms &middot; {mode} search
          </p>
          {results.map((r) => (
            <div key={r.chunk_id} className="card hover:border-gray-700 transition-colors">
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="text-sm font-medium text-brand-400 truncate">{r.filename}</p>
                <span className="badge bg-gray-800 text-gray-400 shrink-0">
                  {(r.score * 100).toFixed(1)}%
                </span>
              </div>
              {r.metadata.page_number && (
                <p className="text-xs text-gray-500 mb-1">Page {r.metadata.page_number}</p>
              )}
              {r.metadata.language && (
                <span className="badge bg-blue-900/30 text-blue-400 mb-2">{r.metadata.language}</span>
              )}
              <p className="text-sm text-gray-300 leading-relaxed line-clamp-4">{r.text}</p>
            </div>
          ))}
        </div>
      )}

      {results.length === 0 && !loading && elapsed !== null && (
        <p className="text-sm text-gray-500 text-center py-8">
          No results found for "{query}". Try different keywords or upload more documents.
        </p>
      )}
    </div>
  );
}
