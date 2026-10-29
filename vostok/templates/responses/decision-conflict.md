---
name: decision-conflict
description: Uma ação necessária conflita com uma decisão ativa da memória. Use antes de executar a ação e pare até o usuário escolher.
usage: |
  DECISION_SUMMARY: o campo Decisão da entrada, resumido em até 2 frases.
  CONFLICT: o ponto exato em que a ação e a decisão se contradizem.
  ADJUSTED_ACTION: como a ação ficaria para respeitar a decisão.
---

**Conflito com a decisão #{DECISION_ID}: #{DECISION_TITLE}**

## Ação pretendida

#{INTENDED_ACTION}

## Decisão registrada

#{DECISION_SUMMARY}

## Conflito

#{CONFLICT}

## Como seguir

| Opção | Descrição |
|---|---|
| A | Manter a decisão e ajustar a ação: #{ADJUSTED_ACTION} |
| B | Substituir a decisão #{DECISION_ID} por uma nova, que será proposta para registro. |
| C | Seguir com a ação como exceção, sem alterar a decisão. |

Responda com a letra ou descreva como prosseguir.
