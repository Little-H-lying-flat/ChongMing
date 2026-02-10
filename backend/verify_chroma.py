import chromadb
import sys

print(f"Python Version: {sys.version}")

try:
    client = chromadb.PersistentClient(path="./test_chroma_db_verify")
    collection = client.get_or_create_collection("verification_collection")
    
    # Clean up
    if collection.count() > 0:
        collection.delete(collection.get()['ids'])
        
    print("Adding document...")
    collection.add(
        documents=["This is a test document about AI testing."],
        metadatas=[{"source": "test"}],
        ids=["id1"]
    )
    
    print("Querying...")
    results = collection.query(
        query_texts=["AI testing"],
        n_results=1
    )
    
    print("Results:", results)
    
    if results['ids'][0][0] == 'id1':
        print("✅ ChromaDB Verification Passed!")
    else:
        print("❌ ChromaDB Verification Failed: ID mismatch.")
        
except Exception as e:
    print(f"❌ ChromaDB Verification Failed with Exception: {e}")
    import traceback
    traceback.print_exc()
