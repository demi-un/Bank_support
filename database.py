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


def dbsearch(question: str, number_of_responses=2):
    question_emb = model.encode([question]).tolist()

    response = collection.query(
        query_embeddings=question_emb,
        n_results=number_of_responses
    )

    result = [[] for _ in range(number_of_responses)]

    response_questions = response['documents'][0]
    response_answers = []
    for answer in response['metadatas'][0]:
        response_answers.append(answer['answer'])
    for i in range(number_of_responses):
        result[i].append(response_questions[i])
        result[i].append(response_answers[i])

    return result


if __name__ == '__main__':
    question = input("Введите вопрос: ")
    result = dbsearch(question)
    print(result)
