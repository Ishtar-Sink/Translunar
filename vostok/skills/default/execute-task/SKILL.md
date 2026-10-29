---
name: execute-task
description: "Executa uma tarefa aprovada de uma especificação (spec), em work/tasks/: confere se ela pode começar, coleta o baseline antes de qualquer mudança, implementa os testes pedidos em Verificação e depois o código, seguindo os passos, sem commit nem stage, e termina com a tarefa em execução, pronta para ser finalizada. Uma tarefa por pedido. Use quando o usuário pedir para executar, implementar, fazer ou começar uma tarefa, ou citar um ID como TASK-03 para execução."
allowed-tools: Read Edit Write Glob Grep Bash
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok task load, vostok task start, vostok task baseline, vostok commit check"
  templates: "templates/responses/question.md templates/responses/blocker.md templates/responses/completion.md"
---

# Executar tarefa

Leva uma tarefa aprovada de `approved` a `in_progress`, coleta o estado anterior (baseline) e implementa a tarefa, deixando-a em execução e pronta para ser finalizada pela skill `finish-task`.

## Termos

- **Tarefa:** o arquivo `vostok/work/tasks/<SPEC_ID>/<TASK_ID>.md`.
- **Executável:** tarefa com status `approved` e todas as dependências (`depends_on`) com status `done`.
- **Baseline:** a saída e o código de saída dos comandos de "Baseline", gravados antes de qualquer mudança em `evidence/<TASK_ID>/baseline/`. A `finish-task` os executa de novo e compara, para achar regressões.
- **Registro:** a seção "Registro de execução" da tarefa, com uma linha por etapa, escrita só pelos comandos.

## Regras

[execute-task-01]: Uma tarefa por pedido. Ao terminar, não comece outra sem um novo pedido do usuário.
[execute-task-02]: Só execute tarefas que o `vostok task start` aceitar. Não contorne uma recusa mudando o status, o hash ou as dependências.
[execute-task-03]: Colete o baseline antes de mudar qualquer arquivo do projeto.
[execute-task-04]: Siga "Mudar" e "Passos" da tarefa. Não amplie o escopo: o que for necessário e não estiver na tarefa vira pergunta ao usuário.
[execute-task-05]: Não faça commit nem stage ([agent/boundaries-01], [agent/boundaries-02]).
[execute-task-06]: Nunca edite o front-matter, o "Registro de execução" nem o "Histórico de ajustes" da tarefa. Só os comandos os alteram.
[execute-task-07]: Esta skill não valida nem conclui a tarefa e não chama a `finish-task` (RN-03). A finalização é um pedido separado do usuário.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Identificar a tarefa
- [ ] 3. Iniciar
- [ ] 4. Carregar a tarefa
- [ ] 5. Coletar o baseline
- [ ] 6. Implementar os testes
- [ ] 7. Implementar o código
- [ ] 8. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill execute-task
```

### 2. Identificar a tarefa

As tarefas ficam em `vostok/work/tasks/<SPEC_ID>/`, e os IDs são numerados dentro de cada spec. Procure a tarefa citada com Glob (`vostok/work/tasks/*/TASK-05.md`):

- Tarefa citada que existe numa única spec: use essa.
- Tarefa citada que existe em mais de uma spec: **PARE** e pergunte de qual, com o template `question`.
- Sem citação ("executa a próxima"): leia o front-matter das tarefas e liste as executáveis. Uma só: use essa. Mais de uma: **PARE** e pergunte qual, com o template `question`, usando a [lista de tarefas executáveis](#lista-de-tarefas-executáveis). Nenhuma: informe as tarefas aprovadas com dependências pendentes e as pendentes de aprovação, e encerre.

### 3. Iniciar

Execute:

```bash
vostok task start <SPEC_ID> <TASK_ID>
```

O comando confere se a tarefa está aprovada, sem mudança depois da aprovação e com as dependências concluídas, e muda o status para `in_progress`. Se ele recusar, **PARE** e responda com o template `blocker`, com a mensagem do comando:

| Recusa | Como resolver |
|---|---|
| Tarefa fora de `approved` | Aprovar a tarefa (skill `approve-task`), a pedido do usuário. |
| Tarefa mudou depois da aprovação | Registrar o ajuste (skill `adjust-task`) e aprovar de novo. |
| Dependência fora de `done` | Executar e concluir a dependência antes. |

### 4. Carregar a tarefa

Execute `vostok task load <SPEC_ID> <TASK_ID>` e leia os arquivos de "Ler".

### 5. Coletar o baseline

Antes de mudar qualquer arquivo, execute:

```bash
vostok task baseline <SPEC_ID> <TASK_ID>
```

O `vostok task baseline` executa cada comando de "Baseline" a partir da raiz do projeto e grava o resultado. Um código de saída diferente de zero não impede a coleta: ele é o estado anterior, e a `finish-task` compara com ele. Se o comando recusar, **PARE** e responda com o template `blocker`.

### 6. Implementar os testes

Implemente primeiro os testes automatizados que a "Verificação" e os "Passos" pedem, para que comprovem a tarefa antes do código existir.

### 7. Implementar o código

Siga os "Passos", na ordem, mudando só os arquivos de "Mudar". Se um passo exigir algo fora da tarefa, **PARE** e pergunte ao usuário, com o template `question`.

### 8. Responder ao usuário

Execute `vostok commit check` e responda com o template `completion`:

- **Resumo:** a tarefa foi implementada e segue `in_progress`.
- **Verificação:** o que foi feito nesta execução, com as linhas do "Registro de execução" da tarefa (início e baseline), e o que não foi verificado: os testes, a regressão e as evidências ficam para a `finish-task`.
- **Próximos passos:** o pedido em linguagem natural para finalizar a tarefa, por exemplo `- "finaliza a TASK-04" (skill finish-task): executar os testes, comparar com o baseline e concluir a tarefa`. Nunca indique um comando.

Esta skill não chama a `finish-task` nem roda `vostok task tests`, `vostok task regression` ou `vostok task evidence` (RN-03): a conclusão só começa quando o usuário pedir.

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

### Lista de tarefas executáveis

```markdown
| Spec | ID | Título | Nível |
|---|---|---|---|
| SPEC-002 | TASK-05 | Título curto | complexa |
```
