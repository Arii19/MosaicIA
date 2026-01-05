import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

import requests
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


GITLAB_API_BASE = "https://gitlab.com/api/v4"
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


def _fetch_wiki_documents(max_depth: int, max_pages: int) -> List[Document]:
    """Baixar páginas do wiki via API oficial do GitLab usando tokens privados."""

    project_id = (os.getenv("PROJECT_ID") or "").strip()
    token = (os.getenv("GITLAB_TOKEN") or "").strip()

    if not project_id:
        raise RuntimeError("PROJECT_ID não está definido. Configure o ID numérico ou path do projeto GitLab.")

    if not token:
        raise RuntimeError(
            "GITLAB_TOKEN não está definido. Gere um token de acesso pessoal com escopo api/read_api e configure-o."
        )

    encoded_project = quote_plus(project_id)
    session = requests.Session()
    session.headers.update({"PRIVATE-TOKEN": token})

    slug_env = os.getenv("WIKI_PAGE_SLUGS", "")
    requested_slugs = [slug.strip() for slug in slug_env.split(",") if slug.strip()]

    def _list_slugs() -> List[str]:
        if requested_slugs:
            return requested_slugs[:max_pages]

        slugs: List[str] = []
        page = 1
        while len(slugs) < max_pages:
            response = session.get(
                f"{GITLAB_API_BASE}/projects/{encoded_project}/wikis",
                params={"per_page": 100, "page": page},
                timeout=WIKI_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            if not payload:
                break
            for entry in payload:
                slug = entry.get("slug")
                if slug:
                    slugs.append(slug)
                    if len(slugs) >= max_pages:
                        break
            page += 1
        return slugs

    documents: List[Document] = []
    for slug in _list_slugs():
        try:
            response = session.get(
                f"{GITLAB_API_BASE}/projects/{encoded_project}/wikis/{quote_plus(slug)}",
                timeout=WIKI_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.HTTPError as exc:
            status_code = exc.response.status_code if exc.response else None
            if status_code in {401, 403}:
                raise RuntimeError(
                    "Token GitLab sem acesso à wiki privada. Garanta que o token possui escopo api/read_api no projeto."
                ) from exc
            logger.warning("Falha ao baixar a página %s: %s", slug, exc)
            continue
        except requests.RequestException as exc:
            logger.warning("Falha ao baixar a página %s: %s", slug, exc)
            continue

        content = payload.get("content", "").strip()
        title = payload.get("title") or slug
        if not content:
            continue

        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": f"gitlab-wiki:{slug}",
                    "title": title,
                },
            )
        )

        if len(documents) >= max_pages:
            break

    return documents


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
    docs_path = Path("docs")

    fetch_remote = os.getenv("FETCH_WIKI_DOCS", "1").lower() not in {"0", "false"}
    if fetch_remote:
        try:
            wiki_docs = _fetch_wiki_documents(max_depth=max_depth, max_pages=max_pages)
        except RuntimeError as remote_error:
            logger.warning("Falha ao baixar wiki remoto: %s", remote_error)
            if not docs_path.exists():
                raise RuntimeError(
                    "Não foi possível carregar o wiki remoto e a pasta docs/ não existe. Verifique o GITLAB_TOKEN ou disponibilize arquivos Markdown locais em docs/."
                ) from remote_error

    if not wiki_docs:
        if not docs_path.exists():
            raise FileNotFoundError(
                "A pasta docs/ não foi encontrada. Crie docs/ com arquivos .md ou habilite FETCH_WIKI_DOCS com GITLAB_TOKEN válido."
            )

        loader = DirectoryLoader(
            str(docs_path),
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


_USER_MEMORIES: Dict[str, ConversationBufferMemory] = {}


def _get_user_memory(user_id: Optional[str]) -> ConversationBufferMemory:
    cache_key = (user_id or "default").strip() or "default"
    if cache_key not in _USER_MEMORIES:
        _USER_MEMORIES[cache_key] = ConversationBufferMemory(
            memory_key="chat_history",
            output_key="answer",
            return_messages=True,
        )
    return _USER_MEMORIES[cache_key]


def _create_chain(memory: ConversationBufferMemory) -> ConversationalRetrievalChain:
    """Criar uma nova instância de cadeia de recuperação de conversas.."""

    retriever = _build_ensemble_retriever()
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)

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

def run_rag_pipeline(question: str, user_id: Optional[str] = None) -> Dict:
    """Executar o pipeline RAG sem cache para cada pergunta enviada."""

    memory = _get_user_memory(user_id)
    chain = _create_chain(memory)
    sanitized_question = (question or "").strip()
    if not sanitized_question:
        raise ValueError("Pergunta vazia não pode ser processada.")
    return chain.invoke({"question": sanitized_question})


def reset_user_memory(user_id: Optional[str] = None) -> None:
    """Limpar a memória de conversa armazenada para um usuário."""

    cache_key = (user_id or "default").strip() or "default"
    _USER_MEMORIES.pop(cache_key, None)


if __name__ == "__main__":
    response = run_rag_pipeline("O que é a int.aplicinsumoagric?")
    print(response.get("answer", "[sem resposta]"))