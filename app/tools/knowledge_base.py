"""
Knowledge base builder and query module for Wesh Tuition Centre.
Run this file directly to build the FAISS index:
    python -m app.tools.knowledge_base
"""
import os
import pickle
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
# Updated to use the modern, officially supported Hugging Face integration
from langchain_huggingface import HuggingFaceEmbeddings

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).resolve().parent.parent.parent
DOCS_DIR   = BASE_DIR / "knowledge_base" / "docs"
INDEX_DIR  = BASE_DIR / "knowledge_base" / "index"

# ── Embedding model (same one from your APEL chatbot) ────────────────────────
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_vectorstore = None  # singleton — loaded once


def _load_documents() -> list[str]:
    """Load all .md/.txt files from the docs folder."""
    docs = []
    for file in DOCS_DIR.glob("*.md"):
        docs.append(file.read_text(encoding="utf-8"))
    for file in DOCS_DIR.glob("*.txt"):
        docs.append(file.read_text(encoding="utf-8"))
    return docs


def build_index():
    """Build and save the FAISS index from knowledge base documents."""
    print("📚 Loading documents...")
    raw_docs = _load_documents()
    print(f"   Loaded {len(raw_docs)} document(s)")

    print("✂️  Splitting into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ".", "?", "!"],
    )
    chunks = splitter.create_documents(raw_docs)
    print(f"   Created {len(chunks)} chunks")

    print("🧠 Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    print("🔍 Building FAISS index...")
    vectorstore = FAISS.from_documents(chunks, embeddings)

    print("💾 Saving index...")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(INDEX_DIR))
    print(f"   ✅ Index saved to {INDEX_DIR}")
    return vectorstore


def get_vectorstore() -> FAISS:
    """Load the FAISS index (singleton — loads once per process)."""
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    index_path = str(INDEX_DIR)

    # In production on Railway, this should always exist because we committed it to Git.
    if not (INDEX_DIR / "index.faiss").exists():
        print("⚠️  No FAISS index found — building now...")
        _vectorstore = build_index()
    else:
        _vectorstore = FAISS.load_local(
            index_path,
            embeddings,
            allow_dangerous_deserialization=True,
        )
    return _vectorstore


def query_knowledge_base(question: str, k: int = 2) -> str:
    """
    Query the knowledge base and return the most relevant context.
    This is what the LangChain agent tool will call.
    """
    vs = get_vectorstore()
    docs = vs.similarity_search(question, k=k)
    if not docs:
        return "No relevant information found in the knowledge base."
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


if __name__ == "__main__":
    print("\n🏗️  Building Wesh Tuition Centre knowledge base...\n")
    build_index()
    print("\n✅ Done! Testing a sample query...\n")
    result = query_knowledge_base("What are the fees for all subjects?")
    print("Query: 'What are the fees for all subjects?'")
    print("Result:\n", result[:500], "...")