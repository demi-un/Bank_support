# test_search.py - улучшенная версия
import chromadb

client = chromadb.PersistentClient(path="./chroma_db_sber")
collection = client.get_collection("sber_support_knowledge")

# Тестовые запросы
test_queries = [
    "Как сбросить пароль?",
    "Не работает VPN",
    "Как получить доступ к системе?",
    "Проблемы с почтой",
    "Ошибка при печати",
    "У меня не открывается 1С, что делать?"
]

for query in test_queries:
    print(f"\n{'='*50}")
    print(f"🔍 ПОИСК: '{query}'")
    print('='*50)
    
    results = collection.query(
        query_texts=[query],
        n_results=3  # Берем больше результатов
    )
    
    print("📄 Найдено документов:", len(results['documents'][0]))
    
    for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
        print(f"\n{i+1}. Документ (категория: {metadata.get('category', 'N/A')}):")
        print(f"   {doc}")
        if 'distances' in results:
            print(f"   Схожесть: {results['distances'][0][i]:.3f}")