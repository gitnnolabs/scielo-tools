# Bootstrap inicial — SciELO Tools

**Data:** 2026-06-23  
**Repositório:** [scieloorg/SciELO-Tools](https://github.com/scieloorg/SciELO-Tools)  
**Âmbito:** PR inicial com a fundação da plataforma (scaffold, infraestrutura, modelos base e admin Wagtail).

---

## Mensagem de commit

```
Adiciona bootstrap inicial da plataforma SciELO Tools

Estabelece stack Django 6 + Wagtail 7.4, Docker Compose local e
produção, apps core/users/core_settings, modelos de referência,
integração Celery no admin e pipeline de CI.
```

---

## O que esse PR faz?

Este PR entrega a **fundação do repositório SciELO Tools** — plataforma web para ferramentas de apoio à produção e publicação científica da rede SciELO, alinhada ao RCT v4.0 (SciELO Research Communication Tools). Não inclui ainda os apps de domínio (`xml_manager`, `reference`, `model_ai`, `docx_layouts`, `tracker`) nem API REST; prepara o terreno para que novas ferramentas sejam adicionadas como Django apps neste monorepo.

### Stack e dependências

| Componente | Versão / nota |
|------------|---------------|
| Python | 3.14 (Docker) |
| Django | 6.0.5 |
| Wagtail | 7.4.2 |
| Celery | 5.3.6 + django-celery-beat + django-celery-results |
| PostgreSQL | via Docker (compose/production/postgres) |
| Redis | 8 |
| Outros | django-environ, whitenoise, django-compressor, wagtail-modeladmin, wagtail-autocomplete, flower |

### Infraestrutura e desenvolvimento local

- **`local.yml`** — Compose com serviços: `django`, `postgres`, `redis`, `celeryworker`, `celerybeat`, `flower`, `mailhog`.
- **`compose/local/django/`** — Dockerfile multi-stage, scripts de arranque (`/start`, celery worker/beat/flower).
- **`compose/production/`** — Dockerfiles e scripts para Django, PostgreSQL (backup/restore), Traefik.
- **`.envs.example/.local/`** — Modelos de variáveis para Django, Postgres e Celery/Flower.
- **`Makefile`** — Targets para build, up/down, migrate, shell, testes, makemessages, dump/restore de BD, limpeza de containers/volumes.
- **`.dockerignore`**, **`.git-hook-commit-msg`** — Suporte a hooks de commit opcionais (`make configure_git_hooks`).

### Configuração Django (`config/`)

- **`settings/base.py`** — Apps instalados (Django, Wagtail, Celery, compressor, autocomplete), i18n (pt-br, es, en), static/media, `AUTH_USER_MODEL`, Celery com result backend em BD.
- **`settings/local.py`** — DEBUG, Redis cache, debug toolbar, django-extensions, email via MailHog.
- **`settings/production.py`** e **`settings/test.py`** — Perfis separados para deploy e CI.
- **`urls.py`** — Admin Django, Wagtail admin, documentos, i18n e páginas públicas.
- **`celery_app.py`** — App Celery com autodiscover de tasks.
- **`menu.py`** — Ordem de grupos no menu Wagtail (ex.: `celery_wagtail`).

### App `users/`

- **`CustomUser`** — Modelo de utilizador customizado (`AUTH_USER_MODEL`) com campo `name`, integrado ao Django Admin via `CustomUserAdmin` e formulários de criação/edição.

### App `core/` — modelos e utilitários base

Modelos de **referência editorial** reutilizáveis por futuros apps:

| Modelo / mixin | Função |
|----------------|--------|
| `CommonControlField` | Campos abstratos: `created`, `updated`, `creator`, `updated_by` |
| `Gender` | Sexo (códigos M/F), com `load()` a partir de `choices.GENDER_CHOICES` |
| `Language` | Idiomas (nome + code2), com `load()` e `get_or_create()` |
| `License` / `LicenseStatement` | Tipos Creative Commons e declarações por URL/idioma |
| `FlexibleDate` | Data parcial (ano/mês/dia) |
| Mixins abstratos | `TextWithLang`, `TextLanguageMixin`, `RichTextWithLanguage`, `FileWithLang` |
| `LanguageFallbackManager` | Fallback pt → es → en em conteúdos multilíngues |

**Wagtail e admin:**

- **`core/home/`** — `HomePage` (página raiz Wagtail).
- **`core/wagtail_hooks.py`** — Reorganização do menu principal (“Content Manager”), link da wiki no menu de ajuda, título automático em imagens sem título.
- **`core/celery_wagtail.py`** — Gestão de tarefas Celery Beat no admin Wagtail (PeriodicTask, crontab, interval, etc.) com ações enable/disable/run e endpoint `celery_wagtail/`.
- **Templates** — `base.html`, `404.html`, `500.html`, welcome/home pages, template Celery no admin.
- **Static** — CSS/JS SciELO, logos e favicons da marca.

**Migrations:** `0001_initial`, `0002_initial` (FKs e relações), `0003_delete_coresyncstate` (remoção de `CoreSyncState`).

### App `core_settings/`

- **`CustomSettings`** — Configurações editáveis no Wagtail (nome, email, telefone, footer, favicon, logos do site e do admin).
- Templates Wagtail admin customizados (login, logo) e CSS do favicon/logo no painel.

### Internacionalização

- Traduções em **`locale/pt_BR`**, **`locale/es`**, **`locale/en`** (ficheiros `.po`/`.mo`).
- `LocaleMiddleware` e `LANGUAGES` configurados em `base.py`.

### CI/CD e governança do repositório

- **`.github/workflows/ci.yml`** — Build Docker, migrate, testes Django (`config.settings.test`) e pytest em PR/push para `main`/`master`.
- **`.github/dependabot.yml`** — Atualizações diárias de GitHub Actions, Docker e pip.
- **Templates de issue** — nova funcionalidade, novo projeto, reportar problema, tarefa de desenvolvimento.
- **`.github/PULL_REQUEST_TEMPLATE/`** — Template oficial de PR.
- **`LICENSE`**, **`README.md`** — Documentação de arranque e estrutura do projeto.

### O que ainda não está incluído (próximos PRs)

- Apps de domínio: `xml_manager`, `reference`, `model_ai`, `docx_layouts`, `tracker`.
- API REST com JWT (DRF).
- Pipeline DOCX/LaTeX → XML SPS e integração packtools.
- Testes automatizados de apps (apenas `config/settings/test.py` e job CI preparados).
- `production.yml` na raiz (existe apenas estrutura em `compose/production/`).

---

## Onde a revisão poderia começar?

1. **`config/settings/base.py`** — Visão geral de apps, Celery, Wagtail e i18n.
2. **`local.yml`** + **`compose/local/django/Dockerfile`** — Ambiente de desenvolvimento.
3. **`core/models.py`** — Modelos base e mixins multilíngues.
4. **`core/celery_wagtail.py`** + **`core/wagtail_hooks.py`** — Customizações do admin Wagtail.
5. **`core_settings/models.py`** — Configurações do site.
6. **`users/models.py`** — Utilizador customizado.
7. **`.github/workflows/ci.yml`** — Pipeline de integração contínua.

---

## Como este poderia ser testado manualmente?

1. **Pré-requisitos:** Docker, Docker Compose e Make instalados.

2. **Configurar ambiente:**
   ```bash
   cp -r .envs.example/.local .envs/.local
   make configure_git_hooks   # opcional
   make build
   make up
   ```

3. **Aplicar migrations e criar superutilizador:**
   ```bash
   make django_migrate
   make django_createsuperuser
   ```

4. **Verificar serviços:**
   - Aplicação: http://localhost:8000 (porta mapeada em `local.yml`)
   - Wagtail admin: http://localhost:8000/admin/
   - Flower (Celery): http://localhost:5559
   - MailHog: http://localhost:8029

5. **No admin Wagtail:**
   - Fazer login com o superutilizador.
   - Confirmar menu “Content Manager” (Pages, Images, Documents).
   - Em Settings → Site configuration, editar nome, logos e favicon.
   - Em Settings → Tarefas agendadas, listar periodic tasks do Celery Beat.
   - Verificar menu de ajuda com link para a wiki do projeto.

6. **Testes automatizados:**
   ```bash
   make test
   ```
   Ou, equivalente ao CI:
   ```bash
   docker compose -f local.yml run --rm django python manage.py test --settings=config.settings.test
   docker compose -f local.yml run --rm django pytest
   ```

7. **Parar ambiente:**
   ```bash
   make down
   ```

---

## Algum cenário de contexto que queira dar?

Este repositório é o **ponto de partida** da plataforma SciELO Tools descrita no RCT v4.0: ciclo editorial completo com XML SPS como registro único, marcação assistida por IA, validação packtools e integração com sistemas externos via API. O código atual provém de um scaffold Django/Wagtail/Celery já usado em projetos SciELO (p.ex. padrões de `CommonControlField`, licenças CC, multilíngue), adaptado para ser o monorepo onde cada ferramenta editorial será um app Django.

**Decisões relevantes para o revisor:**

- Monorepo com apps `core` (base), `users` e `core_settings` (site); novas ferramentas entram como apps adicionais.
- Celery Beat com scheduler em base de dados, gerível pelo admin Wagtail.
- i18n nativo (pt-br, es, en) desde o início.
- Volumes Postgres em `../scms_data/scielo_tools/` (fora do repo) — requer pasta no host ou ajuste local.
- README menciona porta `8009`; `local.yml` expõe `8000` — alinhar na documentação se necessário.
- Makefile ainda referencia app `manuscripts` em `test-cov` (resquício de template anterior).

---

## Screenshots

N/A — PR de infraestrutura e scaffold; capturas do admin Wagtail e da home podem ser anexadas no PR do GitHub após primeiro `make up`.

---

## Quais são tickets relevantes?

N/A — bootstrap inicial do repositório.

---

## Referências

- [Wagtail 7.4](https://docs.wagtail.org/)
- [Django 6.0](https://docs.djangoproject.com/en/6.0/)
- [django-celery-beat](https://django-celery-beat.readthedocs.io/)
- Wiki do projeto: https://github.com/scieloorg/scielo-tools/wiki
