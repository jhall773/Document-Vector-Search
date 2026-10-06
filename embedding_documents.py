import os
import glob
import sqlite3
import sqlite_vec
import json
from pypdf import PdfReader
from docx import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

# 4. Processing Engine for PDFs (with Page Tracking)
def process_pdf(file_path, start_id, embeddings_model, text_splitter, db):
    reader = PdfReader(file_path)
    file_name = os.path.basename(file_path)
    current_id = start_id

    # Process page by page to capture correct metadata
    for page_idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text()
        if not page_text.strip():
            continue

        chunks = text_splitter.split_text(page_text)
        for chunk in chunks:
            vector = embeddings_model.embed_query(chunk)

            db.execute("INSERT INTO document_vectors(id, embedding) VALUES (?, ?)", (current_id, json.dumps(vector)))
            db.execute("""
                INSERT INTO document_metadata(id, content, source_file, location_info)
                VALUES (?, ?, ?, ?)
            """, (current_id, chunk, file_name, f"Page {page_idx}"))

            current_id += 1
    return current_id

# 5. Processing Engine for DOCX (with Heading Tracking)
def process_docx(file_path, start_id, embeddings_model, text_splitter, db):
    doc = Document(file_path)
    file_name = os.path.basename(file_path)
    current_id = start_id

    current_heading = "Document Start"
    buffer_text = []

    # Read block by block to find structural headings
    for para in doc.paragraphs:
        if para.style.name.startswith('Heading'):
            # If we hit a new heading, flush out the accumulated text before it
            if buffer_text:
                full_text = "\n".join(buffer_text)
                chunks = text_splitter.split_text(full_text)
                for chunk in chunks:
                    vector = embeddings_model.embed_query(chunk)
                    db.execute("INSERT INTO document_vectors(id, embedding) VALUES (?, ?)", (current_id, json.dumps(vector)))
                    db.execute("""
                        INSERT INTO document_metadata(id, content, source_file, location_info)
                        VALUES (?, ?, ?, ?)
                    """, (current_id, chunk, file_name, f"Section: {current_heading}"))
                    current_id += 1
                buffer_text = []
            current_heading = para.text.strip()
        else:
            if para.text.strip():
                buffer_text.append(para.text)

    # Flush any remaining text left over at the end of the file
    if buffer_text:
        full_text = "\n".join(buffer_text)
        chunks = text_splitter.split_text(full_text)
        for chunk in chunks:
            vector = embeddings_model.embed_query(chunk)
            db.execute("INSERT INTO document_vectors(id, embedding) VALUES (?, ?)", (current_id, json.dumps(vector)))
            db.execute("""
            INSERT INTO document_metadata(id, content, source_file, location_info)
            VALUES (?, ?, ?, ?)
            """, (current_id, chunk, file_name, f"Section: {current_heading}"))
            current_id += 1

    return current_id


FOLDER_PATH = "../Embed_Docs" # Put your 15 files in this folder
def create_embeddings_db(FOLDER_PATH, progress_callback=None):
    # --- CONFIGURATION ---
    DB_NAME = "local_knowledge.db"

    # 1. Initialize local 384-dimension embedding model
    print("🧠 Loading local 'all-MiniLM-L6-v2' model...")
    embeddings_model = HuggingFaceEmbeddings(model_name="local_models/all-MiniLM-L6-v2")


    # 2. Text Splitter Configuration (Optimized for 256-word token limit)
    text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=100,
    length_function=len
    )

    # 3. Setup New SQLite Tables with Location Tracking
    db = sqlite3.connect(DB_NAME)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)

    db.execute("DROP TABLE IF EXISTS document_vectors")
    db.execute("DROP TABLE IF EXISTS document_metadata")

    db.execute("CREATE VIRTUAL TABLE document_vectors USING vec0(id INTEGER PRIMARY KEY, embedding float [384])")
    db.execute("""
    CREATE TABLE document_metadata (
    id INTEGER PRIMARY KEY,
    content TEXT,
    source_file TEXT,
    location_info TEXT
    )
    """)
    db.commit()
    # 6. Run the main processing loop
    supported_extensions = ['*.pdf', '*.docx', '*.doc']
    files_to_process = []
    for ext in supported_extensions:
        files_to_process.extend(glob.glob(os.path.join(FOLDER_PATH, ext)))

    print(f"\n📂 Found {len(files_to_process)} document(s) to index in {FOLDER_PATH}.")

    global_id_counter = 1

    for idx, file_path in enumerate(files_to_process, start=1):
        print(f"📄 Indexing: {os.path.basename(file_path)}...")
        if progress_callback:
            progress_callback(idx, len(files_to_process))
        if file_path.endswith('.pdf'):
            global_id_counter = process_pdf(file_path, global_id_counter, embeddings_model, text_splitter, db)
        elif file_path.endswith(('.docx', '.doc')):
            global_id_counter = process_docx(file_path, global_id_counter, embeddings_model, text_splitter, db)
    db.commit()

    print(f"\n🎉 Finished! Total text blocks indexed: {global_id_counter - 1}")
    db.close()

if __name__ == "__main__":
    create_embeddings_db(FOLDER_PATH)