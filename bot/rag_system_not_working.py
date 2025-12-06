# rag_system.py 
import chromadb
from langchain_chroma import Chroma  
from langchain_huggingface import HuggingFaceEmbeddings  
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

class SberSupportRAG:
    def __init__(self):
        # 1. Инициализируем эмбеддинги
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )
        
        # 2. Подключаемся к существующей ChromaDB
        self.client = chromadb.PersistentClient(path="./chroma_db_sber")
        
        # 3. Создаем LangChain векторное хранилище
        self.vectorstore = Chroma(
            client=self.client,
            collection_name="sber_support_knowledge",
            embedding_function=self.embeddings.embed_documents
        )
        
        # 4. Создаем ретривер
        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": 3}
        )
        
        # 5. Настраиваем промпт
        self.prompt_template = """Ты - помощник службы поддержки Сбербанка.
        
Используй информацию из базы знаний, чтобы ответить на вопрос.
Если информации недостаточно, предложи обратиться в службу поддержки по телефону 8-800-555-00-00.

Контекст: {context}

Вопрос: {question}

Полезный, подробный ответ на русском языке:"""
        
        self.PROMPT = PromptTemplate(
            template=self.prompt_template,
            input_variables=["context", "question"]
        )
        
        # 6. Инициализируем модель qwen2.5:3b
        print("🔄 Загружаем модель qwen2.5:3b...")
        self.llm = Ollama(
            model="qwen2.5:3b",
            temperature=0.3,
            num_predict=300
        )
        
        # 7. Создаем цепочку RAG
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=self.retriever,
            chain_type_kwargs={"prompt": self.PROMPT},
            return_source_documents=True
        )
    
    def get_answer(self, question):
        """Получаем ответ на вопрос"""
        try:
            result = self.qa_chain({"query": question})
            return {
                "answer": result["result"],
                "sources": result.get("source_documents", [])
            }
        except Exception as e:
            print(f"Ошибка при получении ответа: {e}")
            # Fallback
            docs = self.vectorstore.similarity_search(question, k=2)
            answer = "\n\n".join([doc.page_content for doc in docs])
            return {
                "answer": f"Вот что найдено в базе знаний:\n\n{answer}",
                "sources": docs
            }

# Тестируем систему
if __name__ == "__main__":
    print("🧪 Тестирование RAG системы...")
    rag = SberSupportRAG()
    
    test_questions = [
        "Как сбросить пароль?",
        "У меня не работает VPN, что делать?",
        "Как получить доступ к системе отчетности?"
    ]
    
    for question in test_questions:
        print(f"\n{'='*60}")
        print(f"❓ Вопрос: {question}")
        result = rag.get_answer(question)
        print(f"🤖 Ответ: {result['answer'][:200]}...")
        if result['sources']:
            print(f"📚 Источников: {len(result['sources'])}")