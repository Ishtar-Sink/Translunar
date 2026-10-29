---
name: approve-task
description: "Aprova tarefas de uma especificação (spec) planejada, em work/tasks/: uma, várias ou todas as pendentes. Confere se cada tarefa está pendente, sem edição manual sem registro e válida, e grava a aprovação em todas ou em nenhuma. Use quando o usuário pedir para aprovar tarefas, citar IDs como TASK-01 para aprovação ou disser que aprova as tarefas."
allowed-tools: Read Glob Bash(vostok *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok task load, vostok task approve validate, vostok task approve approve"
  templates: "templates/responses/question.md templates/responses/blocker.md templates/responses/completion.md"
---

# Aprovar tarefas

Aprova as tarefas que o usuário escolheu, de forma determinística: todas as pedidas ficam aprovadas, ou nenhuma.

## Termos

- **Tarefa:** o arquivo `vostok/work/tasks/<SPEC_ID>/<TASK_ID>.md`, criado pela skill `approve-plan`.
- **Pendente:** tarefa com status `pending`. É a única que pode ser aprovada.
- **Aprovada:** tarefa com status `approved`, com `approved_at` e `approved_hash` no front-matter. Só ela pode ser executada.
- **Citação:** tarefa nomeada no pedido pelo ID (`TASK-03`), pelo título ou por um intervalo ("da 1 à 3").
- **Impedimento:** o que impede a aprovação: status fora de `pending`, edição manual sem registro ou problema de validação.

## Regras

[approve-task-01]: Só aprove a pedido do usuário. Nunca aprove por iniciativa própria, nem como parte de outro fluxo.
[approve-task-02]: Aprove só as tarefas citadas. Sem citação, não aprove nenhuma: pergunte quais (passo 3).
[approve-task-03]: Use `--all` só quando o usuário pedir explicitamente todas as tarefas ("aprova todas", "aprova todas as tarefas da SPEC-002"). "Aprova as tarefas" não é pedido de todas.
[approve-task-04]: Nunca edite as tarefas nem o front-matter nesta skill. Quem grava a aprovação é o comando.
[approve-task-05]: Não resolva impedimentos por conta própria. Responda com o template `blocker`; mudanças na tarefa são feitas pela skill `adjust-task`.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Identificar a spec
- [ ] 3. Identificar as tarefas
- [ ] 4. Conferir os impedimentos
- [ ] 5. Aprovar
- [ ] 6. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill approve-task
```

### 2. Identificar a spec

As tarefas ficam em `vostok/work/tasks/<SPEC_ID>/`, uma pasta por spec, e os IDs são numerados dentro de cada spec. Procure as tarefas citadas com Glob (`vostok/work/tasks/*/TASK-03.md`):

- Spec citada no pedido, ou tarefas citadas que existem em uma única spec: use essa spec.
- Tarefa citada que existe em mais de uma spec: **PARE** e pergunte de qual, com o template `question`, uma opção por spec. Não aprove nada antes da resposta.
- Tarefa citada que não existe: **PARE** e informe as tarefas existentes.

Sem citação, considere as specs com tarefas `pending`. Se houver mais de uma, a pergunta do passo 3 traz as tarefas de todas, com a spec de cada uma.

### 3. Identificar as tarefas

Com citação, use as tarefas citadas. Com pedido explícito de todas, use `--all`.

Sem citação: leia o front-matter das tarefas da spec, liste as que estão com status `pending` e **PARE**. Pergunte quais aprovar, com o template `question`, usando a [lista de tarefas pendentes](#lista-de-tarefas-pendentes) e as opções "todas", "só algumas (diga quais)" e "nenhuma". Não aprove nada antes da resposta. Sem tarefas `pending`, informe que não há tarefas para aprovar e encerre.

### 4. Conferir os impedimentos

Execute, com os IDs ou `--all`:

```bash
vostok task approve validate <SPEC_ID> <TASK_ID ...>
```

O comando lista os impedimentos de cada tarefa, sem alterar nada. Se houver algum, **PARE** e responda com o template `blocker`, com a mensagem do comando:

| Impedimento | Como resolver |
|---|---|
| Status fora de `pending` | Uma tarefa aprovada que precisa mudar volta a `pending` com um ajuste (skill `adjust-task`). |
| Edição manual sem registro | Registrar a edição com `vostok task adjust record-manual` ou pedir um ajuste (skill `adjust-task`). |
| Problema de validação | Ajustar a tarefa com a skill `adjust-task`. |

### 5. Aprovar

Execute, com os mesmos argumentos do passo 4:

```bash
vostok task approve approve <SPEC_ID> <TASK_ID ...>
```

O comando confere de novo e aprova todas as tarefas pedidas, ou nenhuma. Se ele recusar, volte ao passo 4.

### 6. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** as tarefas aprovadas, na [lista de tarefas pendentes](#lista-de-tarefas-pendentes), com o novo status.
- **Verificação:** os comandos executados e o resultado.
- **Próximos passos:** a execução de uma tarefa aprovada, pedida pelo ID (skill `execute-task`).

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

### Lista de tarefas pendentes

```markdown
| Spec | ID | Título | Nível | Bloqueada por |
|---|---|---|---|---|
| SPEC-002 | TASK-03 | Título curto | moderada | TASK-02 |
```
