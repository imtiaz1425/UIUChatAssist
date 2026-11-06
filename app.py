import json
import os
import re
import sqlite3

import faiss
import groq
import numpy as np
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "uiu-chatassist-dev-secret")

# Groq client will be initialized from the GROQ_API_KEY environment variable
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "users.db")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

INDEX_PATH = "data/vector_store/faiss_index.index"
METADATA_PATH = "data/embeddings/metadata.json"
MODEL_NAME = "all-MiniLM-L6-v2"

faiss_index = None
chunk_metadata = []
embedding_model = None


def get_auth_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_auth_db():
    with get_auth_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                university_id TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def init_chat_db():
    with get_auth_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_created ON messages(conversation_id, created_at ASC)"
        )
        connection.commit()


def find_user_by_email(email):
    with get_auth_connection() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)",
            (email,)
        ).fetchone()


def find_user_by_university_id(university_id):
    with get_auth_connection() as connection:
        return connection.execute(
            "SELECT * FROM users WHERE university_id = ?",
            (university_id,)
        ).fetchone()


def create_user(full_name, university_id, email, password_hash):
    with get_auth_connection() as connection:
        connection.execute(
            """
            INSERT INTO users (full_name, university_id, email, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (full_name, university_id, email, password_hash),
        )
        connection.commit()


init_auth_db()
init_chat_db()


def create_conversation(user_id, title="New Chat"):
    with get_auth_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO conversations (user_id, title)
            VALUES (?, ?)
            """,
            (user_id, title),
        )
        connection.commit()
        return cursor.lastrowid


def get_conversation_for_user(user_id, conversation_id):
    with get_auth_connection() as connection:
        return connection.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()


def list_recent_conversations_for_user(user_id, limit=20):
    with get_auth_connection() as connection:
        return connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            WHERE user_id = ?
            ORDER BY datetime(updated_at) DESC, id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()


def list_messages_for_conversation(user_id, conversation_id):
    with get_auth_connection() as connection:
        return connection.execute(
            """
            SELECT m.id, m.role, m.content, m.created_at
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.conversation_id = ? AND c.user_id = ?
            ORDER BY datetime(m.created_at) ASC, m.id ASC
            """,
            (conversation_id, user_id),
        ).fetchall()


def add_message(conversation_id, user_id, role, content):
    with get_auth_connection() as connection:
        connection.execute(
            """
            INSERT INTO messages (conversation_id, user_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, user_id, role, content),
        )
        connection.execute(
            """
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        )
        connection.commit()


def count_user_messages(conversation_id):
    with get_auth_connection() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM messages
            WHERE conversation_id = ? AND role = 'user'
            """,
            (conversation_id,),
        ).fetchone()
        return int(row["total"]) if row else 0


def update_conversation_title(user_id, conversation_id, title):
    with get_auth_connection() as connection:
        connection.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (title, conversation_id, user_id),
        )
        connection.commit()


def delete_conversation_for_user(user_id, conversation_id):
    with get_auth_connection() as connection:
        row = connection.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
        if not row:
            return False

        connection.execute(
            "DELETE FROM messages WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        connection.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        connection.commit()
        return True


def load_rag_resources():
    """Load FAISS index, metadata, and embedding model."""
    global faiss_index, chunk_metadata, embedding_model
    global groq_client

    if faiss_index is None:
        faiss_index = faiss.read_index(INDEX_PATH)
        print(f"Loaded FAISS index from {INDEX_PATH}")

    if not chunk_metadata:
        with open(METADATA_PATH, "r", encoding="utf-8") as file:
            chunk_metadata = json.load(file)
        print(f"Loaded {len(chunk_metadata)} chunk metadata records")

    if embedding_model is None:
        print(f"Loading embedding model: {MODEL_NAME}")
        embedding_model = SentenceTransformer(MODEL_NAME)
        print("Embedding model loaded")

    if groq_client is None:
        api_key = GROQ_API_KEY
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set")
        groq_client = groq.Groq(api_key=api_key)
        print("Groq client initialized")
def search_relevant_data(query: str, top_k: int = 10):

    query_vector = embedding_model.encode([query]).astype(np.float32)
    faiss.normalize_L2(query_vector)

    scores, indices = faiss_index.search(query_vector, top_k)

    relevant_chunks = []

    for score, index_id in zip(scores[0], indices[0]):
        if index_id == -1 or index_id >= len(chunk_metadata):
            continue

        chunk = chunk_metadata[index_id]

        relevant_chunks.append({
            "score": float(score),
            "chunk_id": chunk.get("chunk_id"),
            "url": chunk.get("url", ""),
            "title": chunk.get("title", ""),
            "text": chunk.get("text", "")
        })

    print("\n========== RETRIEVED CHUNKS ==========")

    for i, chunk in enumerate(relevant_chunks):
        print(f"\nChunk {i+1}")
        print("Score:", chunk["score"])
        print("Title:", chunk["title"])
        print("URL:", chunk["url"])
        print("Text:", chunk["text"][:500])

    print("\n======================================")

    return relevant_chunks

@app.route("/")
def home():
    return render_template("login.html", error=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", error=None)

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="Please fill in all fields.")

    user = find_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"] = user["id"]
    session["full_name"] = user["full_name"]
    session["email"] = user["email"]
    session["university_id"] = user["university_id"]

    return redirect(url_for("chat"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", error=None)

    full_name = request.form.get("full_name", "").strip()
    university_id = request.form.get("university_id", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([full_name, university_id, email, password, confirm_password]):
        return render_template("register.html", error="Please fill in all fields.")

    if not EMAIL_PATTERN.match(email):
        return render_template("register.html", error="Please enter a valid email address.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters long.")

    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.")

    if find_user_by_email(email):
        return render_template("register.html", error="Email is already registered.")

    if find_user_by_university_id(university_id):
        return render_template("register.html", error="University ID is already registered.")

    create_user(full_name, university_id, email, generate_password_hash(password))

    return redirect(url_for("login"))


@app.route("/chat", methods=["GET", "POST"])
def chat():

    if request.method == "GET":
        if not session.get("user_id"):
            return redirect(url_for("login"))

        return render_template(
            "chat.html",
            full_name=session.get("full_name", "User"),
            university_id=session.get("university_id", "N/A"),
            email=session.get("email", "student@uiu.ac.bd")
        )

    if not session.get("user_id"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        user_id = session.get("user_id")
        payload = request.get_json(silent=True) or {}
        user_message = payload.get("message", "").strip()
        conversation_id = payload.get("conversation_id")

        if conversation_id is not None:
            try:
                conversation_id = int(conversation_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid conversation id"}), 400

            if not get_conversation_for_user(user_id, conversation_id):
                return jsonify({"error": "Conversation not found"}), 404
        else:
            conversation_id = create_conversation(user_id)

        print(f"Query received: {user_message}")

        # Empty message check
        if not user_message:
            return jsonify({
                "error": "Empty message"
            }), 400

        load_rag_resources()

        # Search relevant university data
        relevant_chunks = search_relevant_data(user_message)
        print(f"Chunks retrieved: {len(relevant_chunks)}")

        # Build context
        context = "\n\n".join(chunk["text"] for chunk in relevant_chunks)

        if not context:
            context = "No specific university information found."

        # Structured system prompt enforcing guidelines and factual constraints
        system_prompt = """You are UIU ChatAssist, an AI assistant for United International University (UIU).

Your primary purpose is assisting students, faculty, and visitors with accurate information regarding admissions, academics, campus/office locations, semester details, notices, and university services.

Strict Response Guidelines:
1. Answer the user's exact question first.
2. Use clear, simple, student-friendly language.
3. Keep normal answers concise (around 80–150 words).
4. Use bullet points for faculty information instead of large tables.
5. Avoid providing unrelated information, excessive statistics, or publication details unless requested.
6. If a user's spelling is unclear, suggest the most likely matching faculty member and ask for confirmation when necessary.
7. Never invent faculty information, contact details, academic rules, or university policies.
8. Use only the retrieved context as the factual source. If the retrieved information does not contain the answer, clearly say that the information is unavailable.
9. For follow-up questions, answer in the context of the previous conversation when possible. Do not claim to remember previous information if it was not provided to the model.
10. Use headings only when they improve readability.

Additional Rules:
- If the user greets casually, respond naturally and politely.
- If the user asks unrelated topics outside UIU, politely say:
   "I mainly assist with UIU-related information."
- Be friendly and conversational."""

        rag_prompt = f"""University Information:
{context}

User Question:
{user_message}"""

        # Retrieve recent conversation context for this user and conversation (up to last 6 messages)
        past_records = list_messages_for_conversation(user_id, conversation_id)
        recent_records = past_records[-6:] if len(past_records) > 6 else past_records

        # Generate Groq response with system prompt, recent conversational context, and current RAG turn
        messages = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]

        for record in recent_records:
            msg_role = "assistant" if record["role"] == "assistant" else "user"
            messages.append({
                "role": msg_role,
                "content": record["content"]
            })

        # Append current user question along with newly retrieved university context
        messages.append({
            "role": "user",
            "content": rag_prompt
        })

        response = groq_client.chat.completions.create(
            messages=messages,
            model="openai/gpt-oss-120b",
            temperature=0.2,
        )

        # Extract text from response
        bot_message = ""
        try:
            if response and getattr(response, "choices", None):
                bot_message = response.choices[0].message.content or ""
        except Exception:
            bot_message = str(response)

        add_message(conversation_id, user_id, "user", user_message)
        add_message(conversation_id, user_id, "assistant", bot_message)

        if count_user_messages(conversation_id) == 1:
            new_title = user_message[:60].strip()
            if new_title:
                update_conversation_title(user_id, conversation_id, new_title)

        print("Groq response generated")

        return jsonify({
            "response": bot_message,
            "context_used": [chunk["text"] for chunk in relevant_chunks],
            "conversation_id": conversation_id
        })

    except Exception as e:

        print("Error:", str(e))

        return jsonify({
            "error": str(e)
        }), 500


@app.route("/api/conversations", methods=["GET", "POST"])
def conversations_api():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "POST":
        conversation_id = create_conversation(user_id)
        conversation = get_conversation_for_user(user_id, conversation_id)
        return jsonify(
            {
                "id": conversation["id"],
                "title": conversation["title"],
                "created_at": conversation["created_at"],
                "updated_at": conversation["updated_at"],
            }
        )

    items = list_recent_conversations_for_user(user_id)
    return jsonify(
        {
            "items": [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "created_at": item["created_at"],
                    "updated_at": item["updated_at"],
                }
                for item in items
            ]
        }
    )


@app.route("/api/conversations/<int:conversation_id>", methods=["GET", "DELETE"])
def conversation_detail_api(conversation_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    if request.method == "DELETE":
        deleted = delete_conversation_for_user(user_id, conversation_id)
        if not deleted:
            return jsonify({"error": "Conversation not found or unauthorized"}), 404
        return jsonify({"success": True, "deleted_id": conversation_id})

    conversation = get_conversation_for_user(user_id, conversation_id)
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    messages = list_messages_for_conversation(user_id, conversation_id)
    return jsonify(
        {
            "id": conversation["id"],
            "title": conversation["title"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
            "messages": [
                {
                    "id": item["id"],
                    "role": item["role"],
                    "content": item["content"],
                    "created_at": item["created_at"],
                }
                for item in messages
            ],
        }
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/health")
def health():

    return jsonify({
        "status": "running",
        "data_loaded": faiss_index is not None and len(chunk_metadata) > 0,
        "data_points": len(chunk_metadata)
    })


if __name__ == "__main__":

    # Load RAG resources
    load_rag_resources()

    # Run Flask app
    app.run(debug=True, port=5000)