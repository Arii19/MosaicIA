import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime
from main import rag_chain

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

# -------------------------
# Estilos customizados
# -------------------------
st.markdown("""
<style>
    .css-1d391kg { background-color: #1e1e2e; }
    .main { background-color: #0f0f23; color: white; }
    .chat-message {
        padding: 1rem; border-radius: 0.5rem; margin: 0.5rem 0;
        display: flex; align-items: flex-start;
    }
    .user-message {
        background: linear-gradient(135deg, #6b7c6e 0%, #5a8d8a 100%);
        margin-left: 20%; color: white;
    }
    .assistant-message {
        background: linear-gradient(135deg, #7d8a7f 0%, #4a6962 100%);
        margin-right: 20%; color: white;
    }
    .chat-input-container {
        position: fixed; bottom: 0; left: 0; right: 0;
        background-color: #0f0f23; padding: 1rem;
        border-top: 1px solid #4a676a;
        display: flex; gap: 10px;
    }
    .chat-input-container input {
        flex: 1;
        background-color: #32424a; color: white;
        border: 1px solid #4a676a; border-radius: 10px; padding: 0.8rem;
    }
    .chat-input-container input:focus {
        border: 2px solid #40e0d0 !important;
        outline: none !important;
        box-shadow: 0 0 10px rgba(64, 224, 208, 0.3) !important;
    }
    .chat-input-container button {
        background: linear-gradient(135deg, #3b5859 0%, #52a1a1 100%);
        color: white; border: none; border-radius: 10px;
        padding: 0.8rem 1.2rem; font-weight: bold;
        cursor: pointer;
    }
    .chat-input-container button:hover {
        background: linear-gradient(135deg, #52a1a1 0%, #3b5859 100%);
    }
    .chat-history-item {
        background-color: #2a2a3e;
        padding: 0.8rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        border-left: 3px solid #667eea;
        cursor: pointer;
        transition: all 0.3s ease;
        color: white;
    }
    .chat-history-item:hover {
        background-color: #3a3a4e;
        border-left-color: #93f8fb;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Sidebar com logo e histórico
# -------------------------
st.sidebar.image("605e2afebb3af870a9d35b2f_smartbreederWhiteLogo.png", use_container_width=True)
st.sidebar.markdown("---")
st.sidebar.markdown("### Histórico de Conversas")

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
if "messages" not in st.session_state:
    st.session_state.messages = []
    for h in reversed(historico):
        st.session_state.messages.append({"role": "user", "content": h.pergunta})
        st.session_state.messages.append({"role": "assistant", "content": h.resposta})

# -------------------------
# Renderizar mensagens
# -------------------------
st.title("💬Mosaic")

for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    if role == "user":
        st.markdown(f"<div class='chat-message user-message'>{content}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-message assistant-message'>{content}</div>", unsafe_allow_html=True)

# -------------------------
# Input fixo no rodapé
# -------------------------
with st.container():
    st.markdown("<div class='chat-input-container'>", unsafe_allow_html=True)
    chat_input = st.text_input("Digite sua mensagem:", key="chat_input", label_visibility="collapsed")
    send_button = st.button("Enviar")
    st.markdown("</div>", unsafe_allow_html=True)

if send_button and chat_input:
    st.session_state.messages.append({"role": "user", "content": chat_input})

    # 🔗 Chamada ao RAG/LLM
    resp = rag_chain.invoke({"question": chat_input, "user_id": USER_ID})
    resposta = resp.content if hasattr(resp, "content") else str(resp)

    st.session_state.messages.append({"role": "assistant", "content": resposta})
    salvar_chat(USER_ID, chat_input, resposta)

    st.rerun()
