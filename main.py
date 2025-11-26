import os
from functools import lru_cache
from typing import Dict, Optional

from dotenv import load_dotenv
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.retrievers import EnsembleRetriever
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter


def _ensure_environment() -> None:
    """Load environment variables and ensure required keys are available."""

    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY não está definido. Configure no .env ou variável de ambiente."
        )

    os.environ["GOOGLE_API_KEY"] = google_api_key


@lru_cache(maxsize=1)
def _load_documents() -> list:
    """Load and split documents from the docs directory."""

    loader = DirectoryLoader(
        "docs/",
        glob="*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8", "autodetect_encoding": True},
    )
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ".", ",", ""],
    )

    chunks = splitter.split_documents(docs)
    return chunks


@lru_cache(maxsize=1)
def _build_ensemble_retriever() -> EnsembleRetriever:
    """Create a hybrid retriever combining BM25 and dense embeddings."""

    _ensure_environment()
    chunks = _load_documents()

    embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    embeddings_model = HuggingFaceEmbeddings(model_name=embedding_model_name)

    vectorstore = FAISS.from_documents(documents=chunks, embedding=embeddings_model)
    vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

    bm25_retriever = BM25Retriever.from_documents(chunks)
    bm25_retriever.k = 5

    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, vector_retriever],
        weights=[0.4, 0.6],
    )
    return ensemble_retriever


_USER_CHAINS: Dict[str, ConversationalRetrievalChain] = {}


def _create_chain() -> ConversationalRetrievalChain:
    """Construct a new conversational retrieval chain instance."""

    retriever = _build_ensemble_retriever()
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)

    memory = ConversationBufferMemory(
        memory_key="chat_history",
        output_key="answer",
        return_messages=True,
    )

    return ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        verbose=False,
        return_source_documents=True,
        get_chat_history=lambda history: "\n".join(
            [message.content for message in history]
        ),
    )


def get_rag_chain(user_id: Optional[str] = None) -> ConversationalRetrievalChain:
    """Expose a conversational retrieval chain for the given user."""

    cache_key = user_id or "default"
    if cache_key not in _USER_CHAINS:
        _USER_CHAINS[cache_key] = _create_chain()
    return _USER_CHAINS[cache_key]


def answer_question(question: str, user_id: Optional[str] = None) -> Dict:
    """Run the RAG pipeline for a question and return the raw chain output."""

    chain = get_rag_chain(user_id=user_id)
    return chain.invoke({"question": question})


def reset_user_memory(user_id: Optional[str] = None) -> None:
    """Clear cached chain (and memory) for a specific user."""

    cache_key = user_id or "default"
    _USER_CHAINS.pop(cache_key, None)


if __name__ == "__main__":
    response = answer_question("O que é a int.aplicinsumoagric?")
    print(response.get("answer", "[sem resposta]"))