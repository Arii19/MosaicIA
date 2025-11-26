import html
import os
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from main import answer_question, reset_user_memory

CHAT_MAX_WIDTH = 900
CHAT_INPUT_WRAPPER_ID = "chat-input-wrapper"

load_dotenv()
st.set_page_config(page_title="Mosaic Chat", page_icon="💬", layout="wide")

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


def criar_tabelas() -> None:
    Base.metadata.create_all(engine)


def salvar_chat(user_id: str, pergunta: str, resposta: str) -> None:
    session = Session()
    novo = ChatHistory(user_id=user_id, pergunta=pergunta, resposta=resposta)
    session.add(novo)
    session.commit()
    session.close()


def buscar_historico(user_id: str, limit: int = 20):
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
    style = """
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
            max-width: __CHAT_MAX_WIDTH__px !important;
            margin: 0 auto !important;
            padding: 40px 1.5rem 0 !important;
            padding-bottom: 220px !important;
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

        .chat-spacer {
            height: 200px !important;
        }

        .chat-title {
            font-size: 28px !important;
            font-weight: 600 !important;
            text-align: center !important;
            margin-bottom: 12px !important;
        }

        .chat-history-item {
            background: #2f313c !important;
            color: #ececf1 !important;
            padding: 0.8rem !important;
            border-radius: 8px !important;
            margin-bottom: 0.6rem !important;
            border: 1px solid rgba(255,255,255,0.05) !important;
        }

        [data-testid="stAppViewContainer"] > .main {
            padding-bottom: 260px !important;
        }

        div.block-container {
            padding-bottom: 0 !important;
            margin-bottom: 0 !important;
        }

        #__CHAT_INPUT_WRAPPER_ID__ {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            width: 100% !important;
            background: rgba(52,53,65,0.95) !important;
            padding: 16px 24px !important;
            z-index: 9999 !important;
            pointer-events: auto !important;
        }

        #__CHAT_INPUT_WRAPPER_ID__ .chat-input-inner {
            width: min(__CHAT_MAX_WIDTH__px, 100%) !important;
            margin: 0 auto !important;
            background-color: #40414f !important;
            border: 1px solid #565869 !important;
            border-radius: 14px !important;
            padding: 12px 16px 10px !important;
            box-sizing: border-box !important;
        }

        #__CHAT_INPUT_WRAPPER_ID__ .chat-input-inner [data-testid="column"] {
            padding: 0 !important;
        }

        #__CHAT_INPUT_WRAPPER_ID__ textarea {
            background-color: transparent !important;
            color: #ECECF1 !important;
            border: none !important;
            resize: none !important;
            font-size: 15px !important;
            line-height: 1.5 !important;
            padding-right: 12px !important;
        }

        #__CHAT_INPUT_WRAPPER_ID__ textarea:focus-visible {
            outline: none !important;
            box-shadow: none !important;
        }

        #__CHAT_INPUT_WRAPPER_ID__ .stButton button {
            width: 100% !important;
            height: 48px !important;
            border-radius: 10px !important;
            border: none !important;
            background: linear-gradient(135deg, #0a8f76 0%, #10a37f 100%) !important;
            color: white !important;
            font-weight: 600 !important;
            cursor: pointer !important;
        }

        #__CHAT_INPUT_WRAPPER_ID__ .stButton button:hover {
            background: linear-gradient(135deg, #10a37f 0%, #0a8f76 100%) !important;
        }
    </style>
    """
    style = style.replace("__CHAT_MAX_WIDTH__", str(CHAT_MAX_WIDTH)).replace(
        "__CHAT_INPUT_WRAPPER_ID__", CHAT_INPUT_WRAPPER_ID
    )
    st.markdown(style, unsafe_allow_html=True)


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

LOGO_SMARTBREEDER = "605e2afebb3af870a9d35b2f_smartbreederWhiteLogo.png"
LOGO_MOSAIC_CANDIDATES = "Copilot_20251124_232058.png"

mosaic_logo = LOGO_MOSAIC_CANDIDATES if Path(LOGO_MOSAIC_CANDIDATES).exists() else None

if mosaic_logo:
    st.sidebar.image(mosaic_logo, use_container_width=True)
else:
    st.sidebar.markdown(
        "<div style='text-align:center; font-size:22px; font-weight:600;'>Mosaic IA</div>",
        unsafe_allow_html=True,
    )

st.sidebar.image(LOGO_SMARTBREEDER, use_container_width=True)
st.sidebar.markdown("---")
st.sidebar.markdown("### Histórico de Conversas", unsafe_allow_html=True)
new_chat_clicked = st.sidebar.button("➕ Novo chat", use_container_width=True)

USER_ID = "ariane"
criar_tabelas()
historico = buscar_historico(USER_ID, limit=20)

if historico:
    for h in historico:
        st.sidebar.markdown(
            f"<div class='chat-history-item'><b>{h.pergunta}</b><br>"
            f"<small>{h.created_at.strftime('%d/%m %H:%M')}</small></div>",
            unsafe_allow_html=True,
        )
else:
    st.sidebar.info("Nenhuma conversa registrada ainda.")

if new_chat_clicked:
    st.session_state.messages = []
    st.session_state.reset_chat_input = False
    reset_user_memory(USER_ID)
    st.rerun()

if "messages" not in st.session_state or new_chat_clicked:
    st.session_state.messages = []
    for h in reversed(historico):
        st.session_state.messages.append({"role": "user", "content": h.pergunta})
        st.session_state.messages.append({"role": "assistant", "content": h.resposta})

st.markdown("<div class='chat-wrapper'>", unsafe_allow_html=True)
st.markdown("<div class='chat-title'>Mosaic Assistant</div>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    st.markdown(_render_message(msg["role"], msg["content"]), unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<div class='chat-spacer'></div>", unsafe_allow_html=True)

st.session_state.setdefault("chat_input", "")
st.session_state.setdefault("reset_chat_input", False)

if st.session_state.get("reset_chat_input", False):
    st.session_state.chat_input = ""
    st.session_state.reset_chat_input = False

input_container = st.container()
with input_container:
    cols = st.columns([0.85, 0.15], gap="small")
    with cols[0]:
        st.text_area("Digite sua mensagem:", key="chat_input", height=120, label_visibility="collapsed")
    with cols[1]:
        send_button = st.button("Enviar", use_container_width=True)

input_container.markdown(
    f"""
    <script>
    const assignChatWrapper = () => {{
        let textarea = document.querySelector('textarea[id^="chat_input"]');
        if (!textarea) {{
            const allAreas = Array.from(document.querySelectorAll('textarea[data-testid="stTextArea"]'));
            textarea = allAreas.length ? allAreas[allAreas.length - 1] : null;
        }}
        if (!textarea) {{
            window.setTimeout(assignChatWrapper, 50);
            return;
        }}
        const wrapper = textarea.closest('div[data-testid="stVerticalBlock"]');
        if (wrapper) {{
            wrapper.id = '{CHAT_INPUT_WRAPPER_ID}';
            wrapper.style.position = 'fixed';
            wrapper.style.left = '0';
            wrapper.style.right = '0';
            wrapper.style.bottom = '0';
            wrapper.style.width = '100%';
            wrapper.style.background = 'rgba(52,53,65,0.95)';
            wrapper.style.padding = '16px 24px';
            wrapper.style.zIndex = '9999';
        }}
        const inner = textarea.closest('div[data-testid="stHorizontalBlock"]');
        if (inner) {{
            inner.classList.add('chat-input-inner');
            inner.style.margin = '0 auto';
            inner.style.width = 'min({CHAT_MAX_WIDTH}px, 100%)';
            inner.style.backgroundColor = '#40414f';
            inner.style.border = '1px solid #565869';
            inner.style.borderRadius = '14px';
            inner.style.padding = '12px 16px 10px';
            inner.style.boxSizing = 'border-box';
        }}
    }};
    assignChatWrapper();
    </script>
    """,
    unsafe_allow_html=True,
)

if send_button:
    question = st.session_state.get("chat_input", "").strip()
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        resp = answer_question(question, user_id=USER_ID)
        resposta = resp.get("answer") if isinstance(resp, dict) else str(resp)
        st.session_state.messages.append({"role": "assistant", "content": resposta})
        salvar_chat(USER_ID, question, resposta)
        st.session_state.reset_chat_input = True
        st.rerun()
