"""
services/vector_store.py
--------------------------
WHAT:
    Wraps a FAISS index (the "vector database") together with a
    parallel metadata list, and exposes create / add / search /
    save / load operations.

WHY:
    FAISS itself only stores raw vectors and returns integer positions
    ("I found your best match at position 7"). It knows nothing about
    which document or chunk of text that vector came from. This module
    keeps a Python list of metadata dicts in the SAME ORDER as vectors
    are added to the index, so position 7 in FAISS always corresponds
    to position 7 in the metadata list. That parallel-array discipline
    is the single most important invariant in this file — breaking it
    silently returns wrong answers with high confidence, which is worse
    than crashing.

HOW:
    Uses faiss.IndexFlatL2 (a plain L2-distance index — simple, exact,
    and more than fast enough at the scale of a single study document).
    Vectors are converted to float32 NumPy arrays, which FAISS requires.

INPUT:
    Embedding vectors (lists of floats) + matching metadata dicts.

OUTPUT:
    Search results: ranked list of metadata dicts for the most
    semantically similar chunks to a query vector.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import faiss
import numpy as np


@dataclass
class VectorStore:
    """
    Holds a FAISS index and its parallel metadata list.

    Attributes:
        dimension: length of each embedding vector. Set on first
            add_documents() call and enforced afterwards.
        index: the underlying FAISS index, or None until created.
        metadata: list of dicts, one per vector, in insertion order.
            Each dict looks like: {"text": ..., "source": ..., "chunk_id": ...}
    """

    dimension: int | None = None
    index: faiss.Index | None = None
    metadata: list[dict] = field(default_factory=list)

    def create_index(self, dimension: int) -> None:
        """Initialize an empty FAISS index for vectors of the given dimension."""
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.metadata = []

    def add_documents(self, embeddings: list[list[float]], metadata: list[dict]) -> None:
        """
        Add a batch of embeddings and their matching metadata to the index.

        Args:
            embeddings: list of embedding vectors.
            metadata: list of metadata dicts, SAME LENGTH and SAME ORDER
                as `embeddings`. metadata[i] must describe embeddings[i].

        Raises:
            ValueError: if lengths mismatch (this would silently corrupt
                the store's core invariant, so we refuse instead).
        """
        if len(embeddings) != len(metadata):
            raise ValueError(
                f"embeddings ({len(embeddings)}) and metadata ({len(metadata)}) "
                "must be the same length."
            )
        if not embeddings:
            return

        vectors = np.array(embeddings, dtype="float32")

        if self.index is None:
            self.create_index(dimension=vectors.shape[1])

        self.index.add(vectors)
        self.metadata.extend(metadata)

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[dict]:
        """
        Find the top_k chunks most semantically similar to a query vector.

        Args:
            query_embedding: embedding of the user's question.
            top_k: how many results to return.

        Returns:
            List of metadata dicts (copies, with a "score" field added),
            ordered from most to least similar. Empty list if the store
            has no documents yet.
        """
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vector = np.array([query_embedding], dtype="float32")
        k = min(top_k, self.index.ntotal)

        distances, indices = self.index.search(query_vector, k)

        results: list[dict] = []
        for distance, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            record = dict(self.metadata[idx])
            record["score"] = float(distance)  # lower L2 distance = more similar
            results.append(record)

        return results

    def save_index(self, index_path: str, metadata: list[dict] | None = None) -> None:
        """
        Persist the FAISS index and metadata to disk.

        Args:
            index_path: path (without extension) to save to. Two files
                are written: "{index_path}.faiss" and "{index_path}.meta.npy".
            metadata: optionally override stored metadata before saving.
        """
        import json
        from pathlib import Path

        if metadata is not None:
            self.metadata = metadata

        if self.index is None:
            raise ValueError("Cannot save an index that has not been created yet.")

        Path(index_path).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, f"{index_path}.faiss")

        with open(f"{index_path}.meta.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f)

    def load_index(self, index_path: str) -> None:
        """Load a previously saved FAISS index and its metadata from disk."""
        import json

        self.index = faiss.read_index(f"{index_path}.faiss")
        self.dimension = self.index.d

        with open(f"{index_path}.meta.json", encoding="utf-8") as f:
            self.metadata = json.load(f)
