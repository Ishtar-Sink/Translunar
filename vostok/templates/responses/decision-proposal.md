---
name: decision-proposal
description: Proposta de registrar uma decisão estruturante na memória. Use antes de gravar qualquer decisão e pare até o usuário confirmar.
usage: |
  Cada valor ocupa uma linha da tabela, com os mesmos campos da entrada de decisão.
  SUPERSEDES: o ID da decisão substituída, ou "Nenhuma".
---

**Proposta de decisão: #{DECISION_TITLE}**

| Campo | Valor |
|---|---|
| Contexto | #{DECISION_CONTEXT} |
| Decisão | #{DECISION} |
| Alternativas descartadas | #{DECISION_ALTERNATIVES} |
| Consequências | #{DECISION_CONSEQUENCES} |
| Tags | #{ENTRY_TAGS} |
| Substitui | #{SUPERSEDES} |

Responda `ok` para registrar ou diga o que ajustar.
