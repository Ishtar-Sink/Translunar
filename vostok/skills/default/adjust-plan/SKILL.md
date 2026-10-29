---
name: adjust-plan
description: "Ajusta o plano de tarefas de uma especificação (spec) aprovada, em work/plans/. Aplica um ou vários ajustes pedidos numa mesma mensagem (dividir, juntar, remover ou reordenar tarefas, mudar dependências, cobertura ou fatos de esforço), registra edições feitas à mão, recalcula os níveis e mantém o histórico de ajustes do plano. Use quando o usuário pedir para ajustar, corrigir, mudar, dividir, juntar ou remover algo do plano de tarefas, ou comentar o plano logo depois de ele ser criado ou ajustado."
allowed-tools: Read Edit Glob Bash(vostok *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok memory search, vostok plan adjust record-manual, vostok plan adjust validate, vostok plan adjust record"
---

# Ajustar plano

Aplica ao plano de tarefas certo todos os ajustes que o usuário pediu, deixando o plano válido, com os níveis recalculados e cada ajuste registrado no histórico.

## Termos

- **Plano:** o arquivo `vostok/work/plans/<SPEC_ID>.md`, criado pela skill `plan-tasks`. É o único que esta skill edita.
- **Plano desatualizado:** plano com `spec_hash` diferente do `approved_hash` da spec. Não é ajustado: é recriado pela `plan-tasks`.
- **Pedido:** a mensagem do usuário com um ou mais ajustes.
- **Ajuste:** uma mudança pedida, com um único alvo e uma única ação. Um pedido pode ter vários ajustes.
- **Alvo:** o ponto do plano que o ajuste muda: uma tarefa (`TASK-03`), uma coluna, um fato ou a visão geral.
- **Edição manual:** mudança feita à mão no plano, fora desta skill. O comando a detecta pelo hash do conteúdo.
- **Histórico:** a seção "Histórico de ajustes" do plano, escrita só pelo comando.
- **Inferência:** decisão tomada pelo agente sem perguntar ao usuário.

## Regras

[adjust-plan-01]: Só ajuste planos existentes e atualizados. Nunca edite a spec nem arquivos de tarefa.
[adjust-plan-02]: Nunca edite um plano sem ter certeza de que é o correto. Na dúvida, pergunte (passo 2).
[adjust-plan-03]: Nunca edite à mão o front-matter, a coluna "Nível", a seção "Níveis de esforço" nem o "Histórico de ajustes". Só os comandos os alteram.
[adjust-plan-04]: Todo ajuste do pedido é aplicado ou vira pergunta. Nenhum é descartado sem aviso.
[adjust-plan-05]: No máximo 1 rodada de perguntas, sempre antes de qualquer edição.
[adjust-plan-06]: Não amplie o pedido. O que não foi pedido e for necessário para o plano continuar coerente (renumerar dependências, redistribuir cobertura) é inferência e aparece na resposta.
[adjust-plan-07]: Todos os ajustes de um pedido são registrados juntos, com um único `vostok plan adjust record`.
[adjust-plan-08]: Não aprove o plano como parte do ajuste. A aprovação é feita pela skill `approve-plan`, só a pedido do usuário.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Identificar o plano
- [ ] 3. Registrar edições manuais
- [ ] 4. Decompor o pedido em ajustes
- [ ] 5. Analisar os ajustes
- [ ] 6. Rodada de perguntas (máx. 1)
- [ ] 7. Editar o plano
- [ ] 8. Validar
- [ ] 9. Registrar o ajuste
- [ ] 10. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill adjust-plan
```

Os formatos das tabelas do plano estão em "Formatos de resposta" da skill [plan-tasks](../plan-tasks/SKILL.md).

### 2. Identificar o plano

Os planos existentes são os arquivos de `vostok/work/plans/`, um por spec, com o ID da spec no nome.

Use o plano sem perguntar em qualquer um destes casos:

- O usuário cita a spec ou o plano por ID, título ou arquivo.
- O pedido vem logo depois de o plano ser criado ou ajustado nesta conversa.
- Existe um único plano.

Nos demais casos:

1. Nenhum plano: **PARE** e informe que não há plano de tarefas para ajustar.
2. Mais de um: **PARE** e pergunte qual ajustar, com o template `question`, com uma opção por plano (ID e título da spec). Aceite também resposta livre. Não edite nada antes da resposta.

Spec citada sem plano: **PARE** e informe que ela não tem plano; o plano é criado pela skill `plan-tasks`.

### 3. Registrar edições manuais

Execute:

```bash
vostok plan adjust record-manual <SPEC_ID>
vostok plan adjust validate <SPEC_ID>
```

Se a validação apontar plano desatualizado, **PARE** e responda com o template `blocker`: o plano deve ser recriado com a skill `plan-tasks`. Outros problemas são corrigidos no passo 7, junto com os ajustes do pedido.

### 4. Decompor o pedido em ajustes

Leia o plano inteiro e a spec. Depois, separe o pedido em ajustes, qualquer que seja a forma:

| Forma do pedido | Como separar |
|---|---|
| Prosa | Cada verbo de mudança sobre um alvo diferente é um ajuste. "Divida a TASK-02 e remova a TASK-04" são dois. |
| Lista enumerada ou com marcadores | Cada item é um ajuste. Um item com dois alvos vira dois. |
| Citação exata (ID de tarefa, coluna, trecho entre aspas) | O alvo é o citado. Mude só ele. |
| Texto a substituir ("onde está A, coloque B") | O alvo é o trecho A. |
| Mistura das formas acima | Aplique cada regra à sua parte. |

O mesmo pedido repetido em formas diferentes é um único ajuste.

Para cada ajuste, anote o alvo e tudo o que ele afeta indiretamente: dividir uma tarefa pede novos fatos e redistribui a cobertura; remover uma tarefa tira-a das dependências das outras e exige que os IDs que ela cobria passem a outra tarefa.

### 5. Analisar os ajustes

Classifique cada ajuste:

| Situação | Ação |
|---|---|
| Claro, com alvo existente | Aplicar |
| Ambíguo: mais de uma interpretação válida | Pergunta |
| Deixa um ID da spec sem tarefa e não diz qual tarefa o assume | Pergunta |
| Cria dependência em ciclo | Pergunta |
| Contradiz outro ajuste do mesmo pedido | Pergunta |
| Cita um alvo que não existe (ex.: `TASK-40`) | Pergunta |
| Contradiz uma decisão ativa da memória (`vostok memory search decision <termos>`) | Pergunta, citando o ID da decisão |
| Exige mudar a spec | **PARE**: responda com o template `blocker`; a spec é ajustada pela skill `adjust-spec` e o plano, recriado depois. |

Sem perguntas, vá para o passo 7.

### 6. Rodada de perguntas

Envie numa única mensagem, com o template `question`, uma pergunta para cada ajuste classificado como pergunta, citando o ajuste e o trecho do plano. **PARE** e aguarde a resposta.

Não edite nada antes da resposta, nem os ajustes claros. Depois dela, aplique todos juntos. O que continuar sem resposta não é aplicado e aparece em "Pendências" da resposta.

### 7. Editar o plano

Aplique os ajustes nas seções "Visão geral", "Tarefas" e "Fatos de esforço":

- Os IDs das tarefas continuam sequenciais a partir de `TASK-01`. Ao renumerar, atualize as dependências.
- Toda tarefa tem uma linha na tabela de fatos, e toda linha de fatos tem uma tarefa.
- Na coluna "Nível", deixe o valor atual ou `-`: o `vostok plan adjust record` recalcula.
- Atualize a visão geral se a divisão ou a ordem do trabalho mudou.

### 8. Validar

Execute:

```bash
vostok plan adjust validate <SPEC_ID>
```

O comando lista os problemas sem alterar nada. Diferenças de nível são resolvidas pelo `vostok plan adjust record`; corrija os demais e execute de novo. Se falhar pela segunda vez com outros problemas, **PARE** e responda com o template `blocker`.

### 9. Registrar o ajuste

Execute, com um item por ajuste no resumo, separados por `; `:

```bash
vostok plan adjust record <SPEC_ID> "TASK-02 dividida em TASK-02 e TASK-03; TASK-05 removida"
```

O comando recalcula os níveis, valida de novo, incrementa `adjustments`, atualiza as datas e o hash e acrescenta uma linha ao histórico. Se ele recusar o ajuste, volte ao passo 8.

### 10. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** o caminho do plano, o número do ajuste, a [tabela de ajustes](#tabela-de-ajustes) e o plano atualizado no formato "Resumo do plano" da skill `plan-tasks`.
- Se houve ajuste manual no passo 3, informe o número dele.
- Acrescente a lista de inferências, se houver, com a letra e o que foi inferido.
- **Pendências:** os ajustes que ficaram sem resposta. Informe que o plano pode receber novos ajustes ou ser aprovado (skill `approve-plan`).

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

### Tabela de ajustes

Uma linha por ajuste identificado no pedido, na ordem em que aparecem.

```markdown
| # | Ajuste pedido | O que foi feito |
|---|---|---|
| 1 | Resumo do pedido, com o alvo. | Tarefas, dependências e fatos alterados. |
```
