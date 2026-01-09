from abh_assist.rag.index import get_collection

def retrieve_context(query, n_results=3):
    collection = get_collection()
    results = collection.query(query_texts=[query], n_results=n_results)
    
    context = []
    if results['documents']:
        for i, doc in enumerate(results['documents'][0]):
            meta = results['metadatas'][0][i]
            context.append(f"Source: {meta['source']}\nContent: {doc}")
            
    return "\n\n".join(context)
