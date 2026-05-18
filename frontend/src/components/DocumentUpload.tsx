import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, Image, Code, Music, Video, X, CheckCircle, AlertCircle, Loader } from "lucide-react";
import clsx from "clsx";
import axios from "axios";
import type { Document } from "../App";

const API_BASE = "/api/v1";

interface UploadStatus {
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  message?: string;
  docId?: string;
}

interface Props {
  onDocumentAdded: (doc: Document) => void;
}

const FILE_ICON: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  pdf: FileText,
  image: Image,
  code: Code,
  audio: Music,
  video: Video,
};

function detectDocType(file: File): { type: string; endpoint: string } {
  const ext = file.name.split(".").pop()?.toLowerCase() || "";
  if (ext === "pdf") return { type: "pdf", endpoint: `${API_BASE}/ingest/pdf` };
  if (["png", "jpg", "jpeg", "gif", "webp", "bmp"].includes(ext))
    return { type: "image", endpoint: `${API_BASE}/ingest/image` };
  if (["mp3", "wav", "m4a", "ogg", "flac"].includes(ext))
    return { type: "audio", endpoint: `${API_BASE}/ingest/audio` };
  if (["mp4", "avi", "mov", "mkv", "webm"].includes(ext))
    return { type: "video", endpoint: `${API_BASE}/ingest/video` };
  return { type: "code", endpoint: `${API_BASE}/ingest/pdf` }; // fallback
}

async function uploadFile(file: File): Promise<Document> {
  const { endpoint } = detectDocType(file);
  const form = new FormData();
  form.append("file", file);
  const response = await axios.post<{ doc_id: string; filename: string; chunk_count: number }>(
    endpoint,
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return {
    id: response.data.doc_id,
    filename: response.data.filename,
    doc_type: detectDocType(file).type,
    chunk_count: response.data.chunk_count,
    file_size: file.size,
    created_at: new Date().toISOString(),
    metadata: {},
    status: "indexed",
  };
}

export default function DocumentUpload({ onDocumentAdded }: Props) {
  const [uploads, setUploads] = useState<UploadStatus[]>([]);

  const onDrop = useCallback(
    async (accepted: File[]) => {
      const newUploads: UploadStatus[] = accepted.map((f) => ({ file: f, status: "pending" }));
      setUploads((prev) => [...prev, ...newUploads]);

      for (let i = 0; i < accepted.length; i++) {
        const file = accepted[i];
        setUploads((prev) =>
          prev.map((u) => (u.file === file ? { ...u, status: "uploading" } : u))
        );
        try {
          const doc = await uploadFile(file);
          onDocumentAdded(doc);
          setUploads((prev) =>
            prev.map((u) =>
              u.file === file ? { ...u, status: "done", docId: doc.id, message: `${doc.chunk_count} chunks indexed` } : u
            )
          );
        } catch (err: unknown) {
          const message = axios.isAxiosError(err)
            ? err.response?.data?.detail || err.message
            : String(err);
          setUploads((prev) =>
            prev.map((u) => (u.file === file ? { ...u, status: "error", message } : u))
          );
        }
      }
    },
    [onDocumentAdded]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/*": [".png", ".jpg", ".jpeg", ".gif", ".webp"],
      "audio/*": [".mp3", ".wav", ".m4a", ".ogg", ".flac"],
      "video/*": [".mp4", ".avi", ".mov", ".mkv", ".webm"],
      "text/*": [".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".md"],
    },
  });

  const clearDone = () => setUploads((prev) => prev.filter((u) => u.status !== "done"));

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={clsx(
          "border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all duration-150",
          isDragActive
            ? "border-brand-400 bg-brand-600/10"
            : "border-gray-700 hover:border-gray-500 bg-gray-800/30"
        )}
      >
        <input {...getInputProps()} />
        <Upload
          size={32}
          className={clsx("mx-auto mb-3", isDragActive ? "text-brand-400" : "text-gray-500")}
        />
        <p className="text-sm font-medium text-gray-300">
          {isDragActive ? "Drop files to upload..." : "Drag & drop files here"}
        </p>
        <p className="text-xs text-gray-500 mt-1">
          PDF, Images (PNG/JPG), Audio (MP3/WAV), Video (MP4), or Code files
        </p>
        <button className="mt-3 btn-secondary text-xs">Browse files</button>
      </div>

      {uploads.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Upload Queue</p>
            <button onClick={clearDone} className="text-xs text-gray-500 hover:text-gray-300">
              Clear done
            </button>
          </div>
          {uploads.map((u, idx) => {
            const { type } = detectDocType(u.file);
            const Icon = FILE_ICON[type] || FileText;
            return (
              <div key={idx} className="flex items-center gap-3 card py-2 px-3">
                <Icon size={16} className="text-gray-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-200 truncate">{u.file.name}</p>
                  {u.message && (
                    <p
                      className={clsx(
                        "text-xs",
                        u.status === "error" ? "text-red-400" : "text-gray-500"
                      )}
                    >
                      {u.message}
                    </p>
                  )}
                </div>
                <div className="shrink-0">
                  {u.status === "uploading" && (
                    <Loader size={16} className="text-brand-400 animate-spin" />
                  )}
                  {u.status === "done" && <CheckCircle size={16} className="text-green-400" />}
                  {u.status === "error" && <AlertCircle size={16} className="text-red-400" />}
                  {u.status === "pending" && (
                    <div className="w-4 h-4 rounded-full border-2 border-gray-600" />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
