import React, { useState } from "react";
import { Routes, Route, NavLink } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import Search from "./pages/Search";

export interface Document {
  id: string;
  filename: string;
  doc_type: string;
  chunk_count: number;
  file_size: number;
  created_at: string;
  metadata: Record<string, unknown>;
  status: string;
}

export interface AppState {
  documents: Document[];
  setDocuments: React.Dispatch<React.SetStateAction<Document[]>>;
  activeDocIds: string[];
  setActiveDocIds: React.Dispatch<React.SetStateAction<string[]>>;
}

export const AppContext = React.createContext<AppState>({
  documents: [],
  setDocuments: () => {},
  activeDocIds: [],
  setActiveDocIds: () => {},
});

export default function App() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [activeDocIds, setActiveDocIds] = useState<string[]>([]);

  return (
    <AppContext.Provider value={{ documents, setDocuments, activeDocIds, setActiveDocIds }}>
      <div className="flex h-screen overflow-hidden bg-gray-950">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/search" element={<Search />} />
          </Routes>
        </main>
      </div>
    </AppContext.Provider>
  );
}
