import html
import os
from pathlib import Path
from datetime import datetime
from functools import lru_cache

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from main import answer_question

load_dotenv()
st.set_page_config(page_title="Mosaic Chat", page_icon="💬", layout="wide")

# -------------------------
# Configuração do banco
# -------------------------
DATABASE_URL = os.getenv("DATABASE_URL")
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
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    session.close()
    return historico

def _inject_chatgpt_theme() -> None:
    st.markdown(
        """
    <style>
        html, body, [data-testid="stAppViewContainer"], .main {
            background-color: #343541 !important;
            color: #ECECF1 !important;
            overflow-x: hidden !important;
            transform: none !important;
        }

        [data-testid="stAppViewContainer"] > .main {
            transform: none !important;
        }

        [data-testid="stSidebar"] {
            background-color: #202123 !important;
            color: #ECECF1 !important;
        }

        .chat-wrapper {
            max-width: 900px !important;
            margin: 0 auto !important;
            padding: 40px 1.5rem 0 !important;
            padding-bottom: 220px !important; /* espaço para o campo fixado */
        }

        .chat-message {
            display: flex !important;
            gap: 16px !important;
            padding: 24px 0 !important;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08) !important;
        }

        .chat-message .avatar {
            width: 32px !important;
            height: 32px !important;
            border-radius: 4px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            font-size: 18px !important;
            font-weight: 600 !important;
            color: #fff !important;
        }

        .assistant-message .avatar {
            background-color: #10a37f !important;
        }

        .user-message .avatar {
            background-color: #2f7bff !important;
        }

        .chat-message .message-content {
            flex: 1 !important;
            font-size: 15px !important;
            line-height: 1.6 !important;
            white-space: pre-wrap !important;
            word-break: break-word !important;
        }

        .assistant-message .message-content {
            background-color: #444654 !important;
            border-radius: 8px !important;
            padding: 16px !important;
        }

        .user-message {
            justify-content: flex-end !important;
        }

        .user-message .message-content {
            background-color: #343541 !important;
            border: 1px solid #565869 !important;
            border-radius: 8px !important;
            padding: 16px !important;
        }

        div[data-testid="stForm"] {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            display: flex !important;
            justify-content: center !important;
            padding: 18px 24px 26px !important;
            background: linear-gradient(180deg, rgba(52,53,65,0) 0%, rgba(52,53,65,0.85) 55%, rgba(52,53,65,0.95) 100%) !important;
            border-top: 1px solid rgba(255,255,255,0.12) !important;
            z-index: 9999 !important;
            pointer-events: auto !important; /* corrigido aqui */
            box-sizing: border-box !important;
        }

        div[data-testid="stForm"] > form,
        form[data-testid="stForm"] {
            width: min(900px, 100%) !important;
            background-color: #40414f !important;
            border: 1px solid #565869 !important;
            border-radius: 14px !important;
            padding: 12px 16px 8px !important;
            pointer-events: auto !important;
            box-sizing: border-box !important;
            min-height: 100px !important;
        }

        div[data-testid="stForm"] textarea {
            background-color: transparent !important;
            color: #ECECF1 !important;
            border: none !important;
            resize: none !important;
            font-size: 15px !important;
            line-height: 1.5 !important;
        }

        div[data-testid="stForm"] textarea:focus-visible {
            outline: none !important;
            box-shadow: none !important;
        }

        div[data-testid="stFormSubmitButton"] button {
            width: 100% !important;
            height: 48px !important;
            border-radius: 10px !important;
            border: none !important;
            background: linear-gradient(135deg, #0a8f76 0%, #10a37f 100%) !important;
            color: white !important;
            font-weight: 600 !important;
            cursor: pointer !important;
        }

        div[data-testid="stFormSubmitButton"] button:hover {
            background: linear-gradient(135deg, #10a37f 0%, #0a8f76 100%) !important;
        }

        .chat-spacer {
            height: 200px !important;
        }

        .chat-title {
            font-size: 28px !important;
            font-weight: 600 !important;
            text-align: center !important;
            margin-bottom: 12px !important;
        }

        .sidebar-title {
            color: #ECECF1 !important;
        }

        .chat-history-item {
            background: #2f313c !important;
            color: #ececf1 !important;
            padding: 0.8rem !important;
            border-radius: 8px !important;
            margin-bottom: 0.6rem !important;
            border: 1px solid rgba(255,255,255,0.05) !important;
        }
   </style>

                """,
        unsafe_allow_html=True,
    )


def _render_message(role: str, content: str) -> str:
    avatar = "🧑" if role == "user" else "🤖"
    safe_content = html.escape(content).replace("\n", "<br>")
    role_class = "user-message" if role == "user" else "assistant-message"
    return (
        f"<div class='chat-message {role_class}'>"
        f"<div class='avatar'>{avatar}</div>"
        f"<div class='message-content'>{safe_content}</div>"
        "</div>"
    )

_inject_chatgpt_theme()

# -------------------------
# Sidebar com logo e histórico
# -------------------------
LOGO_SMARTBREEDER = "605e2afebb3af870a9d35b2f_smartbreederWhiteLogo.png"
LOGO_MOSAIC_CANDIDATES = "Copilot_20251124_232058.png"

mosaic_logo = LOGO_MOSAIC_CANDIDATES if Path(LOGO_MOSAIC_CANDIDATES).exists() else None

if mosaic_logo:
    st.sidebar.image(mosaic_logo, width="stretch")
else:
    st.sidebar.markdown("<div style='text-align:center; font-size:22px; font-weight:600;'>Mosaic IA</div>", unsafe_allow_html=True)

st.sidebar.image(LOGO_SMARTBREEDER, width="stretch")
st.sidebar.markdown("---")
st.sidebar.markdown("### Histórico de Conversas", unsafe_allow_html=True)
new_chat_clicked = st.sidebar.button("➕ Novo chat", use_container_width=True)

USER_ID = "ariane"
criar_tabelas()
historico = buscar_historico(USER_ID, limit=20)

if historico:
    for h in historico:
        st.sidebar.markdown(
            f"<div class='chat-history-item'><b>{h.pergunta}</b><br><small>{h.created_at.strftime('%d/%m %H:%M')}</small></div>",
            unsafe_allow_html=True
        )
else:
    st.sidebar.info("Nenhuma conversa registrada ainda.")

# -------------------------
# Inicialização do chat
# -------------------------
if new_chat_clicked:
    st.session_state.messages = []
    st.rerun()

if "messages" not in st.session_state or new_chat_clicked:
    st.session_state.messages = []
    for h in reversed(historico):
        st.session_state.messages.append({"role": "user", "content": h.pergunta})
        st.session_state.messages.append({"role": "assistant", "content": h.resposta})

# -------------------------
# Renderizar mensagens
# -------------------------
st.markdown("<div class='chat-wrapper'>", unsafe_allow_html=True)
st.markdown("<div class='chat-title'>Mosaic Assistant</div>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    st.markdown(_render_message(msg["role"], msg["content"]), unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<div class='chat-spacer'></div>", unsafe_allow_html=True)

# -------------------------
# Campo de entrada fixado
# -------------------------
form_placeholder = st.empty()
with form_placeholder.form("chat_form", clear_on_submit=True):
    cols = st.columns([0.85, 0.15])
    with cols[0]:
        chat_input = st.text_area("Digite sua mensagem:", key="chat_input", height=120, label_visibility="collapsed")
    with cols[1]:
        send_button = st.form_submit_button("Enviar")

if send_button and chat_input:
    question = chat_input.strip()
    if question:
        st.session_state.messages.append({"role": "user", "content": question})

        resp = answer_question(question, user_id=USER_ID)
        resposta = resp.get("answer") if isinstance(resp, dict) else str(resp)

        st.session_state.messages.append({"role": "assistant", "content": resposta})
        salvar_chat(USER_ID, question, resposta)

        st.rerun()

# -------------------------
# CSS adicional
# -------------------------
st.markdown(
    """
    <style>
        [data-testid="stAppViewContainer"] {
            transform: none !important;
        }

        .chat-wrapper {
            padding-bottom: 220px !important;
        }

        div[data-testid="stForm"] {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            z-index: 9999 !important;
            background: rgba(52,53,65,0.95) !important;
            pointer-events: auto !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)
