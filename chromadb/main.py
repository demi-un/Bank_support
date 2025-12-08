import chromadb
from sentence_transformers import SentenceTransformer
import json


# data - словарь "вопрос": "ответ"
with open("data.json") as f:
    data = json.load(f) 


# инициализация векторизатора
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# создаём/подключаем Chroma
client = chromadb.PersistentClient(path="maindb")
collection = client.get_or_create_collection(
    name="faq",
    metadata={"hnsw:space": "cosine"}  # метрика расстояния
)

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
query = "Не отправляются документы через чат поддержки."
query_emb = model.encode([query]).tolist()

result = collection.query(
    query_embeddings=query_emb,
    n_results=3
)


# print(result)

questions = result['documents'][0]
results = []
for i in result['metadatas'][0]:
    results.append(i['answer'])


print(f"ИСХОДНЫЙ ВОПРОС: {query}\n")

for i in range(len(questions)):
    print(f"ВОПРОС {i}: ")
    print(questions[i])
    print(f"ОТВЕТ {i}: ")
    print(results[i])
    print("")
