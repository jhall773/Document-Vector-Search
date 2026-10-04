import sqlite3
import sqlite_vec
import json
from langchain_huggingface import HuggingFaceEmbeddings

def search_local_docs(query_text, num_results=3):
    DB_NAME = "local_knowledge.db"
    embeddings_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    db = sqlite3.connect(DB_NAME)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)

    query_vector = embeddings_model.embed_query(query_text)

    # Grab the text, filename, and location_info from metadata
    cursor = db.execute("""
        SELECT
        m.content,
        m.source_file,
        m.location_info,
        v.distance
        FROM (
        SELECT id, distance
        FROM document_vectors
        WHERE embedding MATCH ?
        LIMIT ?
        ) v
        JOIN document_metadata m ON v.id = m.id
        ORDER BY v.distance
    """, (json.dumps(query_vector), num_results))

    results = cursor.fetchall()
    db.close()
    return results

if __name__ == "__main__":
    user_question = "Installing React.js"

    print(f"\n🔍 Searching for: '{user_question}'...")
    search_results = search_local_docs(user_question, num_results=5)

    for idx, (content, source_file, location, distance) in enumerate(search_results, start=1):
        print("-" * 60)
        print(f"Match #{idx} | 📄 File: {source_file} | 📍 {location} | 📉 Distance: {distance:.4f}")
        print("-" * 60)
        print(f"Content:\n{content.strip()}\n")