import chromadb
from sentence_transformers import SentenceTransformer

# инициализация векторизатора
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# создаём/подключаем Chroma
client = chromadb.PersistentClient(path="maindb")
collection = client.get_or_create_collection(
    name="faq",
    metadata={"hnsw:space": "cosine"}  # метрика расстояния
)

# данные
data = {
    "Как зовут основателя UNIBANK": "demi-un",
    "Как заблокировать карту": (
        "В приложении банка перейти к списку карт, "
        "нажать на нужную карту, открыть настройки, выбрать «Блокировка»."
    )
}

# формируем списки
texts = list(data.keys())
answers = list(data.values())
embeddings = model.encode(texts).tolist()

# добавляем в коллекцию
collection.add(
    ids=[f"id_{i}" for i in range(len(texts))],
    documents=texts,
    embeddings=embeddings,
    metadatas=[{"answer": ans} for ans in answers]
)


# поиск в db
query = "Что делать если потерял карту?"
query_emb = model.encode([query]).tolist()

result = collection.query(
    query_embeddings=query_emb,
    n_results=1
)

print(result)
