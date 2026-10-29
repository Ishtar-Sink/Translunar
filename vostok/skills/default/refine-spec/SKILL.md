---
name: refine-spec
description: Refina uma especificação (spec) em rascunho. Investiga o projeto e a memória, identifica ambiguidades, conflitos e lacunas, resolve com o usuário em rodadas de perguntas e gera em `refined/` uma spec detalhada, com seções conforme o tipo (feature, improvement, fix, study, analysis). Use quando o usuário pedir para refinar, detalhar ou esclarecer uma spec em rascunho (status draft), ou perguntar quais specs em draft estão prontas para refinamento. Não use para specs já refinadas: ajustes nelas são feitos pela skill adjust-spec.
allowed-tools: Read Edit Bash(vostok *)
metadata:
  version: "2.1.1"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok spec list, vostok memory search, vostok spec refine, vostok spec validate, vostok spec mark-refined"
  templates: "templates/spec/refined.md templates/spec/sections"
---

# Refinar spec

Transforma uma spec com status `draft` em uma spec refinada: concreta, sem ambiguidades conhecidas, com requisitos, testes e critérios de aceite rastreáveis e com cada decisão registrada.

## Termos

- **Rascunho:** a spec original, em `draft/`. Não é editada por esta skill.
- **Refinada:** a spec gerada em `refined/` pelo comando `vostok spec refine`.
- **Ambiguidade:** trecho com mais de uma interpretação válida.
- **Conflito:** trechos da spec que se contradizem.
- **Lacuna:** informação necessária que não está na spec.
- **Inferência:** decisão tomada pelo agente sem perguntar ao usuário.
- **Tipo:** a natureza da spec (`feature`, `improvement`, `fix`, `study` ou `analysis`), que define as seções da refinada.
- **Referência:** arquivo, entrada da memória ou documento consultado na investigação.
- **Rodada:** uma mensagem com todas as perguntas abertas, seguida da resposta do usuário.

## Regras

[refine-spec-01]: Nunca edite o rascunho. Só o comando muda o status dele, no passo 8. Não edite o "Histórico de ajustes": ele é do comando da skill `adjust-spec`.
[refine-spec-02]: Não pergunte durante a análise. Junte todas as perguntas e envie-as numa única mensagem por rodada.
[refine-spec-03]: No máximo 2 rodadas. O que continuar em aberto vai para a seção "Pendências" da refinada.
[refine-spec-04]: Não crie requisitos. Tudo o que não está no rascunho e não veio de uma resposta do usuário é inferência: aparece na tabela de inferências e no "Registro de decisões".
[refine-spec-05]: Tabelas trazem só texto relevante para a decisão, sem links, imagens ou formatação que dificulte a leitura.
[refine-spec-06]: Todo critério de aceite da refinada precisa ser verificável.
[refine-spec-07]: Nenhuma seção fica genérica. Cada seção traz informação concreta do projeto (caminhos, comandos, campos, IDs), vinda do rascunho, das respostas do usuário ou da investigação (com referência), ou registrada como inferência.
[refine-spec-08]: Uma lacuna é também uma seção do tipo que não pode ser preenchida com essa informação. Ela vira pergunta ou inferência, pelo critério do passo 4.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Identificar a spec
- [ ] 3. Investigar o projeto
- [ ] 4. Analisar a spec
- [ ] 5. Rodada de perguntas (máx. 2)
- [ ] 6. Criar a refinada
- [ ] 7. Preencher a refinada
- [ ] 8. Validar e marcar como refinada
- [ ] 9. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill refine-spec
```

### 2. Identificar a spec

**O usuário indicou uma spec** (ID, título ou arquivo):

1. Execute `vostok spec list` e encontre o ID correspondente.
2. Não encontrou: **PARE** e informe que a spec não existe.
3. Status diferente de `draft`: **PARE** e informe o status atual. Só rascunhos são refinados.

**O usuário não indicou nenhuma spec:**

1. Execute `vostok spec list draft`.
2. Nenhuma spec: **PARE** e informe que não há specs em draft.
3. Uma spec: use-a.
4. Mais de uma: **PARE** e pergunte qual refinar, com o template `question`, com uma opção por spec (ID e título).

### 3. Investigar o projeto

Leia o rascunho inteiro. Depois, antes de qualquer pergunta:

1. Busque decisões e conhecimentos com os termos do assunto, incluindo sinônimos:
   `vostok memory search all <termos>`
2. Leia os arquivos que o rascunho cita e os que ele envolve: os componentes que serão criados ou alterados, os scripts e configurações de que eles dependem e exemplos do mesmo tipo que já existam no projeto.
3. Anote cada item consultado e o uso dele. Eles vão para a seção "Referências".

Leia só o necessário para preencher as seções do tipo. Não altere nenhum arquivo neste passo.

### 4. Analisar a spec

1. Defina o tipo pela tabela de [references/sections.md](references/sections.md). Se o rascunho servir para mais de um tipo, pergunte.
2. Para cada seção do tipo (`sections_<tipo>` em `config/specs.yml`), verifique se o rascunho, a investigação e as inferências possíveis bastam para preenchê-la ([refine-spec-08]).
3. Classifique cada problema encontrado e decida como tratá-lo:

| Situação | Ação |
|---|---|
| Afeta escopo, arquitetura, critérios de aceite, custo ou prazo | Pergunta |
| Há uma interpretação claramente dominante e de baixo impacto | Inferência |
| Conflito entre trechos da spec | Pergunta, sempre |
| O rascunho contradiz uma decisão ativa da memória | Pergunta, sempre, citando o ID da decisão |

### 5. Rodada de perguntas

Sem perguntas: vá para o passo 6 e mostre as inferências na resposta final.

Com perguntas: envie numa única mensagem todas as perguntas, com o template `question`, seguidas da [tabela de inferências](#tabela-de-inferências). **PARE** e aguarde a resposta.

Ao receber as respostas:

- Se surgirem ambiguidades novas e esta for a 1ª rodada, faça a 2ª rodada.
- O que continuar sem resposta depois da 2ª rodada vira pendência ([refine-spec-03]).
- Uma inferência corrigida pelo usuário vira decisão.

### 6. Criar a refinada

Execute:

```bash
vostok spec refine <SPEC_ID> <tipo>
```

O comando monta a refinada com as seções do tipo e imprime o caminho do arquivo criado. Se ele falhar, **PARE** e responda com o template `blocker`.

### 7. Preencher a refinada

Leia [references/sections.md](references/sections.md) e preencha cada seção do arquivo criado, substituindo as variáveis `#{...}`. Mantenha os títulos e os cabeçalhos das tabelas como estão. Não deixe nenhuma variável `#{...}` no arquivo.

### 8. Validar e marcar como refinada

Execute:

```bash
vostok spec validate <SPEC_ID>
```

O comando lista todos os problemas, sem alterar nada: variáveis sem preencher, seções ausentes ou vazias, requisitos (`RF`) sem caso de teste ou critério de aceite, argumentos da tese ou da antítese fora da síntese e componentes afetados com ação ou caminho inconsistentes. Corrija os problemas e execute de novo. Se falhar pela segunda vez, **PARE** e responda com o template `blocker`.

Com a refinada válida, execute:

```bash
vostok spec mark-refined <SPEC_ID>
```

O comando grava o hash do conteúdo da refinada e muda o status do rascunho para `refined`.

### 9. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** o caminho e o tipo da refinada, um resumo de 1 a 3 frases do que mudou e a contagem de itens por seção (ex.: 8 RF, 12 CT, 6 CA).
- **Pendências:** o número de pendências registradas na refinada.
- Acrescente a [tabela de inferências](#tabela-de-inferências) com o cabeçalho "Inferências" depois de "O que foi feito", se ela ainda não foi mostrada numa rodada.

## Formatos de resposta

Perguntas usam o template `question`. Nas rodadas do passo 5, o contexto de cada pergunta cita o trecho da spec, e o fechamento ganha a frase: `Para corrigir uma inferência, cite a letra dela.`

### Tabela de inferências

Identifique as inferências por letras, a partir de A.

```markdown
| # | Inferência |
|---|---|
| A | O que foi inferido e com base em qual trecho da spec. |
```
