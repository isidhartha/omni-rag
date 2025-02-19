import React, { useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import clsx from "clsx";

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
  citations: Citation[];
}

export default function CitationViewer({ citations }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  if (!citations || citations.length === 0) return null;

  return (
    <div className="w-full">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-200 transition-colors"
      >
        <BookOpen size={12} />
        <span>{citations.length} source{citations.length !== 1 ? "s" : ""}</span>
        {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>

      {expanded && (
        <div className="mt-2 space-y-2">
          {citations.map((c, idx) => (
            <div
              key={c.chunk_id}
              className="bg-gray-800/60 border border-gray-700 rounded-lg overflow-hidden"
            >
              {/* Header */}
              <button
                onClick={() => setOpenId(openId === c.chunk_id ? null : c.chunk_id)}
                className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-800 transition-colors"
              >
                <span className="w-5 h-5 rounded-full bg-brand-600/30 text-brand-400 text-xs flex items-center justify-center shrink-0 font-medium">
                  {idx + 1}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-200 truncate">{c.filename}</p>
                  <p className="text-xs text-gray-500">
                    {c.page_number ? `Page ${c.page_number}` : ""}
                    {c.section ? ` · ${c.section}` : ""}
                    {" · "}
                    <span className="text-brand-500">{(c.relevance_score * 100).toFixed(0)}% relevant</span>
                  </p>
                </div>
                {openId === c.chunk_id ? <ChevronUp size={12} className="text-gray-500 shrink-0" /> : <ChevronDown size={12} className="text-gray-500 shrink-0" />}
              </button>

              {/* Excerpt */}
              {openId === c.chunk_id && (
                <div className="px-3 pb-3 border-t border-gray-700">
                  <p className="text-xs text-gray-300 leading-relaxed mt-2 font-mono bg-gray-900 rounded p-2 whitespace-pre-wrap">
                    {c.text_excerpt}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
