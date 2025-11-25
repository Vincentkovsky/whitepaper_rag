import chromadb
from pathlib import Path

# Use the same persistent directory as the backend
persist_dir = Path(__file__).parent / "app" / "storage" / "chromadb"
persist_dir.mkdir(parents=True, exist_ok=True)

client = chromadb.PersistentClient(path=str(persist_dir))
collection = client.get_or_create_collection("documents")

# 看当前 collection 中的总量
total = collection.count()
print(f"Total embeddings: {total}")

if total > 0:
    # 列出前 5 条 embedding 及其 metadata
    records = collection.get(
        include=["metadatas", "documents", "embeddings"],
        limit=5,
    )
    for idx, doc_id in enumerate(records["ids"]):
        print(f"\nID: {doc_id}")
        print("metadata:", records["metadatas"][idx])
        print("text snippet:", records["documents"][idx][:120])
        print("embedding dim:", len(records["embeddings"][idx]))
        print("-" * 40)
else:
    print("No embeddings found in the collection.")
