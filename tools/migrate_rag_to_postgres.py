from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import db  # noqa: E402
from app.rag import RAG_DOCUMENT_SUFFIXES, ingest_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chunk and embed published PostgreSQL rag_files into document_chunks."
    )
    parser.add_argument("--course-id", help="Only migrate one course UUID.")
    args = parser.parse_args()

    files = db.list_indexable_rag_files()
    if args.course_id:
        files = [file for file in files if file.get("course_id") == args.course_id]

    indexed_files = 0
    indexed_chunks = 0
    skipped: list[str] = []
    for position, file in enumerate(files, start=1):
        filename = Path(str(file["filename"])).name
        if Path(filename).suffix.lower() not in RAG_DOCUMENT_SUFFIXES:
            skipped.append(filename)
            continue

        with tempfile.TemporaryDirectory(prefix="socratic-rag-") as temp_dir:
            path = Path(temp_dir) / filename
            path.write_bytes(bytes(file["content"]))
            _, chunk_count = ingest_file(
                path,
                conversation_id=str(file["conversation_id"]) if file.get("conversation_id") else None,
                course_id=str(file["course_id"]) if file.get("course_id") else None,
                file_id=str(file["file_id"]),
            )
        indexed_files += 1
        indexed_chunks += chunk_count
        print(f"[{position}/{len(files)}] {filename}: {chunk_count} chunks")

    print(
        f"Migration complete: {indexed_files} files, {indexed_chunks} chunks, "
        f"{len(skipped)} unsupported files skipped."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
