"""
Lightweight ONNX Runtime CPU Embedder for all-MiniLM-L6-v2.
Provides 100% vector-compatible embeddings with SentenceTransformers
while eliminating PyTorch, reducing RAM footprint from ~500 MB to ~160 MB.
"""

import os
import shutil
import urllib.request
import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

HF_BASE_URL = "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main"

# Minimum valid file size thresholds in bytes to detect truncated downloads
MIN_FILE_SIZES = {
    "model.onnx": 50 * 1024 * 1024,      # ~86 MB expected, min 50 MB
    "tokenizer.json": 100 * 1024         # ~440 KB expected, min 100 KB
}


class ONNXEmbeddingModel:
    """
    Drop-in replacement for SentenceTransformer('all-MiniLM-L6-v2') using ONNX Runtime.
    Produces 384-dimensional L2-normalized dense embeddings identical to PyTorch.
    """

    def __init__(self, model_dir=None):
        if model_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            model_dir = os.path.join(base_dir, "models", "all-MiniLM-L6-v2")

        self.model_dir = model_dir
        self.model_path = os.path.join(model_dir, "model.onnx")
        self.tokenizer_path = os.path.join(model_dir, "tokenizer.json")

        self._ensure_model_files()

        # Load tokenizers fast tokenizer
        self.tokenizer = Tokenizer.from_file(self.tokenizer_path)
        self.tokenizer.enable_padding(length=256)
        self.tokenizer.enable_truncation(max_length=256)

        # Configure ONNX Runtime session for lightweight CPU execution
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            self.model_path,
            sess_options=opts,
            providers=["CPUExecutionProvider"]
        )

    def _ensure_model_files(self):
        """
        Verify model and tokenizer files exist and are complete.
        Downloads to a temporary file, verifies file integrity, and atomically renames.
        Never overwrites a valid existing file with an incomplete download.
        """
        os.makedirs(self.model_dir, exist_ok=True)

        files = [
            ("onnx/model.onnx", self.model_path, "model.onnx", "ONNX Model (~86 MB)"),
            ("tokenizer.json", self.tokenizer_path, "tokenizer.json", "Tokenizer JSON (~440 KB)")
        ]

        for remote_subpath, local_path, filename, desc in files:
            min_size = MIN_FILE_SIZES.get(filename, 1024)

            # Check if valid file already exists
            if os.path.exists(local_path):
                actual_size = os.path.getsize(local_path)
                if actual_size >= min_size:
                    # Valid existing file, leave untouched
                    continue
                else:
                    print(f"Warning: Existing {filename} is corrupt or truncated ({actual_size} bytes < {min_size} bytes). Re-downloading...")

            tmp_path = f"{local_path}.tmp"
            url = f"{HF_BASE_URL}/{remote_subpath}"

            print(f"Downloading {desc} from Hugging Face...")
            try:
                # Remove any leftover temporary file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "UIUChatAssist/1.0 (Render deployment build)"}
                )

                # Stream download in chunks to temporary file
                with urllib.request.urlopen(req, timeout=120) as response, open(tmp_path, "wb") as out_file:
                    shutil.copyfileobj(response, out_file)

                # Validation step 1: Check downloaded size meets threshold
                downloaded_size = os.path.getsize(tmp_path)
                if downloaded_size < min_size:
                    raise IOError(
                        f"Downloaded {filename} is incomplete: {downloaded_size} bytes "
                        f"(expected at least {min_size} bytes)."
                    )

                # Validation step 2: For tokenizer, test syntax
                if filename == "tokenizer.json":
                    try:
                        Tokenizer.from_file(tmp_path)
                    except Exception as te:
                        raise ValueError(f"Downloaded tokenizer.json failed parsing validation: {te}")

                # Atomic replacement: only commit when fully verified
                os.replace(tmp_path, local_path)
                print(f"✓ Verified and saved {desc} to {local_path} ({downloaded_size / (1024 * 1024):.2f} MB)")

            except Exception as e:
                # Clean up temporary file on failure
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                raise RuntimeError(
                    f"CRITICAL: Failed downloading or validating {desc} from {url}.\n"
                    f"Error: {e}\n"
                    f"Please check network access to huggingface.co."
                ) from e

    def encode(self, texts, batch_size=32):
        """
        Encode a string or list of strings into 384-dimensional L2-normalized vectors.
        Returns a float32 numpy array of shape (N, 384).
        """
        if isinstance(texts, str):
            texts = [texts]

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            encodings = self.tokenizer.encode_batch(batch)

            input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
            attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
            token_type_ids = np.array([e.type_ids for e in encodings], dtype=np.int64)

            ort_inputs = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids
            }
            outputs = self.session.run(None, ort_inputs)
            token_embeddings = outputs[0]  # Shape: (batch_size, seq_len, 384)

            # Mean pooling masked by attention mask
            input_mask_expanded = np.broadcast_to(
                np.expand_dims(attention_mask, -1), token_embeddings.shape
            ).astype(np.float32)

            sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
            sum_mask = np.clip(input_mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
            pooled = sum_embeddings / sum_mask

            # L2 Normalize
            norms = np.linalg.norm(pooled, ord=2, axis=1, keepdims=True)
            normalized = (pooled / norms).astype(np.float32)
            all_embeddings.append(normalized)

        return np.vstack(all_embeddings)
