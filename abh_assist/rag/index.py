import chromadb
from chromadb.utils import embedding_functions
from abh_assist.config import config
import os

def get_collection():
    client = chromadb.PersistentClient(path=config['chroma_db_path'])
    
    # Use a default embedding function if local model not easily available, 
    # or use sentence-transformers if installed.
    # For PoC simplicity, we use the default all-MiniLM-L6-v2 which Chroma downloads automatically.
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=config['embedding_model'])
    
    collection = client.get_or_create_collection(name="abh_kb", embedding_function=ef)
    return collection

def build_index(kb_dir="kb"):
    collection = get_collection()
    
    ids = []
    documents = []
    metadatas = []
    
    if not os.path.exists(kb_dir):
        return
        
    for f in os.listdir(kb_dir):
        if f.endswith(".txt"):
            with open(os.path.join(kb_dir, f), "r", encoding="utf-8") as file:
                text = file.read()
                # Simple chunking by paragraph
                chunks = text.split("\n\n")
                for i, chunk in enumerate(chunks):
                    if chunk.strip():
                        ids.append(f"{f}_{i}")
                        documents.append(chunk)
                        metadatas.append({"source": f})
                        
    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
        print(f"Indexed {len(ids)} chunks.")
