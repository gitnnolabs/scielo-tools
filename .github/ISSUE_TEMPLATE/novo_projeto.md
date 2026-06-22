---
name: Novo Projeto
about: Contribua com novas idéias e necessidades
title: ''
labels: enhancement
assignees: ''
---

# Novo Projeto / Nova Aplicação

## Informações Gerais

### Nome do Projeto
<!-- Nome da aplicação ou iniciativa -->

### Responsável
<!-- Responsável técnico -->

### Objetivo
<!-- Descreva resumidamente o objetivo do projeto -->

### Justificativa
<!-- Problema que será resolvido ou benefício esperado -->

---

# Classificação da Solução

### Criticidade do Sistema

- [ ] Baixa
- [ ] Média
- [ ] Alta

### Tipo de Informação Tratada

- [ ] Dados públicos
- [ ] Dados internos
- [ ] Dados pessoais (LGPD)
- [ ] Dados pessoais sensíveis (LGPD)
- [ ] Não aplicável

### Integrações Externas

- [ ] Sim
- [ ] Não

Se sim, descreva:

---

# Requisitos de Segurança

## Autenticação

- [ ] Não aplicável
- [ ] LDAP/Active Directory
- [ ] OAuth2/OpenID Connect
- [ ] Keycloak
- [ ] Outro

Descrição:

---

## Controle de Acesso

- [ ] Perfis de usuário
- [ ] RBAC
- [ ] Controle administrativo
- [ ] Não aplicável

Descrição:

---

## Comunicação Segura

- [ ] HTTPS obrigatório
- [ ] TLS entre componentes internos
- [ ] Não aplicável

Descrição:

---

## Gestão de Segredos

- [ ] GitHub Secrets
- [ ] Kubernetes Secrets
- [ ] Vault
- [ ] Outro

Descrição:

---

## Proteção de Dados

- [ ] Dados criptografados em trânsito
- [ ] Dados criptografados em repouso
- [ ] Não aplicável

Descrição:

---

## Registro e Auditoria

A aplicação deverá registrar:

- [ ] Autenticações
- [ ] Falhas de autenticação
- [ ] Alterações administrativas
- [ ] Erros da aplicação
- [ ] Não aplicável

Descrição:

---

## Backup e Recuperação

- [ ] Necessita backup
- [ ] Não necessita backup

Descrição:

---

# Avaliação de Segurança

## O sistema processa dados pessoais?

- [ ] Sim
- [ ] Não

Se sim, descreva quais dados:

---

## O sistema processa dados pessoais sensíveis?

- [ ] Sim
- [ ] Não

Se sim, descreva:

---

## Existe exposição para Internet?

- [ ] Sim
- [ ] Não

---

## Existe integração com terceiros?

- [ ] Sim
- [ ] Não

Se sim, descreva:

---

## Existe armazenamento de credenciais ou segredos?

- [ ] Sim
- [ ] Não

Se sim, descreva:

---

# Arquitetura da Solução

## Componentes Principais

- [ ] Frontend
- [ ] Backend
- [ ] API
- [ ] Banco de Dados
- [ ] Worker/Job
- [ ] Outro

Descrição:

---

## Banco de Dados

- [ ] PostgreSQL
- [ ] MySQL/MariaDB
- [ ] MongoDB
- [ ] Elasticsearch/OpenSearch
- [ ] Outro

Descrição:

---

## Infraestrutura

- [ ] Kubernetes
- [ ] Docker
- [ ] Máquina Virtual
- [ ] Serviço Externo
- [ ] Outro

Descrição:

---

## Diagrama da Arquitetura

Anexar ou informar link para:

- Draw.io
- Mermaid
- Wiki
- Documento técnico

Link:

---

# Requisitos de Desenvolvimento Seguro

## O projeto seguirá o fluxo padrão?

- [ ] Pull Request obrigatório
- [ ] Revisão por pares
- [ ] SonarQube
- [ ] Trivy
- [ ] OWASP ZAP (quando aplicável)
- [ ] Assinatura de imagens com Cosign
- [ ] Deploy via ArgoCD (quando aplicável)

---
# Avaliação LGPD

## O sistema processa dados pessoais?

- [ ] Sim

- [ ] Não

Se sim, descreva:

---

## O sistema processa dados pessoais sensíveis?

- [ ] Sim

- [ ] Não

Se sim, descreva:

---

## Existe compartilhamento de dados com terceiros?

- [ ] Sim

- [ ] Não

Se sim, descreva:

---

## Conclusão LGPD

- [ ] LGPD não aplicável

- [ ] LGPD aplicável

- [ ] Requer avaliação adicional do Gestor de SI

---

# Aprovação

## Gestor Técnico

Nome:

Data:

---

## Gestor de Segurança da Informação

Nome:

Data:

Comentários:
