# Mosaic IA Assistant

> Plataforma RAG que combina um backend FastAPI com frontend React para responder perguntas sobre documentação agrícola (PIMS) com apoio do Google Gemini.

## Visão Geral

- Assistente virtual orientado a documentos técnicos da Mosaic.
- Recupera trechos relevantes de markdowns em `docs/` e gera respostas contextuais.
- Cada usuário possui histórico persistido em banco relacional (`chat_history`).
- Interface web responsiva (sidebar + chat) consumindo a API REST `/api/*`.

## Principais Funcionalidades

- **RAG híbrido**: Ensemble FAISS (dense) + BM25 (lexical) para encontrar evidências.
- **LLM Google Gemini 2.5 Flash** com conversação contextual por usuário.
- **Histórico persistido** com reset individual e listagem diretamente na UI.
- **Frontend otimista** com atualização imediata e composer responsivo.
- **Conversão de PDFs** para Markdown via `converter_pdf_markdown.py` quando necessário.

## Arquitetura

```
[React/Vite SPA] --HTTP--> [FastAPI /api]
                          ├── LangChain RAG (FAISS + BM25)
                          ├── Google Generative AI (Gemini)
                          └── PostgreSQL (chat_history)
```

- Backend em Python 3.11 com FastAPI, SQLAlchemy e LangChain.
- Frontend em React 18 (Vite) com fetch nativo e CSS customizado.
- Documentos técnicos carregados em memória no primeiro uso e cacheados.

## Requisitos

- Python 3.11+
- Node.js 18+
- Chave Google Generative AI (`GOOGLE_API_KEY`)
- Banco compatível com SQLAlchemy (PostgreSQL recomendado)

## Configuração Rápida

### 1. Clonar o Repositório

```bash
git clone https://github.com/Arii19/MosaicIA.git
cd MosaicIA
```

### 2. Backend FastAPI

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Crie um arquivo .env na raiz
echo "DATABASE_URL=postgresql://user:pass@host:5432/db" >> .env
echo "GOOGLE_API_KEY=sua_chave" >> .env

# Executar localmente
uvicorn app:app --reload
```

Endpoints úteis: `GET /api/health`, `GET /api/history/{user_id}`, `POST /api/chat`.

### 3. Frontend React

```bash
cd frontend
npm install

# Configure o endpoint do backend
echo "VITE_API_URL=http://localhost:8000/api" > .env.local

# Ambiente de desenvolvimento
npm run dev

# Build de produção
npm run build
```

### 4. Documentos de Conhecimento

- Insira arquivos `.md` em `docs/`. Ex.: `DOC_SP_DES_INT_ESTIMATIVA_PIMS.md`.
- Para converter PDFs utilize `python converter_pdf_markdown.py`.

## Variáveis de Ambiente

| Nome               | Descrição                                        | Exemplo                           |
|--------------------|--------------------------------------------------|-----------------------------------|
| `DATABASE_URL`     | Conexão SQLAlchemy                               | `postgresql://user:pass@host/db`  |
| `GOOGLE_API_KEY`   | Chave Google Generative AI                       | `AIza...`                         |
| `ALLOWED_ORIGINS`  | Lista CSV com origens autorizadas no CORS        | `https://app.onrender.com`        |
| `VITE_API_URL`     | (Frontend) URL base da API                       | `https://backend/api`             |

## Scripts Úteis

| Comando                           | Descrição                              |
|-----------------------------------|----------------------------------------|
| `uvicorn app:app --reload`        | Executa API local com hot-reload       |
| `npm run dev` (frontend/)         | Inicia frontend em modo desenvolvimento|
| `npm run build` (frontend/)       | Gera artefatos estáticos para deploy   |
| `python converter_pdf_markdown.py`| Converte PDF para Markdown              |

## Estrutura de Diretórios

```
.
├─ app.py              # FastAPI + rotas REST
├─ main.py             # Pipeline LangChain / Gemini
├─ docs/               # Fonte de conhecimento em Markdown
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx       # Shell principal
│  │  ├─ hooks/useChat # Cliente REST + estado
│  │  └─ components/   # ChatWindow, Sidebar, MessageBubble
│  └─ public/          # Logos e assets
├─ Dockerfile          # Empacotamento do backend
├─ Procfile            # Comando para Render/Heroku
└─ requirements.txt    # Dependências Python
```

## Deploy (Render)

1. **Backend**: Web Service (Docker). Configure `DATABASE_URL`, `GOOGLE_API_KEY`, `ALLOWED_ORIGINS`. Health check em `/api/health`.
2. **Frontend**: Static Site com root `frontend`, build `npm install && npm run build` e publish `frontend/dist`. Defina `VITE_API_URL` com a URL pública do backend.
3. Se preferir servir o React pelo FastAPI, monte `StaticFiles` apontando para `frontend/dist` após executar o build durante a imagem Docker.

## Testes

- Ainda não há suíte oficial. Recomenda-se adicionar testes para as funções principais do RAG e para a API REST via `pytest`.

## Roadmap

- Adicionar autenticação de usuários.
- Persistir o índice FAISS em disco para reduzir cold start.
- Criar testes automatizados e monitoramento (logs estruturados, métricas).
- Otimizar `requirements.txt` removendo dependências legadas (ex.: Streamlit) quando não forem mais necessárias.

---

Feito com apoio do GPT-5-Codex e do time Mosaic para democratizar conhecimento agrícola.
