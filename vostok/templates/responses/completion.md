---
name: completion
description: Conclusão de uma tarefa que alterou arquivos ou executou um fluxo, inclusive o fim de uma skill.
usage: |
  ANTES DE RESPONDER: execute `vostok commit check` ([agent/boundaries-04]). Se ele recusar, não use este
    template: responda com `blocker`, com os commits listados pelo comando.
  SUMMARY: o resultado em uma frase.
  CHANGES: lista `- caminho: o que mudou`, um item por arquivo ou grupo de arquivos.
  VERIFICATION: comandos executados e resultado, inclusive o do `vostok commit check`. Diga também o que não foi verificado.
  MEMORY_RECORDS: opcional. Entradas criadas ou alteradas na memória, `- ID: título`. Sem entradas, omita a seção.
  PENDING: opcional. O que ficou em aberto. Sem pendências, omita a seção.
  NEXT_STEPS: opcional. O que o usuário pode pedir em seguida, um por item: `- pedido em linguagem natural ou skill: quando usar`
    (ex.: `- "aprova o plano" (skill approve-plan): criar as tarefas`). O usuário conversa com o agente: não indique
    scripts nem comandos de terminal. Cite só o que é possível no estado atual. Sem próximos passos, omita a seção.
---

**#{SUMMARY}**

## O que foi feito

#{CHANGES}

## Verificação

#{VERIFICATION}

## Memória

#{MEMORY_RECORDS}

## Pendências

#{PENDING}

## Próximos passos

#{NEXT_STEPS}
