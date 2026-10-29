---
name: approve-spec
description: "Aprova uma especificação (spec) refinada, com status refined. Confere se a spec está válida, sem pendências abertas e sem edições manuais sem registro, muda o status para approved, grava a versão aprovada para a granularização e remove o rascunho. Use quando o usuário pedir para aprovar uma spec, disser que aprova ou que a spec está aprovada, ou citar um ID como SPEC-001 para aprovação."
allowed-tools: Read Bash(vostok *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok spec list, vostok spec approve validate, vostok spec approve approve"
---

# Aprovar spec

Aprova a spec refinada certa, de forma determinística, deixando registrado qual versão foi aprovada.

## Termos

- **Refinada:** a spec em `refined/`, com status `refined`. É a única que pode ser aprovada.
- **Aprovada:** a refinada com status `approved`. Continua em `refined/`, com `approved_at` e `approved_hash` no front-matter.
- **Rascunho:** a spec original, em `draft/`. É removido pelo comando depois da aprovação.
- **Impedimento:** o que impede a aprovação: status errado, problema de validação, pendência aberta ou edição manual sem registro.
- **Versão aprovada:** o `content_hash` no momento da aprovação, gravado em `approved_hash`. Um ajuste depois dela derruba a aprovação.

## Regras

[approve-spec-01]: Só aprove a pedido do usuário. Nunca aprove por iniciativa própria, nem como parte de outro fluxo.
[approve-spec-02]: Nunca aprove uma spec sobre a qual tenha dúvida de ser a correta. Na dúvida, pergunte (passo 2).
[approve-spec-03]: Nunca edite a spec nem o front-matter nesta skill. Quem aprova e remove o rascunho é o comando.
[approve-spec-04]: Não resolva impedimentos por conta própria. Responda com o template `blocker`; correções na spec são feitas pela skill `adjust-spec`.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Identificar a spec
- [ ] 3. Conferir os impedimentos
- [ ] 4. Aprovar
- [ ] 5. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill approve-spec
```

### 2. Identificar a spec

Para saber quais specs podem ser aprovadas, execute `vostok spec list refined` e considere só as linhas com arquivo em `refined/`. O rascunho de uma spec refinada também aparece na lista, com o mesmo ID.

Use a spec sem perguntar em qualquer um destes casos:

- O usuário a cita por ID, título ou arquivo.
- O pedido vem logo depois de a spec ser refinada ou ajustada nesta conversa.
- Existe uma única spec refinada.

Nos demais casos:

1. Nenhuma spec refinada: **PARE** e informe que não há specs refinadas para aprovar.
2. Mais de uma: **PARE** e pergunte qual aprovar, com o template `question`, com uma opção por spec (ID e título). Aceite também resposta livre. Não aprove nada antes da resposta.

Spec citada com status `draft`: **PARE** e informe que ela precisa ser refinada antes. Spec citada com status `approved`: **PARE** e informe que ela já está aprovada.

### 3. Conferir os impedimentos

Execute:

```bash
vostok spec approve validate <SPEC_ID>
```

O comando lista cada impedimento, sem alterar nada. Com impedimentos, **PARE** e responda com o template `blocker`:

| Impedimento | Como resolver |
|---|---|
| Problema de validação | Ajustar a spec com a skill `adjust-spec`. |
| Pendência aberta | Responder à pendência; o ajuste é feito com a skill `adjust-spec`. |
| Edição manual sem registro (inclusive spec sem `content_hash`) | Executar o comando indicado na saída (`vostok spec adjust record-manual`) ou pedir um ajuste. |

### 4. Aprovar

Execute:

```bash
vostok spec approve approve <SPEC_ID>
```

O comando confere os impedimentos de novo, muda o status para `approved`, grava `approved_at` e `approved_hash` e remove o rascunho. Se ele falhar, **PARE** e responda com o template `blocker`, com a mensagem do comando.

### 5. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** o ID e o caminho da spec aprovada e se o rascunho foi removido.
- **Verificação:** os comandos executados e o resultado.
- **Pendências:** informe que um ajuste na spec derruba a aprovação e que ela está pronta para a granularização.
