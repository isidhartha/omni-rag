"""Codebase indexing with AST parsing and semantic search support."""
from __future__ import annotations

import ast
import logging
import os
from pathlib import Path
from typing import Iterator, Optional
from uuid import uuid4

from backend.processing.chunker import SmartChunker
from backend.shared.models import Chunk, DocumentRecord, DocumentType

logger = logging.getLogger("omnirag.ingestion.code")

LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".md": "markdown",
    ".sql": "sql",
}

IGNORED_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".env", "dist", "build"}
IGNORED_EXTS = {".pyc", ".pyo", ".exe", ".dll", ".so", ".bin", ".lock"}


class CodeIngester:
    """Index code files with language-aware chunking and AST metadata."""

    def __init__(self, chunker: Optional[SmartChunker] = None) -> None:
        self._chunker = chunker or SmartChunker(chunk_size=800, chunk_overlap=100)

    def ingest_file(self, file_path: Path) -> tuple[DocumentRecord, list[Chunk]]:
        """Ingest a single code file."""
        lang = LANGUAGE_MAP.get(file_path.suffix.lower(), "text")
        doc_id = str(uuid4())
        source_code = file_path.read_text(encoding="utf-8", errors="replace")

        extra_meta: dict = {}
        if lang == "python":
            extra_meta = self._extract_python_meta(source_code, file_path)

        chunks = self._chunker.chunk_code(
            code=source_code,
            doc_id=doc_id,
            language=lang,
            source=str(file_path),
        )
        for idx, chunk in enumerate(chunks):
            chunk.metadata.chunk_index = idx

        record = DocumentRecord(
            id=doc_id,
            filename=file_path.name,
            doc_type=DocumentType.CODE,
            file_size=file_path.stat().st_size,
            chunk_count=len(chunks),
            metadata={"language": lang, "path": str(file_path), **extra_meta},
        )
        return record, chunks

    def ingest_directory(self, repo_path: Path) -> list[tuple[DocumentRecord, list[Chunk]]]:
        """Recursively ingest all code files in a directory."""
        results: list[tuple[DocumentRecord, list[Chunk]]] = []
        for file_path in self._walk_code_files(repo_path):
            try:
                result = self.ingest_file(file_path)
                results.append(result)
                logger.debug(f"Indexed: {file_path}")
            except Exception as exc:
                logger.warning(f"Failed to index {file_path}: {exc}")
        logger.info(f"Indexed {len(results)} code files from '{repo_path}'.")
        return results

    def _walk_code_files(self, root: Path) -> Iterator[Path]:
        """Yield code files, skipping ignored paths."""
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if fpath.suffix.lower() in IGNORED_EXTS:
                    continue
                if fpath.suffix.lower() in LANGUAGE_MAP:
                    yield fpath

    def _extract_python_meta(self, source: str, file_path: Path) -> dict:
        """Extract top-level function/class names from Python AST."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {}
        functions = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        return {"functions": functions[:20], "classes": classes[:10], "imports": imports[:20]}
