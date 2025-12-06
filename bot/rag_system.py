# rag_system.py - финальная версия
import chromadb
import os
from sentence_transformers import SentenceTransformer

print("🚀 Инициализация RAG системы...")

class SberSupportRAG:
    def __init__(self):
        print("Инициализация RAG...")
        try:
            # 1. Загружаем модель для эмбеддингов
            print("Загружаем модель для эмбеддингов...")
            self.embedding_model = SentenceTransformer(
                'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
            )
            
            # 2. ПОДКЛЮЧАЕМСЯ К БАЗЕ - ВАЖНО!
            # Текущая директория (где rag_system.py): bot/
            # База находится на уровень выше: Bank_support/chroma_db_sber/
            current_dir = os.path.dirname(os.path.abspath(__file__))  # bot/
            parent_dir = os.path.dirname(current_dir)                 # Bank_support/
            db_path = os.path.join(parent_dir, "chroma_db_sber")      # Bank_support/chroma_db_sber/
            
            print(f"🔍 Ищем базу по пути: {db_path}")
            
            if not os.path.exists(db_path):
                print(f"❌ Папка не найдена: {db_path}")
                print("💡 Создайте базу: python sber_knowledge.py")
                raise FileNotFoundError(f"База не найдена: {db_path}")
            
            self.client = chromadb.PersistentClient(path=db_path)
            self.collection = self.client.get_collection("sber_support_knowledge")
            
            # 3. Инициализируем Ollama
            from langchain_community.llms import Ollama
            print("Загружаем модель qwen2.5:3b...")
            self.llm = Ollama(model="qwen2.5:3b", temperature=0.3)
            
            print(f"✅ RAG система готова! Документов: {self.collection.count()}")
            
        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")
            print("⚠️ Переходим в упрощенный режим")
            self.collection = None
            self.llm = None
    
    def get_answer(self, question):
        """Получаем ответ на вопрос"""
        if self.collection is None:
            return {
                "answer": "🔄 Система загружается...\nПока можете позвонить: 8-800-555-00-00",
                "sources": []
            }
        
        try:
            # Ищем похожие документы
            results = self.collection.query(
                query_texts=[question],
                n_results=3
            )
            
            if not results['documents'] or not results['documents'][0]:
                return {
                    "answer": "📭 Информация не найдена.\n📞 Обратитесь в поддержку: 8-800-555-00-00",
                    "sources": []
                }
            
            docs = results['documents'][0]
            
            # Если есть LLM - используем ее
            if self.llm:
                try:
                    # Формируем контекст
                    context = "\n\n".join(docs)
                    
                    # Промпт
                    prompt = f"""Ты - помощник IT-поддержки Сбербанка.

Информация из базы:
{context}

Вопрос сотрудника: {question}

Дай четкий ответ на русском. Если информации мало, предложи позвонить 8-800-555-00-00.

Ответ:"""
                    
                    print("🤖 Генерируем ответ через LLM...")
                    answer = self.llm.invoke(prompt)
                    
                    return {
                        "answer": answer,
                        "sources": docs
                    }
                    
                except Exception as llm_error:
                    print(f"⚠️ Ошибка LLM: {llm_error}")
                    # Fallback на простой поиск
            
            # Упрощенный ответ (без LLM)
            answer_parts = []
            for i, doc in enumerate(docs, 1):
                answer_parts.append(f"{i}. {doc}")
            
            answer = "📚 Найдено в базе знаний:\n\n" + "\n\n".join(answer_parts)
            answer += "\n\n📞 Для уточнений звоните: 8-800-555-00-00"
            
            return {
                "answer": answer,
                "sources": docs
            }
                
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
            return {
                "answer": "⚠️ Ошибка поиска.\n📞 Обратитесь в поддержку: 8-800-555-00-00",
                "sources": []
            }

# ========== ТЕСТ СИСТЕМЫ ==========
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 ТЕСТ RAG СИСТЕМЫ")
    print("=" * 50)
    
    rag = SberSupportRAG()
    
    if rag.collection:
        test_questions = [
            "Как сбросить пароль?",
            "Не работает VPN",
            "Как получить доступ к системе?"
        ]
        
        for question in test_questions:
            print(f"\n{'─' * 40}")
            print(f"❓ Вопрос: {question}")
            result = rag.get_answer(question)
            print(f"📏 Длина ответа: {len(result['answer'])} символов")
            print(f"🤖 Ответ: {result['answer'][:200]}...")
    else:
        print("❌ RAG система не загрузилась!")
        print("💡 Проверьте:")
        print("1. База chroma_db_sber в корне проекта")
        print("2. Запустите: python sber_knowledge.py")
        print("3. Убедитесь, что Ollama запущен")