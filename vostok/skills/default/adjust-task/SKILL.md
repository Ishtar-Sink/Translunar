---
name: adjust-task
description: "Ajusta uma tarefa de uma especificação (spec) planejada, em work/tasks/, em qualquer status menos done. Aplica um ou vários ajustes pedidos numa mesma mensagem (arquivos a ler ou mudar, passos, baseline, verificação, evidências, critérios de conclusão ou descrição), registra edições feitas à mão e mantém o histórico de ajustes da tarefa. Uma tarefa aprovada volta para aprovação; uma em execução volta para in_progress, sem nova aprovação. Use quando o usuário pedir para ajustar, corrigir, mudar ou detalhar algo de uma tarefa, ou comentar uma tarefa antes de executá-la."
allowed-tools: Read Edit Glob Bash(vostok *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok memory search, vostok task load, vostok task adjust record-manual, vostok task adjust validate, vostok task adjust record"
  templates: "templates/responses/question.md templates/responses/blocker.md templates/responses/completion.md"
---

# Ajustar tarefa

Aplica à tarefa certa todos os ajustes que o usuário pediu, deixando a tarefa válida e cada ajuste registrado no histórico.

## Termos

- **Tarefa:** o arquivo `vostok/work/tasks/<SPEC_ID>/<TASK_ID>.md`. Tarefas com status `pending`, `approved`, `in_progress`, `validating` ou `blocked` são ajustadas; `done`, não.
- **Pedido:** a mensagem do usuário com um ou mais ajustes.
- **Ajuste:** uma mudança pedida, com um único alvo e uma única ação. Um pedido pode ter vários ajustes.
- **Alvo:** o ponto da tarefa que o ajuste muda: uma subseção ("Passos", "Baseline"), um item ou um critério.
- **Edição manual:** mudança feita à mão na tarefa, fora desta skill. O comando a detecta pelo hash do conteúdo.
- **Histórico:** a seção "Histórico de ajustes" da tarefa, escrita só pelo comando.
- **Inferência:** decisão tomada pelo agente sem perguntar ao usuário.

## Regras

[adjust-task-01]: Não ajuste tarefas `done`. Nunca edite a spec, o plano nem outras tarefas.
[adjust-task-02]: Nunca edite uma tarefa sem ter certeza de que é a correta. Na dúvida, pergunte (passo 2).
[adjust-task-03]: Nunca edite o front-matter nem o "Histórico de ajustes". Só os comandos os alteram.
[adjust-task-04]: Um ajuste não muda `covers`, `depends_on`, `effort` nem `type`, nem os campos do card que os repetem ("Tipo", "Estimativa", "Rótulos", "Bloqueada por"). Pedido que exige mudá-los vai para um novo plano: responda com o template `blocker`.
[adjust-task-05]: Todo ajuste do pedido é aplicado ou vira pergunta. Nenhum é descartado sem aviso.
[adjust-task-06]: No máximo 1 rodada de perguntas, sempre antes de qualquer edição.
[adjust-task-07]: Não amplie o pedido. O que não foi pedido e for necessário para a tarefa continuar coerente (um passo que cita o arquivo removido de "Mudar") é inferência e aparece na resposta.
[adjust-task-08]: Todos os ajustes de um pedido são registrados juntos, com um único `vostok task adjust record`.
[adjust-task-09]: Não aprove nem execute a tarefa como parte do ajuste. A aprovação é feita pela skill `approve-task`, só a pedido do usuário.
[adjust-task-10]: Numa tarefa em execução (`in_progress`, `validating` ou `blocked`) com baseline coletado, não mude a subseção "Baseline": o baseline gravado deixaria de corresponder a ela. Pedido que a muda: responda com o template `blocker`.
[adjust-task-11]: O ajuste de uma tarefa em execução não pede nova aprovação: o comando a deixa `in_progress`, com tentativas e resultados zerados, mantém o baseline e o código e acrescenta a linha `ajuste` ao "Registro de execução".

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Identificar a tarefa
- [ ] 3. Registrar edições manuais
- [ ] 4. Decompor o pedido em ajustes
- [ ] 5. Analisar os ajustes
- [ ] 6. Rodada de perguntas (máx. 1)
- [ ] 7. Editar a tarefa
- [ ] 8. Validar
- [ ] 9. Registrar o ajuste
- [ ] 10. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill adjust-task
```

Os formatos de cada subseção da tarefa estão no passo 4 da skill [approve-plan](../approve-plan/SKILL.md).

### 2. Identificar a tarefa

As tarefas ficam em `vostok/work/tasks/<SPEC_ID>/`, e os IDs são numerados dentro de cada spec. Procure a tarefa citada com Glob (`vostok/work/tasks/*/TASK-03.md`).

Use a tarefa sem perguntar em qualquer um destes casos:

- O usuário cita a tarefa pelo ID, título ou arquivo, e ela existe numa única spec.
- O pedido vem logo depois de a tarefa ser criada, carregada ou ajustada nesta conversa.

Nos demais casos, **PARE** e pergunte qual ajustar, com o template `question`, uma opção por tarefa candidata (spec, ID e título). Não edite nada antes da resposta.

Tarefa citada que não existe: **PARE** e informe as tarefas da spec. Tarefa `done`: o comando recusa no passo 3; **PARE** e informe o status.

### 3. Registrar edições manuais

Execute:

```bash
vostok task adjust record-manual <SPEC_ID> <TASK_ID>
vostok task adjust validate <SPEC_ID> <TASK_ID>
```

Os problemas apontados pela validação são corrigidos no passo 7, junto com os ajustes do pedido.

### 4. Decompor o pedido em ajustes

Leia a tarefa inteira e as partes da spec que ela cobre. Depois, separe o pedido em ajustes, qualquer que seja a forma:

| Forma do pedido | Como separar |
|---|---|
| Prosa | Cada verbo de mudança sobre um alvo diferente é um ajuste. "Tire o AGENTS.md de 'Mudar' e acrescente um passo de teste" são dois. |
| Lista enumerada ou com marcadores | Cada item é um ajuste. Um item com dois alvos vira dois. |
| Citação exata (subseção, item, trecho entre aspas) | O alvo é o citado. Mude só ele. |
| Texto a substituir ("onde está A, coloque B") | O alvo é o trecho A. |
| Mistura das formas acima | Aplique cada regra à sua parte. |

O mesmo pedido repetido em formas diferentes é um único ajuste.

### 5. Analisar os ajustes

Classifique cada ajuste:

| Situação | Ação |
|---|---|
| Claro, com alvo existente | Aplicar |
| Ambíguo: mais de uma interpretação válida | Pergunta |
| Contradiz outro ajuste do mesmo pedido | Pergunta |
| Cita um alvo que não existe | Pergunta |
| Contradiz uma decisão ativa da memória (`vostok memory search decision <termos>`) | Pergunta, citando o ID da decisão |
| Muda `covers`, `depends_on`, `effort` ou `type` | **PARE**: responda com o template `blocker`; a mudança exige um novo plano. |
| Exige mudar a spec | **PARE**: responda com o template `blocker`; a spec planejada só muda num novo ciclo. |

Sem perguntas, vá para o passo 7.

### 6. Rodada de perguntas

Envie numa única mensagem, com o template `question`, uma pergunta para cada ajuste classificado como pergunta, citando o ajuste e o trecho da tarefa. **PARE** e aguarde a resposta.

Não edite nada antes da resposta, nem os ajustes claros. Depois dela, aplique todos juntos. O que continuar sem resposta não é aplicado e aparece em "Pendências" da resposta.

### 7. Editar a tarefa

Aplique os ajustes nas seções "Execução" e "Descrição", nos formatos da `approve-plan`. Mantenha "Execução" e "Descrição" coerentes: um critério de conclusão novo também entra nos "Critérios de aceite" do card.

### 8. Validar

Execute:

```bash
vostok task adjust validate <SPEC_ID> <TASK_ID>
```

O comando lista os problemas sem alterar nada. Corrija-os e execute de novo. Se falhar pela segunda vez, **PARE** e responda com o template `blocker`.

### 9. Registrar o ajuste

Execute, com um item por ajuste no resumo, separados por `; `:

```bash
vostok task adjust record <SPEC_ID> <TASK_ID> "Passo de teste acrescentado; AGENTS.md removido de Mudar"
```

O comando valida de novo, incrementa `adjustments`, atualiza as datas e o hash e acrescenta uma linha ao histórico. Numa tarefa aprovada, ele a devolve para `pending` e avisa. Numa tarefa em execução, ele a deixa `in_progress`, zera tentativas e resultados e avisa; o trabalho segue pela skill `execute-task`, sem nova aprovação. Se recusar o ajuste, volte ao passo 8.

### 10. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** o caminho da tarefa, o número do ajuste e a [tabela de ajustes](#tabela-de-ajustes).
- Se houve ajuste manual no passo 3, informe o número dele.
- Acrescente a lista de inferências, se houver, com a letra e o que foi inferido.
- **Pendências:** os ajustes que ficaram sem resposta. Se a tarefa voltou para `pending`, informe que precisa ser aprovada de novo; se estava em execução, informe que voltou para `in_progress`, sem nova aprovação.
- **Próximos passos:** novos ajustes ou a aprovação da tarefa (skill `approve-task`).

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

### Tabela de ajustes

Uma linha por ajuste identificado no pedido, na ordem em que aparecem.

```markdown
| # | Ajuste pedido | O que foi feito |
|---|---|---|
| 1 | Resumo do pedido, com o alvo. | Subseções e itens alterados. |
```
