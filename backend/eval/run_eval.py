"""Standalone retrieval-quality eval for the RAG pipeline. Not part of the
pytest suite (it uses the real embedding model, not a mock) -- run it by hand:

    python backend/eval/run_eval.py

Builds a fresh, temporary Chroma index over backend/eval/fixtures/sample.pdf
using the same chunking parameters as backend/app.py, runs every question in
dataset.json through the same k=3 similarity_search the chat endpoint uses,
and reports whether each question's expected page was retrieved.
"""

import json
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

EVAL_DIR = Path(__file__).parent
FIXTURE_PDF = EVAL_DIR / "fixtures" / "sample.pdf"
DATASET = EVAL_DIR / "dataset.json"


def main():
    dataset = json.loads(DATASET.read_text())

    documents = PyMuPDFLoader(str(FIXTURE_PDF)).load()
    chunks = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=80).split_documents(
        documents
    )

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # No persist_directory: an ephemeral in-memory collection is all a
    # one-shot eval run needs, and avoids Chroma leaving open file handles
    # behind for a temp directory to clean up.
    vectorstore = Chroma(collection_name="eval-sample", embedding_function=embeddings)
    vectorstore.add_documents(chunks)

    hits = 0
    for item in dataset:
        question = item["question"]
        expected_page = item["expected_page"]
        results = vectorstore.similarity_search(query=question, k=3)
        retrieved_pages = sorted({doc.metadata.get("page", -1) + 1 for doc in results})

        hit = expected_page in retrieved_pages
        hits += hit
        status = "PASS" if hit else "FAIL"
        print(f"[{status}] expected p.{expected_page}, retrieved {retrieved_pages} -- {question}")

    total = len(dataset)
    rate = (hits / total * 100) if total else 0.0
    print(f"{hits}/{total} hits ({rate:.1f}%)")


if __name__ == "__main__":
    main()
