---
name: question
description: Perguntas que exigem uma decisão do usuário entre opções. Use sempre que precisar parar e perguntar.
usage: |
  Todas as perguntas abertas vão numa única mensagem. Repita o bloco da pergunta para cada uma,
  numerando a partir de 1. Identifique as opções por letras, a partir de A.
  QUESTION_CONTEXT: o trecho ou a situação que gerou a dúvida e por que ela importa, em até 3 frases.
  As tabelas trazem só texto relevante para a decisão, sem links ou imagens.
  A linha de fechamento aparece uma única vez, no fim da mensagem.
---

# #{QUESTION_NUMBER}. #{QUESTION_TITLE}

#{QUESTION_CONTEXT}

| Opção | Descrição |
|---|---|
| A | #{OPTION_DESCRIPTION} |
| B | #{OPTION_DESCRIPTION} |

Responda com o número e a letra (ex.: 1A, 2B). Caso nenhuma se encaixe, descreva como deseja prosseguir.
