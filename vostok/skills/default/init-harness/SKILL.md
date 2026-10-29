---
name: init-harness
description: "Inicializa o harness num projeto: investiga o código (manifestos, configurações de lint e de teste, estrutura de pastas), propõe regras por categoria citando a origem de cada uma, pergunta numa única rodada o que não se aplica, quais regras valem e onde cada categoria é carregada, e grava só o confirmado em rules/project/ e no mapa de contexto. Numa reexecução, mostra o que mudaria e altera só o que o usuário confirmar. Use quando o usuário pedir para inicializar o harness, levantar as regras do projeto, configurar as regras ou rodar o init."
allowed-tools: Read Write Glob Grep Bash(vostok *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok rules detect, vostok rules preview, vostok rules write, vostok rules load, vostok rules validate"
  templates: "templates/rules/category.md templates/responses/question.md templates/responses/completion.md templates/responses/blocker.md"
---

# Inicializar harness

Levanta as regras do projeto a partir do que o código mostra, confirma com o usuário numa única rodada e deixa o harness com as categorias gravadas em `rules/project/` e carregadas onde o usuário escolheu.

## Termos

- **Categoria:** arquivo `rules/project/<categoria>.md`, com título, frase de propósito e regras `[project/<categoria>-NN]`. O nome é o da categoria, em kebab-case.
- **Categoria base:** uma das oito que a skill sempre percorre: `architecture`, `stack`, `code-style`, `development-methodology`, `testing`, `security`, `language` e `naming-convention`.
- **Categoria extra:** categoria que a investigação sugere além das base, por exemplo `api`, `database` ou `frontend`.
- **Sinal:** arquivo ou pasta do projeto que indica uma categoria, no formato `categoria: arquivo: sinal`, listado pelo `vostok rules detect`.
- **Origem:** o arquivo ou sinal que fundamenta uma regra proposta.
- **Carregamento:** onde a categoria entra no contexto: `required` (sempre) ou a lista de uma skill no mapa `skills` do `config/context.yml`.
- **Arquivo de regras:** arquivo temporário, fora do projeto, com uma regra por linha, entregue ao `vostok rules write`.
- **Projeto já inicializado:** projeto que já tem categorias em `rules/project/`.

## Regras

[init-harness-01]: Investigue o projeto antes de perguntar. Toda regra proposta a partir do código cita a origem; regra sem origem é pergunta ao usuário, nunca afirmação.
[init-harness-02]: Uma única rodada de perguntas, com o template `question`, com tudo junto: o que não se aplica, as regras de cada categoria e o carregamento de cada uma.
[init-harness-03]: Grave só o que o usuário confirmar. Sem confirmação, não grave, não altere e não registre nada.
[init-harness-04]: Categoria que o usuário disser que não se aplica não ganha arquivo nem entrada no mapa.
[init-harness-05]: Não crie regra que não veio do código nem de uma resposta do usuário.
[init-harness-06]: Grave categorias e carregamento só pelos comandos `vostok rules write` e `vostok rules load`. Não edite `rules/project/*.md` nem o `config/context.yml` à mão.
[init-harness-07]: Não faça commit nem stage ([agent/boundaries-01], [agent/boundaries-02]).

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Investigar o projeto
- [ ] 3. Montar as propostas
- [ ] 4. Rodada de perguntas
- [ ] 5. Gravar o confirmado
- [ ] 6. Registrar o carregamento
- [ ] 7. Validar
- [ ] 8. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill init-harness
```

### 2. Investigar o projeto

Execute:

```bash
vostok rules detect
```

Cada linha é um sinal (`categoria: arquivo: sinal`). Leia os arquivos citados e complete a investigação com os manifestos (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`), as configurações de lint e de teste e a estrutura de pastas, usando Glob, Grep e Read. Anote a origem de cada regra que você for propor.

Liste também as categorias que já existem em `rules/project/` e leia-as:

- **Sem nenhum sinal** (projeto sem código): não proponha regras a partir de arquivos. Pule o passo 3 e faça no passo 4 só as perguntas abertas por categoria.
- **Com categorias existentes** (projeto já inicializado): trate cada categoria como alteração, conforme o passo 3.
- **Sinais de mais de uma stack** (por exemplo `package.json` e `Cargo.toml`): proponha as regras das duas e pergunte quais valem.

### 3. Montar as propostas

Percorra as oito categorias base, na ordem: `architecture`, `stack`, `code-style`, `development-methodology`, `testing`, `security`, `language` e `naming-convention`. Para cada uma, escreva regras curtas, verificáveis e com a origem. Em `language` e `naming-convention`, parta das regras existentes em `rules/project/`, se houver.

Acrescente categorias extras pelo que a investigação encontrou (`api`, `database`, `frontend` e outras), sempre com a origem. Sinal sem regra concreta não vira categoria.

Para uma categoria que já existe, monte o arquivo de regras só com o que mudaria (regras novas e `remover: NN`) e veja o efeito:

```bash
vostok rules preview <categoria> <arquivo-de-regras>
```

O arquivo de regras é temporário (`mktemp`), fora do projeto, e tem uma regra por linha. Linhas opcionais: `titulo: <título>`, `proposito: <frase>` e `remover: NN`.

### 4. Rodada de perguntas

**PARE.** Envie uma única mensagem com o template `question`, uma pergunta por assunto:

1. Quais categorias **não se aplicam** (as oito base e as extras propostas).
2. Para cada categoria que se aplica, as regras propostas com a origem, para o usuário aceitar, cortar ou acrescentar. Numa categoria existente, mostre o que mudaria (saída do `vostok rules preview`).
3. Para cada categoria, **onde é carregada**: sempre (`required`) ou em quais skills do mapa (liste as skills existentes do catálogo).

Se uma resposta ficar em aberto, a categoria correspondente não é gravada e a pendência vai na resposta final. Não faça uma segunda rodada. Se o usuário não confirmar nada, **nenhum arquivo é alterado**: pule para o passo 8.

### 5. Gravar o confirmado

Para cada categoria confirmada, escreva o arquivo de regras temporário só com as regras aceitas e execute:

```bash
vostok rules write <categoria> <arquivo-de-regras>
```

O comando cria o arquivo pelo template, numera os IDs e, numa categoria existente, acrescenta as regras novas, marca as removidas e não repete as que já estão lá. Não grave as categorias que não se aplicam. Se o comando recusar, **PARE** e responda com o template `blocker`.

### 6. Registrar o carregamento

Para cada categoria gravada, execute:

```bash
vostok rules load <categoria> always
vostok rules load <categoria> <skill>[,<skill>...]
```

Use `always` para `required` e a lista de skills para o mapa `skills`. Categoria sem resposta de carregamento não é registrada. Se o comando recusar (skill inexistente, por exemplo), **PARE** e responda com o template `blocker`.

### 7. Validar

Execute:

```bash
vostok rules validate
```

Se ele apontar problemas, corrija pela mesma via do passo 5 ou 6 e execute de novo. Se falhar pela segunda vez, **PARE** e responda com o template `blocker`.

### 8. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** as categorias gravadas ou alteradas, a contagem de regras de cada uma e onde cada categoria é carregada (`required` ou as skills). Sem nenhuma confirmação, diga que nada foi alterado.
- **Pendências:** categorias deixadas de fora por falta de resposta e o que a investigação não conseguiu determinar.

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formato próprio desta skill, o resumo por categoria:

| Categoria | Regras | Carregada em |
|---|---|---|
| testing | 4 | execute-task, finish-task |
| language | 2 | sempre |
