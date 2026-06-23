# Testes smoke iniciais (pytest)

**Data:** 2026-06-23

---

## Mensagem de commit

```
Adiciona testes smoke para o pytest no bootstrap

O pytest retorna código de saída 5 quando nenhum teste é coletado;
inclui verificações mínimas de settings, utilizador e system check.
```

---

## O que esse PR faz?

Corrige `make test` (e o passo de pytest na CI), que falhava com **Error 5** porque o repositório ainda não tinha ficheiros de teste — o pytest trata “zero testes coletados” como erro.

Adiciona `tests/test_smoke.py` com três verificações mínimas: `AUTH_USER_MODEL`, criação de `CustomUser` e `django check`.

## Onde a revisão poderia começar?

- `tests/test_smoke.py`

## Como este poderia ser testado manualmente?

1. `make test` — deve terminar com 3 testes passados e exit code 0.
2. `make django_test` — também passa (o runner legado do Django aceita zero testes sem erro).

## Algum cenário de contexto que queira dar?

O código de saída **5** do pytest significa especificamente “nenhum teste encontrado”, não falha de infraestrutura Docker. Testes de páginas Wagtail com `ManifestStaticFilesStorage` exigiriam `collectstatic` ou override de `STORAGES` em `test.py`; ficam para quando houver testes de integração HTTP.

## Screenshots

N/A

## Quais são tickets relevantes?

N/A

## Referências

- [Pytest exit codes](https://docs.pytest.org/en/stable/reference/exit-codes.html) — código 5 = no tests collected
