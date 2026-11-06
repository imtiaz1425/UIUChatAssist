import json
import re
import os
from pathlib import Path

def load_data(file_path):
    """Load JSON data from file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def split_sentences(text):
    """Split text into sentences while preserving readability."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def create_chunks(text, max_size=1200, overlap_size=200):
    """
    Create overlapping chunks.
    
    max_size = maximum chunk size
    overlap_size = characters shared between chunks
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + max_size, text_length)
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break

        start = end - overlap_size

    return chunks

def process_data(input_file, output_dir):
    """
    Process pages and create chunks.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    pages = load_data(input_file)

    all_chunks = []
    chunk_id = 1

    NOISE_TEXTS = [
        "Follow Us",
        "About UIU",
        "Departments",
        "Admission",
        "Important Links",
        "Quick Links",
        "United City, Madani Ave, Dhaka 1212"
    ]

    for page in pages:
        url = page.get('url', '')
        title = page.get('title', '')
        content = page.get('content', '')

        if not content:
            continue

        # Remove common website boilerplate
        for noise in NOISE_TEXTS:
            content = content.replace(noise, "")

        # Add title to improve retrieval quality
        full_text = f"Title: {title}\n\n{content}"

        text_chunks = create_chunks(full_text)

        for text in text_chunks:
            chunk_obj = {
                "chunk_id": chunk_id,
                "url": url,
                "title": title,
                "text": text
            }

            all_chunks.append(chunk_obj)
            chunk_id += 1

    output_file = os.path.join(output_dir, 'chunks.json')

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)

    print(f"✓ Total chunks created: {len(all_chunks)}")
    print(f"✓ Chunks saved successfully to {output_file}")

    return all_chunks

if __name__ == "__main__":
    input_file = "data/raw/cse_full_data.json"
    output_dir = "data/chunks"

    process_data(input_file, output_dir)