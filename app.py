import os
from datetime import datetime
from typing import Generator, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import TIMESTAMP, Column, Integer, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from main import answer_question, reset_user_memory

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não configurado. Defina a variável de ambiente DATABASE_URL."
    )

engine = create_engine(DATABASE_URL)
Base = declarative_base()


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(64), nullable=False)
    pergunta = Column(Text, nullable=False)
    resposta = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def criar_tabelas() -> None:
    Base.metadata.create_all(engine)


class SourceSnippet(BaseModel):
    source: Optional[str] = None
    page: Optional[int] = None
    snippet: Optional[str] = None


class ChatRecord(BaseModel):
    id: int
    user_id: str
    question: str
    answer: str
    created_at: datetime
    sources: List[SourceSnippet] = Field(default_factory=list)

    class Config:
        orm_mode = True


class ChatRequest(BaseModel):
    user_id: str
    question: str


class ChatResponse(BaseModel):
    id: int
    user_id: str
    question: str
    answer: str
    created_at: datetime
    sources: List[SourceSnippet] = Field(default_factory=list)


app = FastAPI(title="Mosaic Chat API", version="1.0.0")


allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
]
origin_list = [origin.strip() for origin in allowed_origins.split(",") if origin.strip()] or default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    criar_tabelas()


def _extract_sources(raw_response: dict) -> List[SourceSnippet]:
    sources: List[SourceSnippet] = []
    raw_docs = raw_response.get("source_documents") or []

    for document in raw_docs:
        metadata = getattr(document, "metadata", {}) or {}
        snippet = getattr(document, "page_content", "") or ""
        sources.append(
            SourceSnippet(
                source=metadata.get("source")
                or metadata.get("file_path")
                or metadata.get("file"),
                page=metadata.get("page") or metadata.get("page_number"),
                snippet=snippet[:400].strip() or None,
            )
        )
    return sources


def _persist_chat(session: Session, user_id: str, pergunta: str, resposta: str) -> ChatHistory:
    registro = ChatHistory(user_id=user_id, pergunta=pergunta, resposta=resposta)
    session.add(registro)
    session.commit()
    session.refresh(registro)
    return registro


@app.get("/api/health", status_code=status.HTTP_200_OK)
def health_check() -> dict:
    return {"status": "ok"}


@app.get("/api/history/{user_id}", response_model=List[ChatRecord])
def listar_historico(
    user_id: str,
    limit: int = 50,
    session: Session = Depends(get_db),
) -> List[ChatRecord]:
    clean_user_id = user_id.strip()
    if not clean_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um identificador de usuário válido.",
        )

    registros = (
        session.query(ChatHistory)
        .filter_by(user_id=clean_user_id)
        .order_by(ChatHistory.created_at.asc())
        .limit(limit)
        .all()
    )
    return [
        ChatRecord(
            id=registro.id,
            user_id=registro.user_id,
            question=registro.pergunta,
            answer=registro.resposta,
            created_at=registro.created_at,
            sources=[],
        )
        for registro in registros
    ]


@app.post("/api/chat", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def enviar_pergunta(
    payload: ChatRequest, session: Session = Depends(get_db)
) -> ChatResponse:
    user_id = payload.user_id.strip()
    question = payload.question.strip()

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O identificador do usuário é obrigatório.",
        )

    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pergunta não pode estar vazia.",
        )

    raw_response = answer_question(question, user_id=user_id)
    answer = raw_response.get("answer") if isinstance(raw_response, dict) else str(raw_response)

    if isinstance(raw_response, dict):
        sources = _extract_sources(raw_response)
    else:
        sources = []

    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível obter uma resposta do modelo.",
        )

    registro = _persist_chat(session, user_id, question, answer)

    return ChatResponse(
        id=registro.id,
        user_id=registro.user_id,
        question=registro.pergunta,
        answer=registro.resposta,
        created_at=registro.created_at,
        sources=sources,
    )


@app.post("/api/reset/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def resetar_conversa(user_id: str) -> None:
    clean_user_id = user_id.strip()
    if not clean_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um identificador de usuário válido.",
        )

    reset_user_memory(clean_user_id)


@app.delete("/api/history/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_historico(user_id: str, session: Session = Depends(get_db)) -> None:
    clean_user_id = user_id.strip()
    if not clean_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe um identificador de usuário válido.",
        )

    session.query(ChatHistory).filter_by(user_id=clean_user_id).delete()
    session.commit()
    reset_user_memory(clean_user_id)
