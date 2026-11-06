import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def load_data(index_path, metadata_path):
    """Load FAISS index and metadata."""
    index = faiss.read_index(index_path)
    with open(metadata_path, "r", encoding="utf-8") as file:
        metadata = json.load(file)
    return index, metadata


def search_query(index, metadata, model, query, top_k=20):
    """Search the index for the most similar chunks."""
    query_vector = model.encode([query]).astype("float32")
    faiss.normalize_L2(query_vector)
    scores, indices = index.search(query_vector, top_k)
    return scores[0], indices[0], metadata


def main():
    index_path = "data/vector_store/faiss_index.index"
    metadata_path = "data/embeddings/metadata.json"
    model_name = "all-MiniLM-L6-v2"

    index, metadata = load_data(index_path, metadata_path)
    model = SentenceTransformer(model_name)

    query = input("Enter your question: ")
    scores, indices, metadata = search_query(index, metadata, model, query)

    for rank, (score, index_id) in enumerate(zip(scores, indices), start=1):
        if index_id == -1:
            continue

        chunk = metadata[index_id]
        print(f"\nResult {rank}")
        print(f"Similarity score: {float(score):.4f}")
        print(f"Title: {chunk['title']}")
        print(f"URL: {chunk['url']}")
        print(f"Chunk text: {chunk['text']}")


if __name__ == "__main__":
    main()