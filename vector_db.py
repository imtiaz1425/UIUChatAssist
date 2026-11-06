import json
from pathlib import Path

import faiss
import numpy as np


def load_data(embeddings_path, metadata_path):
    """Load embeddings and metadata from disk."""
    embeddings = np.load(embeddings_path)
    with open(metadata_path, "r", encoding="utf-8") as file:
        metadata = json.load(file)
    return embeddings, metadata


def build_faiss_index(embeddings):
    """Build a cosine-similarity FAISS index."""
    print("→ Creating FAISS index...")
    vectors = embeddings.astype("float32")
    faiss.normalize_L2(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    print("✓ Index created")
    print(f"✓ Vectors stored: {index.ntotal}")
    return index


def save_index(index, output_path):
    """Save the FAISS index to disk."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, output_path)
    print(f"✓ Index saved successfully to {output_path}")


def main():
    embeddings_path = "data/embeddings/embeddings.npy"
    metadata_path = "data/embeddings/metadata.json"
    output_path = "data/vector_store/faiss_index.index"

    print("→ Loading embeddings and metadata...")
    embeddings, metadata = load_data(embeddings_path, metadata_path)
    print(f"✓ Embeddings loaded: {embeddings.shape[0]} vectors")
    print(f"✓ Metadata loaded: {len(metadata)} records")

    index = build_faiss_index(embeddings)
    save_index(index, output_path)


if __name__ == "__main__":
    main()
