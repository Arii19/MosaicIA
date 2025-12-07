import logging
import os
from collections import deque
from functools import lru_cache
from typing import Dict, List, Optional
from urllib.parse import urljoin, urldefrag

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from langchain.retrievers import EnsembleRetriever
from langchain_core.documents import Document
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import FAISS
from langchain_google_genai.chat_models import ChatGoogleGenerativeAI
from langchain_text_splitters import RecursiveCharacterTextSplitter


WIKI_BASE_URL = "https://gitlab.com/arii19-group/Arii19-project/-/wikis"
WIKI_HOME_URL = f"{WIKI_BASE_URL}/home"
WIKI_MAX_DEPTH_DEFAULT = 2
WIKI_MAX_PAGES_DEFAULT = 25
WIKI_REQUEST_TIMEOUT = 30

logger = logging.getLogger(__name__)


def _ensure_environment() -> None:
    """Carregar variáveis de ambiente e garantir que as chaves necessárias estejam disponíveis."""

    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY não está definido. Configure no .env ou variável de ambiente."
        )

    os.environ["GOOGLE_API_KEY"] = google_api_key


@lru_cache(maxsize=1)
def _fetch_wiki_documents(max_depth: int, max_pages: int) -> List[Document]:
    """Baixar páginas do wiki e retornar como documentos LangChain."""

    visited = set()
    documents: List[Document] = []
    queue = deque([(WIKI_HOME_URL, 0)])

    while queue and len(documents) < max_pages:
        current_url, depth = queue.popleft()
        normalized_url = urldefrag(current_url)[0].rstrip("/")

        if normalized_url in visited or depth > max_depth:
            continue

        try:
            response = requests.get(current_url, timeout=WIKI_REQUEST_TIMEOUT)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Falha ao buscar %s: %s", current_url, exc)
            visited.add(normalized_url)
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()

        content_container = (
            soup.find("div", id="wiki-content")
            or soup.find("div", class_="wiki")
            or soup.find("article")
            or soup.body
            or soup
        )

        page_text = content_container.get_text(separator="\n").strip() if content_container else ""

        if page_text:
            documents.append(
                Document(page_content=page_text, metadata={"source": normalized_url})
            )

        visited.add(normalized_url)

        if depth >= max_depth:
            continue

        for link in content_container.find_all("a", href=True) if content_container else []:
            href = link["href"].strip()
            if not href or href.startswith("#"):
                continue

            absolute_url = urljoin(current_url, href)
            absolute_url = urldefrag(absolute_url)[0].rstrip("/")

            if not absolute_url.startswith(WIKI_BASE_URL):
                continue

            if any(absolute_url.endswith(ext) for ext in (".pdf", ".png", ".jpg", ".jpeg", ".svg")):
                continue

            if absolute_url not in visited:
                queue.append((absolute_url, depth + 1))

    return documents


@lru_cache(maxsize=1)
def _load_documents() -> list:
    """Carregar e dividir documentos do wiki ou do diretório local."""

    try:
        max_depth = int(os.getenv("WIKI_MAX_DEPTH", str(WIKI_MAX_DEPTH_DEFAULT)))
    except ValueError:
        max_depth = WIKI_MAX_DEPTH_DEFAULT

    try:
        max_pages = int(os.getenv("WIKI_MAX_PAGES", str(WIKI_MAX_PAGES_DEFAULT)))
    except ValueError:
        max_pages = WIKI_MAX_PAGES_DEFAULT

    wiki_docs: List[Document] = []

    fetch_remote = os.getenv("FETCH_WIKI_DOCS", "1").lower() not in {"0", "false"}
    if fetch_remote:
        wiki_docs = _fetch_wiki_documents(max_depth=max_depth, max_pages=max_pages)

    if not wiki_docs:
        loader = DirectoryLoader(
            "docs/",
            glob="*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8", "autodetect_encoding": True},
        )
        docs = loader.load()
    else:
        docs = wiki_docs

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ".", ",", ""],
    )

    chunks = splitter.split_documents(docs)
    return chunks


@lru_cache(maxsize=1)
def _build_ensemble_retriever() -> EnsembleRetriever:
    """Criar um recuperador híbrido combinando BM25 e embeddings densos."""

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
    """Criar uma nova instância de cadeia de recuperação de conversas.."""

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
    """Disponibilizar uma cadeia de recuperação de conversas para o usuário indicado."""

    cache_key = user_id or "default"
    if cache_key not in _USER_CHAINS:
        _USER_CHAINS[cache_key] = _create_chain()
    return _USER_CHAINS[cache_key]


def answer_question(question: str, user_id: Optional[str] = None) -> Dict:
    """Executar o pipeline RAG para uma pergunta e retornar a saída bruta da cadeia."""

    chain = get_rag_chain(user_id=user_id)
    return chain.invoke({"question": question})


def reset_user_memory(user_id: Optional[str] = None) -> None:
    """Limpar a cadeia em cache (e memória) para um usuário específico."""

    cache_key = user_id or "default"
    _USER_CHAINS.pop(cache_key, None)


if __name__ == "__main__":
    response = answer_question("O que é a int.aplicinsumoagric?")
    print(response.get("answer", "[sem resposta]"))