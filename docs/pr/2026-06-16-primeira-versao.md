# Insumo de PR — primeira versão (MarkAPI / SciELO Tools)

**Data:** 2026-06-16  
**Contexto:** entrega inicial da plataforma web para produção, validação e rastreio de artigos acadêmicos em **SPS XML**.

---

## Mensagem de commit

```
Entrega primeira versão da plataforma MarkAPI (SciELO Tools)

Implementa o fluxo editorial central: ingestão DOCX/XML/ZIP, marcação
assistida por IA, geração e validação SPS, artefatos HTML/PDF, rastreio
de eventos no pipeline e interface Wagtail com API REST para integração.
```

---

## O que esse PR faz?

Esta é a **primeira versão funcional** da plataforma descrita no SciELO Research Communication Tools (RCT): um backbone editorial agnóstico a sistemas externos, com o **XML SPS como registro único** de cada objeto e de cada etapa do ciclo.

**Objetivo atendido nesta entrega:** permitir que uma redação produza, valide e acompanhe artigos acadêmicos — da submissão (upload) à disseminação em múltiplos formatos — com marcação assistida por IA e revisão humana antes de finalizar.

### Capacidades entregues

| Área | O que a aplicação faz |
|------|------------------------|
| **Ingestão** | Upload de DOCX, XML ou ZIP via Wagtail; inspeção automática do tipo de entrada e sugestão de ações |
| **Marcação** | Identificação de citações e referências; extração de estrutura (front/body/back); enriquecimento de metadados via LLM |
| **XML SPS** | Geração de XML a partir da estrutura editável; validação com packtools; pacote `.zip` SPS com assets |
| **Derivados** | HTML e PDF a partir do XML; artefatos versionados (`is_current` / `is_stale`) |
| **Rastreio** | Cada ação do pipeline registrada como `ProcessingEvent` (status, agente, timestamp, detalhes) |
| **Referências** | App `references` com parsing, deduplicação e API REST; bases para normalização editorial |
| **Integração** | API REST (DRF/JWT) para sistemas externos; Wagtail embutido para quem não possui sistema editorial |
| **Infra** | Docker Compose (Django, Celery, Redis, PostgreSQL); LLM configurável (local ou remoto) |

### Apps principais

- **`manuscripts`** — pipeline editorial (upload → inspeção → processamento → estrutura → artefatos)
- **`sps`** — geração e validação SPS, HTML e PDF (packtools + LibreOffice)
- **`ai`** — serviço unificado de LLM (Gemini, Ollama, HuggingFace)
- **`references`**, **`journals`**, **`docx_parser`**, **`labeling`**, **`core`**, **`users`**

### Limitações conhecidas desta versão

- Foco inicial em **artigos/manuscritos** (DOCX/XML); os seis tipos de objeto do RCT (preprint, dado de pesquisa, livro, capítulo) ainda não estão cobertos de forma completa.
- Avaliação informada (checklists CONSORT, PRISMA, FAIR) e integrações SciELO (Upload/OPAC 5) estão no roadmap, não nesta entrega.
- Pipeline executa ações **sequencialmente**; retry granular por ação via Celery encadeado é melhoria futura.

---

## Onde a revisão poderia começar?

1. **`README.md`** — visão geral, pipeline em 9 etapas e mapa de apps.
2. **`manuscripts/processing.py`** — orquestrador do pipeline (`process_input`).
3. **`manuscripts/utils/processing_actions.py`** — handlers por ação (citação, XML, validação, HTML, PDF, pacote SPS).
4. **`manuscripts/controller.py`** — lógica de artigos, eventos e estrutura.
5. **`manuscripts/wagtail_hooks.py`** + **`manuscripts/views/`** — interface editorial no Wagtail.
6. **`sps/`** — camada de conformidade SPS (geração, validação, renderização).

---

## Como este poderia ser testado manualmente?

### 1. Subir o ambiente

```bash
make build
make up
make django_migrate
make django_createsuperuser   # se ainda não existir usuário admin
```

Serviços locais: Wagtail em http://127.0.0.1:8009 (ver `README.md` para demais portas).

### 2. Fluxo editorial completo (Wagtail)

1. Aceder ao admin Wagtail com o superusuário.
2. Criar ou abrir um **Processing** e fazer upload de um DOCX ou XML de exemplo.
3. Confirmar a **inspeção**: tipo detectado e ações sugeridas.
4. Iniciar o **processamento** e acompanhar o estado (`ProcessStatus`) e os eventos registados.
5. Rever a **estrutura** do artigo (front/body/back) e metadados extraídos.
6. Verificar **artefatos** gerados: XML SPS, relatório de validação, pacote ZIP, HTML e PDF.
7. Confirmar que cada etapa aparece em **ProcessingEvent** com status e mensagem coerentes.

### 3. API REST

1. Obter token JWT para um utilizador de teste.
2. Chamar endpoints documentados em `/api/v1/` (ex.: operações sobre artigos e referências).
3. Confirmar autenticação, paginação e respostas esperadas.

### 4. Referências

1. No fluxo de estrutura, validar ligação entre citações no corpo e blocos de referência.
2. Testar endpoints do app `references` (listagem, parsing, deduplicação) via API ou admin.

### 5. Validação automatizada (complementar)

```bash
make test        # suíte pytest do app manuscripts
make test-fast   # fail-fast, útil durante revisão de código
```

Estes comandos validam regressões no pipeline e nas views; **não substituem** o teste manual do fluxo editorial descrito acima.

---

## Algum cenário de contexto que queira dar?

A plataforma nasce para ser **integração aditiva**: periódicos e editoras mantêm OJS, ScholarOne ou fluxos próprios; o MarkAPI actua como backbone via API REST, registando tudo no XML SPS.

**Princípios desta versão:**

- A IA **auxilia** a marcação (referências bibliográficas em destaque); o humano **revisa e corrige** antes de finalizar.
- Conformidade SPS garantida por **packtools** (versão fixada no projeto).
- LLM preferencialmente **on-premise** (`Dockerfile.llama`); APIs externas são responsabilidade da instituição.
- Correções no XML propagam-se aos derivados (HTML, PDF, pacote SPS).

Esta entrega materializa o núcleo do RCT — conversão, marcação, validação, múltiplos formatos e rastreio — numa stack Django/Wagtail implantável com Docker Compose.

---

### Screenshots

Recomendado anexar no PR do GitHub, se possível:

- Tela de upload/inspeção de um Processing no Wagtail
- Lista de eventos do pipeline e artefatos gerados (XML, HTML, PDF)
- Exemplo de estrutura editável (front/body/back)

---

## Quais são tickets relevantes?

N/A

---

### Referências

- SciELO Research Communication Tools (RCT) v4.0 — `scielo_rct_v3_updated.docx`
- Repositório: [scieloorg/SciELO-Tools](https://github.com/scieloorg/scielo-tools)
- Wiki — [modelo LLM e configuração](https://github.com/scieloorg/scielo-tools/wiki)
- `README.md` — pipeline, apps, desenvolvimento e testes

---

## Correção de segurança (pré-push)

Removida `DJANGO_SECRET_KEY` real hardcoded em `config/settings/local.py`; o default local passou a ser `django-insecure-local-dev-only`. Produção continua a exigir `DJANGO_SECRET_KEY` via `.envs` (não versionado).
