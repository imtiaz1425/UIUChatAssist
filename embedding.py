import json
import os
from pathlib import Path
import numpy as np
from sentence_transformers import SentenceTransformer


def load_chunks(file_path):
    """Load chunks from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_embeddings(chunks, model_name="all-MiniLM-L6-v2"):
    """
    Generate embeddings for all chunks.
    
    Args:
        chunks: List of chunk objects
        model_name: Sentence transformer model to use
    
    Returns:
        embeddings: numpy array of shape (num_chunks, embedding_dim)
        metadata: list of chunk metadata
    """
    # Load model
    print(f"→ Loading embedding model: {model_name}")
    model = SentenceTransformer(model_name)
    print(f"✓ Model loaded successfully")
    
    # Extract texts and metadata
    texts = [chunk['text'] for chunk in chunks]
    metadata = [
        {
            'chunk_id': chunk['chunk_id'],
            'url': chunk['url'],
            'title': chunk['title'],
            'text': chunk['text']
        }
        for chunk in chunks
    ]
    
    # Generate embeddings
    print(f"→ Generating embeddings for {len(texts)} chunks...")
    embeddings = model.encode(texts, show_progress_bar=False, batch_size=32)
    print(f"✓ Embeddings generated successfully")
    
    return embeddings, metadata


def save_embeddings(embeddings, metadata, output_dir):
    """
    Save embeddings and metadata to files.
    
    Args:
        embeddings: numpy array of embeddings
        metadata: list of chunk metadata
        output_dir: directory to save files
    """
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Save embeddings as numpy array
    embeddings_file = os.path.join(output_dir, 'embeddings.npy')
    np.save(embeddings_file, embeddings)
    
    # Save metadata as JSON
    metadata_file = os.path.join(output_dir, 'metadata.json')
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    # Print logs
    print(f"✓ Total embeddings generated: {len(embeddings)}")
    print(f"✓ Embedding dimension: {embeddings.shape[1]}")
    print(f"✓ Embeddings saved to {embeddings_file}")
    print(f"✓ Metadata saved to {metadata_file}")
    
    return embeddings_file, metadata_file


def process_embeddings(chunks_file, output_dir):
    """
    Main function to process chunks and generate embeddings.
    
    Args:
        chunks_file: path to chunks JSON file
        output_dir: directory to save embeddings
    """
    # Load chunks
    print(f"→ Loading chunks from {chunks_file}")
    chunks = load_chunks(chunks_file)
    print(f"✓ Loaded {len(chunks)} chunks")
    print()
    
    # Generate embeddings
    embeddings, metadata = generate_embeddings(chunks)
    print()
    
    # Save files
    print("→ Saving embeddings and metadata...")
    save_embeddings(embeddings, metadata, output_dir)


if __name__ == "__main__":
    chunks_file = "data/chunks/chunks.json"
    output_dir = "data/embeddings"
    
    process_embeddings(chunks_file, output_dir)
