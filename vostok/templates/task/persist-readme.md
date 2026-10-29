<!-- Guia das evidências de uma tarefa, gerado pelo `vostok task persist`. O trecho anterior a
     "entrada" é o topo; o seguinte se repete para cada evidência. Variáveis que o comando não
     consegue preencher ficam no guia para o agente completar, e o `vostok task finish` recusa a
     conclusão enquanto alguma restar. -->
# #{TASK_ID}: #{TASK_TITLE}

Evidências da tarefa #{TASK_ID} da #{SPEC_ID}, copiadas de `vostok/work/` e sanitizadas: caminhos pessoais viraram `~`.

- **Persistidas em:** #{DATE}
- **Testes:** #{TESTS_RESULT}
- **Regressão:** #{REGRESSION_RESULT}
- **Regressões aceitas:** #{ACCEPTED}

## Arquivos de apoio

Saídas brutas dos comandos de "Baseline", antes da mudança, e da validação (testes e regressão), depois dela.

#{SUPPORT_FILES}
<!-- entrada -->

## #{NAME}

- **Prova:** #{PROVA}
- **Como gerar:** #{COMMAND}
- **Arquivo:** #{FILE}
- **O que procurar:** #{TRECHO_ESPERADO}
- **Trecho que prova:** #{TRECHO}
- **Sinal de falha:** #{FALHA}
- **Artefato medido:** #{ARTEFATO}
- **Revisão:** #{REVISAO}
