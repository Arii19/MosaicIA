import os
from typing import List
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import Document
from langchain.schema.runnable import RunnablePassthrough

# -------------------------
# Banco de dados
# -------------------------
DATABASE_URL = os.getenv("DATABASE_URL")  # Ex: 'postgresql://user:pass@host:port/dbname'
engine = create_engine(DATABASE_URL)
Base = declarative_base()

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(64))
    pergunta = Column(Text)
    resposta = Column(Text)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

Session = sessionmaker(bind=engine)

def criar_tabelas():
    Base.metadata.create_all(engine)

def salvar_chat(user_id, pergunta, resposta):
    session = Session()
    novo = ChatHistory(user_id=user_id, pergunta=pergunta, resposta=resposta)
    session.add(novo)
    session.commit()
    session.close()

def buscar_historico(user_id, limit=20):
    session = Session()
    historico = (
        session.query(ChatHistory)
        .filter_by(user_id=user_id)
        .order_by(ChatHistory.created_at.asc())  # ordem cronológica
        .limit(limit)
        .all()
    )
    session.close()
    return historico

# -------------------------
# LLM
# -------------------------
def get_llm():
    return ChatGoogleGenerativeAI(
        model="models/gemma-3-27b-it",
        google_api_key=os.getenv("API_KEY"),
        temperature=0.1,
        convert_system_message_to_human=True
    )

# -------------------------
# Configurações
# -------------------------
DOCS_PATH = "./doc"
HF_EMBEDDINGS_MODEL = "intfloat/multilingual-e5-base"
FAISS_INDEX_PATH = "./faiss_index"

# -------------------------
# Carregar arquivos locais
# -------------------------
def load_markdown_docs(path: str) -> List[Document]:
    docs = []
    for root, _, files in os.walk(path):
        for f in files:
            if f.lower().endswith((".md", ".markdown")):
                full_path = os.path.join(root, f)
                with open(full_path, "r", encoding="utf-8") as fp:
                    content = fp.read()
                docs.append(Document(page_content=content, metadata={"source": full_path}))
    return docs

# -------------------------
# Splitters e Embeddings
# -------------------------
def split_markdown_docs(docs: List[Document]) -> List[Document]:
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")]
    )
    hierarchical_docs: List[Document] = []
    for d in docs:
        try:
            parts = header_splitter.split_text(d.page_content)
            for p in parts:
                p.metadata.update(d.metadata)
            hierarchical_docs.extend(parts)
        except Exception:
            hierarchical_docs.append(d)

    chunk_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, chunk_overlap=200,
        separators=["\n## ", "\n### ", "\n", " ", ""]
    )
    return chunk_splitter.split_documents(hierarchical_docs)

def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name=HF_EMBEDDINGS_MODEL,
        encode_kwargs={"normalize_embeddings": True}
    )

# -------------------------
# Vetorstore (FAISS)
# -------------------------
def build_or_load_vectorstore(chunks: List[Document]) -> FAISS:
    embeddings = get_embeddings()
    if os.path.isdir(FAISS_INDEX_PATH) and os.path.exists(os.path.join(FAISS_INDEX_PATH, "index.faiss")):
        print(f"[INFO] Carregando índice FAISS de {FAISS_INDEX_PATH}")
        vs = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    else:
        print("[INFO] Construindo novo índice FAISS...")
        vs = FAISS.from_documents(chunks, embeddings)
        vs.save_local(FAISS_INDEX_PATH)
    return vs

# -------------------------
# Prompt RAG + histórico
# -------------------------
SYSTEM_PROMPT = (
    "Você é uma IA de suporte técnico e documentação. Responda com precisão e cite trechos do contexto "
    "quando útil. Se a informação não estiver no contexto, diga claramente que não encontrou evidência."
)

RAG_PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    MessagesPlaceholder("context"),
    MessagesPlaceholder("history"),
    ("human", "{question}")
])

def format_context_for_messages(docs: List[Document]) -> List[dict]:
    msgs = []
    for i, d in enumerate(docs, start=1):
        snippet = d.page_content
        src = d.metadata.get("source", "desconhecido")
        msgs.append({"role": "system", "content": f"[Contexto {i} - {src}]\n{snippet}"})
    return msgs

def build_rag_chain(vectorstore: FAISS):
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 5})
    llm = get_llm()

    def retrieve_docs(inputs):
        query = inputs["question"]
        user_id = inputs.get("user_id", "default")
        docs = retriever.get_relevant_documents(query)

        # buscar histórico do banco
        historico = buscar_historico(user_id, limit=20)
        history_msgs = []
        for h in historico:
            history_msgs.append({"role": "human", "content": h.pergunta})
            history_msgs.append({"role": "assistant", "content": h.resposta})

        return {
            "context": format_context_for_messages(docs),
            "history": history_msgs,
            "question": query,
            "user_id": user_id
        }

    chain = (
        RunnablePassthrough.assign(**retrieve_docs)
        | RAG_PROMPT
        | llm
    )
    return chain

# -------------------------
# Execução direta
# -------------------------
criar_tabelas()
docs = load_markdown_docs(DOCS_PATH)
chunks = split_markdown_docs(docs)
vs = build_or_load_vectorstore(chunks)
rag_chain = build_rag_chain(vs)

if __name__ == "__main__":
    user_id = "ariane"

    q1 = "Como configurar o ambiente descrito no README?"
    print(f"\n[Q] {q1}")
    resp1 = rag_chain.invoke({"question": q1, "user_id": user_id})
    resposta1 = resp1.content if hasattr(resp1, "content") else str(resp1)
    print("\n[A]", resposta1)
    salvar_chat(user_id, q1, resposta1)

    q2 = "E quais são os requisitos mínimos para rodar esse ambiente?"
    print(f"\n[Q] {q2}")
    resp2 = rag_chain.invoke({"question": q2, "user_id": user_id})
    resposta2 = resp2.content if hasattr(resp2, "content") else str(resp2)
    print("\n[A]", resposta2)
    salvar_chat(user_id, q2, resposta2)
