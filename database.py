import chromadb
from sentence_transformers import SentenceTransformer
import json

with open("data.json") as f:
    data = json.load(f)

model = SentenceTransformer("intfloat/multilingual-e5-base")


def encode(texts):
    prefixed = [f"query: {t}" for t in texts]
    return model.encode(prefixed, normalize_embeddings=True).tolist()


client = chromadb.PersistentClient(path="maindb")
collection = client.get_or_create_collection(
    name="faq",
    metadata={"hnsw:space": "cosine"}
)

texts = list(data.keys())
answers = list(data.values())
embeddings = encode(texts)

collection.add(
    ids=[f"id_{i}" for i in range(len(texts))],
    documents=texts,
    embeddings=embeddings,
    metadatas=[{"answer": ans} for ans in answers]
)


def dbsearch(question: str, n_results=3, threshold=0.85):
    q_emb = encode([question])

    resp = collection.query(
        query_embeddings=q_emb,
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )

    results = []
    for doc, meta, dist in zip(
            resp["documents"][0],
            resp["metadatas"][0],
            resp["distances"][0]
    ):
        similarity = 1 - dist
        if similarity >= threshold:
            results.append((doc, meta["answer"], similarity))

    if not results:
        return "в базе нет подходящего ответа"

    out = ""
    for i, (q, a, sim) in enumerate(results, start=1):
        out += (
            f"Совпадение №{i}: '{q}' "
            f"(similarity={sim:.3f})\n"
            f"Ответ: {a}\n\n"
        )

    return out.strip()


if __name__ == "__main__":
    question = input("Введите вопрос: ")
    print(dbsearch(question))
