# Remoção de modelos de referência não utilizados em core

**Data:** 2026-06-23

---

## Mensagem de commit

```
Remove modelos de referência não utilizados do app core

Elimina Gender, Language, License, LicenseStatement, FlexibleDate,
mixins associados, choices.py e forms.py órfãos; consolida migrações
de core em 0001_initial vazio.
```

---

## O que esse PR faz?

Remove código morto herdado do scaffold SciELO CMS que não era importado nem registado em nenhum módulo do repositório.

**Removido:**

- Modelos concretos: `Gender`, `Language`, `License`, `LicenseStatement`, `FlexibleDate`
- Abstratos e mixins: `CommonControlField`, `TextWithLang`, `TextLanguageMixin`, `RichTextWithLanguage`, `FileWithLang`, `LanguageFallbackManager`
- `core/choices.py` e `core/forms.py` (`CoreAdminModelForm` nunca usado)
- `core/models.py` fica vazio (modelos do app passam a existir só em subapps como `core/home`)

**Migrações:** histórico de `core` consolidado em `core/migrations/0001_initial.py` vazio (sem modelos no app `core`; `HomePage` permanece em `core/home/migrations/`).

## Onde a revisão poderia começar?

- `core/migrations/0004_remove_unused_reference_models.py`
- Diff de remoção em `core/models.py`, `core/choices.py`, `core/forms.py`

## Como este poderia ser testado manualmente?

1. `docker compose -f local.yml run --rm django python manage.py migrate`
2. `docker compose -f local.yml run --rm django python manage.py showmigrations core` — deve listar só `[X] 0001_initial`
3. `make test` — 3 testes smoke devem passar

Se a BD local já tiver registos de `0002`–`0004` em `django_migrations`, apague-os ou recrie o volume Postgres antes do passo 1.

## Algum cenário de contexto que queira dar?

Quando o app `reference` for implementado (ORCID, ROR, licenças, idiomas, etc.), os modelos devem ser criados lá com requisitos próprios do RCT, em vez de reativar este código copiado do CMS.

Strings órfãs em `locale/*/django.po` que apontavam para `core/choices.py` e `core/models.py` podem ser limpas com `make django_makemessages` num passo seguinte.

## Screenshots

N/A

## Quais são tickets relevantes?

N/A

## Referências

N/A
