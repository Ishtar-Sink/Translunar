---
name: approve-plan
description: "Aprova o plano de tarefas de uma especificação (spec) aprovada. Cria um arquivo por tarefa na pasta de tarefas da spec, em work/tasks/, detalha cada uma com a execução para o agente (arquivos, passos, verificação) e a descrição para pessoas (resumo executivo, detalhes técnicos e card para board), remove o plano e marca a spec como planned. Use quando o usuário pedir para aprovar o plano de tarefas ou disser que aprova o plano."
allowed-tools: Read Edit Glob Bash(vostok *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok plan approve create-tasks, vostok plan approve validate, vostok plan approve mark-planned, vostok task load"
  templates: "templates/task/task.md"
---

# Aprovar plano

Transforma o plano de tarefas aprovado pelo usuário em arquivos de tarefa detalhados: prontos para um agente executar e para pessoas acompanharem num board.

## Termos

- **Plano:** o arquivo `vostok/work/plans/<SPEC_ID>.md`. É removido pelo comando depois da aprovação.
- **Tarefa:** o arquivo `vostok/work/tasks/<SPEC_ID>/TASK-NN.md`, criado pelo comando a partir do plano.
- **Execução:** a seção da tarefa lida pelo agente que a executa (`vostok task load`): "Ler", "Mudar", "Passos", "Baseline", "Verificação", "Evidências" e "Concluída quando".
- **Descrição:** a seção da tarefa para leitura humana: "Resumo executivo", "Detalhes técnicos" e "Card".
- **Planejada:** a spec com status `planned`, depois da aprovação do plano. Não é mais ajustada nem planejada.
- **Impedimento:** o que impede a aprovação: spec fora de `approved` ou alterada, plano desatualizado, edição manual sem registro ou problema de validação.

## Regras

[approve-plan-01]: Só aprove a pedido do usuário. Nunca aprove por iniciativa própria, nem como parte de outro fluxo.
[approve-plan-02]: Nunca aprove um plano sobre o qual tenha dúvida de ser o correto. Na dúvida, pergunte (passo 2).
[approve-plan-03]: Não resolva impedimentos por conta própria. Responda com o template `blocker`; mudanças no plano são feitas pela skill `adjust-plan`.
[approve-plan-04]: Nunca edite o plano, a spec nem o front-matter das tarefas. Nas tarefas, só substitua as variáveis `#{...}`.
[approve-plan-05]: O detalhamento segue o plano e a spec. Não acrescente escopo, tarefas nem cobertura.
[approve-plan-06]: A "Execução" é escrita para um agente sem outro contexto: caminhos exatos, passos na ordem e comandos que possam ser executados.
[approve-plan-07]: O "Resumo executivo" usa linguagem de negócio, sem nomes de arquivos, funções ou comandos.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Identificar o plano
- [ ] 3. Criar as tarefas
- [ ] 4. Detalhar as tarefas
- [ ] 5. Validar
- [ ] 6. Marcar a spec como planejada
- [ ] 7. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill approve-plan
```

### 2. Identificar o plano

Os planos existentes são os arquivos de `vostok/work/plans/`, um por spec, com o ID da spec no nome.

Use o plano sem perguntar em qualquer um destes casos:

- O usuário cita a spec ou o plano por ID, título ou arquivo.
- O pedido vem logo depois de o plano ser criado ou ajustado nesta conversa.
- Existe um único plano.

Nos demais casos:

1. Nenhum plano: **PARE** e informe que não há plano de tarefas para aprovar.
2. Mais de um: **PARE** e pergunte qual aprovar, com o template `question`, com uma opção por plano (ID e título da spec). Aceite também resposta livre. Não aprove nada antes da resposta.

### 3. Criar as tarefas

Se a pasta `vostok/work/tasks/<SPEC_ID>/` já existe e o plano também, uma aprovação anterior foi interrompida: não execute o `vostok plan approve create-tasks` e vá para o passo 4 com as tarefas existentes.

Senão, execute:

```bash
vostok plan approve create-tasks <SPEC_ID>
```

O comando confere os impedimentos e cria um arquivo por tarefa, com o front-matter e os campos conhecidos do card. Se ele recusar, **PARE** e responda com o template `blocker`, com a mensagem do comando:

| Impedimento | Como resolver |
|---|---|
| Spec fora de `approved` ou alterada depois da aprovação | Aprovar a spec de novo e recriar o plano com a skill `plan-tasks`. |
| Plano desatualizado | Recriar o plano com a skill `plan-tasks`. |
| Edição manual sem registro | Executar o comando indicado na saída (`vostok plan adjust record-manual`) ou pedir um ajuste. |
| Problema de validação do plano | Ajustar o plano com a skill `adjust-plan`. |

### 4. Detalhar as tarefas

Leia a spec aprovada e o plano. Para cada tarefa, investigue os arquivos do projeto que ela toca e substitua as variáveis `#{...}` do arquivo:

**Execução** (para o agente):

- **`#{TASK_READ}`:** lista de `` - `caminho` `` com o que ler antes de mudar: arquivos afetados, vizinhos que servem de exemplo e a spec.
- **`#{TASK_CHANGE}`:** lista no formato `` - `caminho` (ação): motivo ``, com caminhos relativos à raiz do projeto e ação `criar`, `alterar` ou `remover`. `criar` só para caminhos que ainda não existem; as demais, só para caminhos existentes ou criados por uma tarefa de que esta depende, direta ou indiretamente.
- **`#{TASK_STEPS}`:** passos numerados, na ordem, cada um com uma ação concreta.
- **`#{TASK_BASELINE}`:** lista de `` - `comando` ``, ao menos um, com os comandos rodados antes da mudança e de novo depois, para comparar o resultado. Só comandos estáveis: sem data, sem caminho temporário e sem nada que mude entre execuções.
- **`#{TASK_VERIFY}`:** bloco `bash` com os comandos que comprovam a tarefa (testes, validações) e o resultado esperado.
- **`#{TASK_EVIDENCE}`:** lista com um item por evidência: `` - `arquivo` (automática): `comando` `` (a saída do comando vira o arquivo) ou `` - `arquivo` (manual): o que o usuário deve anexar ``. `arquivo` é só o nome do arquivo, sem caminho, sem começar por `.` e diferente de `baseline` e `validation`: a evidência é gravada com esse nome na pasta de evidências da tarefa. Com `persist_dir` configurado em `config/tasks.yml`, a cópia das evidências para o projeto é feita pelo `vostok task persist`: o item nunca leva o destino da cópia. Prefira a automática; use a manual só quando não houver comando que a produza. Sem evidência, escreva `Não se aplica.` Sob cada evidência, recuados com dois espaços, escreva os subitens que explicam como interpretá-la para quem não executou a tarefa:
  - `Prova:` o que a evidência prova e os critérios ou IDs que ela cobre.
  - `Trecho:` o que procurar na saída (a linha, o valor ou a mensagem que comprova).
  - `Falha:` o que apareceria se a tarefa tivesse falhado.
  - `Artefato:` opcional, o artefato medido (versão, build type, SHA-256).

  ```markdown
  - `cargo-test.txt` (automática): `cargo test`
    - Prova: os testes do aceite passam (RF-01, CT-01).
    - Trecho: as linhas `test accepted_... ok` e `test result: ok`.
    - Falha: `FAILED` ou `test result: FAILED`.
  ```
- **`#{TASK_DONE}`:** checklist dos critérios objetivos de conclusão, ligados aos IDs cobertos. Cada critério é um item `- [ ] critério (IDs).`, seguido de uma linha em branco e da comprovação numa citação recuada com dois espaços, `  > Como comprovar: ...`, com uma linha em branco entre os critérios. "Como comprovar" é escrito para uma pessoa entender: diz em linguagem simples o que conferir e qual o resultado esperado (ex.: "abrir `config/tasks.yml` e ver `max_attempts: 2`", "rodar a suíte e ver 'Falhou: 0'"), citando o comando, o caso da suíte ou o arquivo de evidência só como apoio. O agente que executa a tarefa marca `[x]` em cada item só depois de conferir a comprovação.

**Descrição** (para pessoas):

- **`#{TASK_EXECUTIVE_SUMMARY}`:** até 5 linhas, em linguagem de negócio: objetivo, benefício, esforço (o nível), risco e o que a tarefa bloqueia ou desbloqueia.
- **`#{TASK_TECHNICAL_DETAILS}`:** a abordagem, os componentes afetados, as decisões com as alternativas descartadas, os riscos técnicos e as referências da spec (RF, CT e decisões).
- **`#{TASK_CARD_DESCRIPTION}`:** uma ou duas frases sobre o que a tarefa entrega, pronta para o card.
- **`#{TASK_CARD_CRITERIA}`:** checklist de critérios de aceite, cada item como `  - [ ] critério`, indentado sob "Critérios de aceite".

### 5. Validar

Execute:

```bash
vostok plan approve validate <SPEC_ID>
```

O comando lista os problemas das tarefas sem alterar nada. Corrija-os e execute de novo. Se falhar pela segunda vez, **PARE** e responda com o template `blocker`.

### 6. Marcar a spec como planejada

Execute:

```bash
vostok plan approve mark-planned <SPEC_ID>
```

O comando valida de novo, muda o status da spec para `planned` e remove o plano. Se ele falhar, volte ao passo 5.

### 7. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** a pasta das tarefas, a [lista de tarefas](#lista-de-tarefas), a remoção do plano e o novo status da spec.
- **Verificação:** os comandos executados e o resultado.
- **Pendências:** informe que cada tarefa é carregada para execução com `vostok task load <SPEC_ID> <TASK_ID>` e que o nível é só uma sugestão de esforço.

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

### Lista de tarefas

```markdown
| ID | Título | Tipo | Nível | Bloqueada por |
|---|---|---|---|---|
| TASK-01 | Título curto | tarefa | simples | - |
```
