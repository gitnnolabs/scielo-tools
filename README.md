# MarkAPI

Plataforma web para produção, validação e rastreio de artigos acadêmicos em formato **SPS XML**. Transforma DOCX em XML SPS com apoio de IA, gera HTML e PDF, valida pacotes SPS e expõe API REST para integração.

Stack: Python 3.12, Django 6.0, Wagtail 7.4, DRF, Celery, Redis, PostgreSQL, packtools.

---

## Melhorias futuras

### Arquitetura e organização
- **Dividir `manuscripts` em apps menores.** O app concentra pipeline, estrutura, modelos, views e admin. Separar em `ingestion` (upload, inspeção), `pipeline` (ações de processamento) e `articles` (modelos Article + StructureVersion + Artifact) reduziria o acoplamento e o tamanho dos módulos.
- **Extrair `utils/xml_utils.py` para o app `sps`.** As funções `parse_xml_structure`, `extract_article_metadata` e `generate_structure_xml` são operações de parsing/emissão XML SPS e naturalmente pertencem a `sps/`, não a `manuscripts/utils/`.
- **Revisar `ai/prompts/`.** Consolidar `vision.py` e `text.py` em um único módulo com prompts parametrizáveis por modalidade, evitando duplicação de lógica entre as duas trilhas.

### Funcionalidades
- **Pipeline assíncrono por ação.** Hoje `process_input` executa todas as ações sequencialmente. Cada ação poderia ser uma Celery task encadeada, permitindo retry individual e visibilidade granular.
- **Cache de resultados LLM.** O frontmatter extraído por LLM poderia ser cacheado por checksum do conteúdo, evitando re-chamadas ao reprocessar o mesmo documento.
- **Validação estrutural precoce.** Validar estrutura do DOCX (estilos, seções obrigatórias) antes de iniciar o pipeline, reduzindo falhas tardias.

### Dívida técnica
- **Mover `labeling/` para `utils/`.** O módulo `labeling` só contém funções utilitárias de segmentação e rotulagem — não é um app Django propriamente dito.
- **Remover referências a nomes antigos.** Código e configurações ainda referenciam `scielo_tools` e `markup_doc` — padronizar para `markapi`.
- **Testes de integração para o pipeline completo.** Hoje os testes cobrem unidades isoladas. Adicionar testes end-to-end com fixtures de DOCX → XML → validação → HTML → PDF.

### Infraestrutura
- **Suporte a GPU no container LLM.** O Dockerfile `Dockerfile.llama` hoje depende de CPU. Adicionar variante com CUDA para ambientes com GPU.
- **Métricas e observabilidade.** Expor métricas de uso do pipeline (taxa de sucesso por ação, latência, consumo de tokens LLM) via Prometheus/Grafana.

---

## Apps

| App | Descrição |
|-----|-----------|
| `manuscripts` | Pipeline de processamento — upload, ingestão, inspeção, estrutura, artefatos |
| `sps` | Geração e validação de XML SPS, HTML e PDF via packtools + LibreOffice |
| `ai` | Modelos LLM (Gemini, Ollama, HuggingFace), serviço unificado, prompts |
| `labeling` | Rotulagem de conteúdo DOCX, segmentação de seções, citações |
| `references` | Referências bibliográficas, deduplicação, parsing via IA, API REST |
| `journals` | Periódicos e issues — sincronização com Core API |
| `docx_parser` | Biblioteca de extração de conteúdo e estrutura de arquivos DOCX |
| `core` | Modelos base (`CommonControlField`), choices (línguas), forms, requester |
| `core_settings` | Configurações editáveis do site (nome, logo, favicon) via Wagtail |
| `users` | `CustomUser` (AUTH_USER_MODEL) |

### Estrutura do app `manuscripts`

```
manuscripts/
├── controller.py          lógica de negócio (artigos + eventos)
├── artifacts.py           salvamento e gerenciamento de artefatos + assets
├── blocks.py              StreamField blocks do Wagtail
├── choices.py             enums (ProcessStatus, InputType, ArtifactType, …)
├── forms.py               formulários de upload e revisão
├── processing.py          orquestrador do pipeline (process_input)
├── structure.py           persistência de estrutura e referências no DB
├── tasks.py               tarefas Celery
├── wagtail_hooks.py       viewsets, registro de snippets, hooks do admin
├── models/
│   ├── article.py         Article, StructureVersion, Reference, Citation, Artifact
│   └── processing.py      Processing, ProcessingEvent, proxies
├── utils/
│   ├── docx_utils.py      extração de estrutura de DOCX
│   ├── frontmatter.py     enriquecimento de frontmatter via payload LLM
│   ├── helpers.py         checksum, json_safe, blocks, safe_archive_members
│   ├── ingestion.py       ingestão de documentos, XMLs e ZIPs
│   ├── inspection.py      inspeção de entrada e resolução de ações
│   ├── processing_actions.py  handlers por ação (citation, xml, html, pdf, …)
│   └── xml_utils.py       parsing e geração de XML SPS
└── views/
    ├── editorial.py       views de edição e revisão
    └── wagtail.py         views de criação e inspeção do Wagtail
```

---

## Pipeline de processamento

```
1. Upload
   O usuário envia DOCX, XML ou ZIP via Wagtail admin.

2. Inspeção (inspect_processing)
   Detecta o tipo de entrada, sugere ações aplicáveis.

3. Ingestão (process_input → _ingest_input)
   Extrai o documento ou XML do ZIP, associa a um Article,
   extrai assets embutidos (imagens do DOCX).

4. Marcação de citações (CITATION_MARKUP)
   Identifica e marca referências no DOCX via sps.xref.
   Extrai estrutura (front/body/back).
   Envia frontmatter ao LLM para extração de metadados.
   Cria ArticleStructureVersion com blocos estruturados.

5. Geração XML (XML_GENERATION)
   Converte a estrutura em XML SPS via sps.xml.
   Preserva nós não-modelados via round-trip com XML base.

6. Validação XML (XML_VALIDATION)
   Valida o XML contra SPS via packtools.

7. Geração de pacote SPS (SPS_PACKAGE_GENERATION)
   Empacota XML + assets referenciados em ZIP.

8. Geração HTML (HTML_GENERATION)
   Renderiza HTML a partir do XML SPS.

9. Geração PDF (PDF_GENERATION)
   Converte XML → DOCX (packtools) → PDF (LibreOffice).
```

Cada ação é registrada como `ProcessingEvent` (status, mensagem, detalhes)
e produz `ArticleArtifact` versionado (is_current / is_stale).

---

## Desenvolvimento

**Pré-requisitos:** Docker, Docker Compose, Make.

### Primeira execução

```bash
make build
make up
make django_migrate
make django_createsuperuser
```

### Serviços locais

| Serviço | URL |
|---------|-----|
| Wagtail/Django | http://127.0.0.1:8009 |
| MailHog | http://127.0.0.1:8029 |
| PostgreSQL | localhost:5439 |
| Redis | localhost:6399 |
| Flower | http://127.0.0.1:5559 |

```bash
make help   # todos os alvos Make
```

### Compose

Arquivo principal: `local.yml` (dev). Ambiente em `.envs/.local/`.

Volume Postgres em `../scms_data/scielo_tools/data_dev`.

```bash
make build COMPOSE_FILE=local.yml
make up
make logs
```

### Variante LLM local (llama.cpp)

```bash
make build_llama
```

Define `DOCKERFILE=./compose/local/django/Dockerfile.llama` antes do build.
O compose e demais comandos continuam usando `local.yml`.

### Modelo LLM

[Wiki — baixar e configurar modelo](https://github.com/scieloorg/scielo-tools/wiki)

---

## Testes

```bash
make test              # pytest (padrão, reutiliza DB de teste)
make test-fast         # pytest com -x
make test-cov          # pytest com coverage (manuscripts, 100%)
make test-fresh        # recria o banco de teste e roda pytest

# aliases (compatibilidade)
make pytest
make pytest_fast
make pytest_cov

# legado (Django runner)
make django_test       # manage.py test --settings=config.settings.test
make django_fast       # com --failfast
```

---

## Configuração

### Settings modules

| `DJANGO_SETTINGS_MODULE` | Uso |
|--------------------------|-----|
| `config.settings.local` | Desenvolvimento (default) |
| `config.settings.production` | Produção |
| `config.settings.test` | Testes |

### Arquivos de ambiente

- `.envs/.local/.django` — `USE_DOCKER`, `REDIS_URL`, `HF_TOKEN`, Flower
- `.envs/.local/.postgres` — `POSTGRES_*`
- `.envs/.production/.django` — `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `SENTRY_DSN`, …

No container, o entrypoint define `DATABASE_URL` e `CELERY_BROKER_URL` a partir de `POSTGRES_*` e `REDIS_URL`.

### Variáveis principais

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL (montada no entrypoint) |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` | Credenciais e base |
| `REDIS_URL` | Redis (ex.: `redis://redis:6379/0`) |
| `CELERY_BROKER_URL` | Broker Celery (= `REDIS_URL` no entrypoint) |
| `DJANGO_SECRET_KEY` | Chave secreta (produção) |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Origens CSRF |
| `LLAMA_ENABLED` | Ativar LLM local (`false` em testes) |
| `HF_TOKEN` | Token Hugging Face (download do modelo) |
| `CORE_API_DOMAIN` | API SciELO Core (default `https://core.scielo.org`) |
| `DRF_PAGE_SIZE` | Paginação da API REST |
| `SENTRY_DSN` | Monitorização (produção) |
| `COMPRESS_ENABLED` | Compressor de estáticos (produção) |

---

## Requisitos Python

| Arquivo | Uso |
|---------|-----|
| `requirements/base.txt` | Runtime |
| `requirements/local.txt` | Dev + pytest |
| `requirements/production.txt` | Produção |

Após alterar dependências: `make build`.

---

## Comandos úteis

```bash
make django_shell           # shell Django
make django_bash            # bash no container
make logs                   # logs de todos os serviços
make restart                # reiniciar containers
make dump_data              # backup PostgreSQL
make clean_migrations       # limpar migrations (dev)
make clean_project_images   # remover imagens Docker do projeto
```

**Celery:** serviços `celeryworker` e `celerybeat` no `local.yml`.

**Tarefas agendadas:** menu _Settings → Tarefas agendadas_ no Wagtail admin.
