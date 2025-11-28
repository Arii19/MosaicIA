# Documentacao Executiva - Mosaic IA Assistant

## Visao Geral

- Assistente virtual para equipes agricolas com foco em consolidar e explicar fluxos PIMS e RN internas.
- Arquitetura de duas camadas: API FastAPI + frontend React responsivo (Vite) consumindo pipeline RAG.
- Base de conhecimento formada pelos markdowns em `docs/` convertidos a partir de PDFs tecnicos.
- Persistencia de conversas por usuario, permitindo memoria contextual e retomada de historico.

## Objetivos de Valor

1. Democratizar o acesso rapido a informacoes operacionais criticas (safras, procedimentos, integrações).
2. Reduzir dependencia de especialistas para consultas recorrentes e liberar tempo para analise.
3. Padronizar respostas com citações internas, mantendo auditabilidade e confianca.
4. Preparar terreno para automacoes futuras (ativacao de fluxos, abertura de chamados, analise de indicadores).

## Arquitetura de Alto Nivel

```
[Frontend React] --HTTP--> [FastAPI /api/*] --invoca--> [Pipeline RAG LangChain]
                                          \--SQLAlchemy--> [PostgreSQL chat_history]
                                          \--DirectoryLoader--> [docs/*.md]
```

- Frontend Vite + React 18 hospedado em static hosting (Render, Netlify ou Vercel).
- Backend FastAPI em gunicorn/uvicorn (Docker ou Render web service) expondo endpoints REST.
- Pipeline RAG carrega documentos em memoria na primeira chamada e combina FAISS + BM25 para recuperar contextos.
- Modelo generativo Gemini 2.5 Flash via Google Generative AI para redacao final.
- Historico persistido em tabela `chat_history` para auditoria e reconstrucao de memoria por usuario.

## Backend FastAPI (`app.py`)

- Endpoints principais:
  - `GET /api/health` bem-estar da aplicacao.
  - `GET /api/history/{user_id}` retorna historico paginado (default 50 itens, ordenado por data ascendente).
  - `POST /api/chat` recebe `user_id` e `question`, dispara pipeline RAG e grava resposta.
  - `POST /api/reset/{user_id}` limpa memoria em cache para usuario.
  - `DELETE /api/history/{user_id}` remove registros persistidos e reseta memoria.
- Modelo `ChatHistory` (SQLAlchemy) com campos `id`, `user_id`, `pergunta`, `resposta`, `created_at`.
- Middleware CORS controlado por `ALLOWED_ORIGINS` (fallback: localhost dev ports 5173/4173).
- Funcoes internas:
  - `_extract_sources` interpreta dicionario vindo da cadeia LangChain para mapear snippets (atualmente nao exibidos no frontend, mas mantidos no payload persistido).
  - `_persist_chat` garante commit atomico e retorna registro fresco para resposta HTTP.
- `startup_event` cria tabela automaticamente ao iniciar (ideal apenas para ambientes com permissao DDL).
- Dependencias sensiveis: `DATABASE_URL`, `GOOGLE_API_KEY`, `ALLOWED_ORIGINS` (opcional) lidas via `.env`.

## Pipeline RAG (`main.py`)

- `_ensure_environment` garante `GOOGLE_API_KEY` carregado antes de inicializar o LLM.
- `_load_documents` usa `DirectoryLoader` para ler `docs/*.md`, aplica `RecursiveCharacterTextSplitter` (chunk 1200 chars, overlap 150); memoiza via `lru_cache` (carregamento unico por processo).
- `_build_ensemble_retriever` cria:
  - Embeddings `sentence-transformers/all-MiniLM-L6-v2` (Faiss `k=5`).
  - Retriever BM25 (k=5) com `rank-bm25`.
  - `EnsembleRetriever` (pesos 0.4 BM25 / 0.6 FAISS) para balancear busca lexica e semantica.
- `_create_chain` construi `ConversationalRetrievalChain` com memoria `ConversationBufferMemory` (mensagens completas, reinicializada por usuario). Modelo `gemini-2.5-flash` temperatura 0.3.
- `get_rag_chain(user_id)` mantém cache `_USER_CHAINS` por usuario (memoria + retriever reutilizados).
- `answer_question` executa `chain.invoke` retornando dicionario com `answer`, `source_documents`, `chat_history`.
- `reset_user_memory` remove chave do cache interno, forçando nova cadeia e memoria limpa.

## Frontend React (`frontend/`)

- Construido com Vite + React 18, CSS custom (`App.css`) responsivo.
- Estrutura principal:
  - `App.jsx` controla `userId`, injeta hook `useChat` e compoe `Sidebar` + `ChatWindow`.
  - `hooks/useChat.js` implementa cliente REST (fetch), gestao de estado, controle de session anchor (sempre inicia conversa nova ao abrir/alterar `userId`).
  - `Sidebar.jsx` mostra logos, selecao de usuario, botoes de reset/refresh, historico ordenado por data, badges de stack.
  - `ChatWindow.jsx` renderiza cabecalho, lista de mensagens, composer (Shift+Enter = nova linha, Enter = envia) e tratamento de erros.
  - `MessageBubble.jsx` renderiza mensagens usuario/assistente, com avatar emoji e timestamp local, sem exibicao de fontes.
- Layout responsivo: sidebar fixa no desktop, colapsavel a partir de 820px, composer fixo na base, temas com gradientes e glassmorphism.
- Assets em `frontend/public/` (`mosaic_20251124_232058.png`, `605e2afebb3af870a9d35b2f_smartbreederWhiteLogo.png`).
- Variaveis ambiente frontend: `VITE_API_URL` (ex.: `https://backend.onrender.com/api`).

## Fluxo do Usuario

1. Usuario informa `ID` na sidebar (ex.: `ariane`).
2. `useChat` carrega historico via `GET /api/history/{id}`.
3. Ao enviar texto:
   - Hook cria registro otimista (estado local) para feedback instantaneo.
   - Faz `POST /api/chat` com pergunta.
   - Substitui registro temporario pelo payload persistido retornado pelo servidor.
4. Resposta aparece no chat, historico fica disponivel na sidebar.
5. `Novo chat` reseta memoria (backend + frontend) e oculta mensagens antigas (ancora de sessao).
6. `Atualizar historico` refaz GET e reaproveita registros anteriores.

## Dados e Fontes de Conhecimento

- Markdown tecnicos em `docs/` (ex.: `DOC_SP_DES_INT_ESTIMATIVA_PIMS.md`, `SP_AT_INT_APLICINSUMOAGRIC_Documentacao_Tecnica.md`).
- Possibilidade de converter novos PDFs via `converter_pdf_markdown.py` (PyMuPDF4LLM, fallback PyMuPDF/pdfplumber).
- Pasta `faiss_index/` reservada para caches persistidos (na implementacao atual o indice e reconstruido em memoria por processo).
- Historico de chat armazenado em `chat_history` (PostgreSQL recomendado; para testes pode usar SQLite alterando `DATABASE_URL`).

## Deploy e Operacao

- **Backend**
  - Dockerfile (python:3.11-slim) instala deps via `requirements.txt`, expõe porta 8080 e sobe `uvicorn app:app`.
  - `Procfile` (Render/Heroku) configura `web: uvicorn app:app --host=0.0.0.0 --port=${PORT:-8000}`.
  - Variaveis obrigatorias: `DATABASE_URL`, `GOOGLE_API_KEY`; opcionais `ALLOWED_ORIGINS`.
  - Endpoints health check: `GET /api/health` (Render Use-Case).
- **Frontend**
  - Build `npm install && npm run build`; artefatos em `frontend/dist` prontos para deploy static.
  - Configure `VITE_API_URL` no ambiente de build (Render static site -> Environment). Sem valor, assume `/api` (requer same origin).
- **Passo a passo Render (free tier)**
  1. Criar repo GitHub e conectar render.com (service backend: Docker ou buildpacks). Limite 512MB -> garantir `requirements` sem extras pesados.
  2. Definir environment variables.
  3. Frontend como Static Site apontando para `frontend/`, build command `npm install && npm run build`, publish dir `frontend/dist`.
  4. Configurar rewrite rule para SPA: `/*` -> `/index.html` (status 200).
  5. Atualizar frontend `.env` local com URL publica do backend para testar.
- **Operacao diaria**
  - Monitorar quotas do Google Generative AI (erro 429 -> aguardar reset ou upgrade).
  - Banco: aplicar migrations se necessario (atualmente criado on-the-fly).
  - Logs via provider (Render) ou configurar `uvicorn` log level.

## Boas Practicas e Observacoes

- Limpeza de memoria: `reset_user_memory` garante que cada novo chat comece sem contexto (alinhado ao pedido do time).
- Fontes: ainda presentes na resposta do backend para auditoria, mesmo sem exibicao no UI.
- Codigo legado: `config.py`, `batch_processor.py`, `test_app.py`, `db_utils.py` sao vestigios da versao Streamlit. Revisar antes de uso em producao.
- `requirements.txt` mantem `streamlit` por compatibilidade; remover se nao for mais necessario para reduzir build size.
- Adicionar testes automatizados (ausentes) e mecanismos de observabilidade (tracing, metrics) em roadmap.

## Roadmap Proposto

1. **Observabilidade**: adicionar logs estruturados (request/response), monitoramento de latencia e consumo GPT.
2. **Seguranca**: autenticar usuario (Auth0, Azure AD) e sanitizar input para logs.
3. **Gestao de conteudo**: pipeline automatizado para atualizar `docs/` a partir de PDF originais.
4. **Experiencia usuario**: destacar snippets relevantes, permitir exportar conversas.
5. **Escalabilidade**: persistir indice FAISS em disco e carregar incrementalmente para reduzir cold start.
6. **Modulos legados**: limpar ou migrar para reduzir confusao no repo.

## Referencias de Codigo

- Backend principal: `app.py`, `main.py`.
- Frontend: `frontend/src/App.jsx`, `frontend/src/components/*.jsx`, `frontend/src/hooks/useChat.js`, `frontend/src/App.css`.
- Infra: `Dockerfile`, `Procfile`, `requirements.txt`, `runtime.txt` (especifica Python para plataformas que usam buildpacks).

## Checklist para Apresentacao em Slides

- Slide 1: Problema e objetivo (Visao Geral + Objetivos de Valor).
- Slide 2: Arquitetura (diagrama ASCII, componentes principais).
- Slide 3: Pipeline RAG (carregamento docs, retrievers, LLM).
- Slide 4: Experiencia do usuario (fluxo e telas principais).
- Slide 5: Deploy e operacao (Render, variaveis ambiente, monitoramento).
- Slide 6: Roadmap e proximos passos (prioridades listadas acima).
- Slide 7: Referencias e agradecimentos.
