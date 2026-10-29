---
name: create-skill
description: "Cria uma nova skill do harness no formato padrão: gera o SKILL.md a partir do template, os redirecionamentos para Claude Code, Codex e Cursor e a entrada no catálogo, e propõe subcomandos do vostok para as operações determinísticas. Use quando o usuário pedir para criar, adicionar ou gerar uma skill ou habilidade, ou transformar um fluxo de trabalho em skill. Use sempre esta skill em vez dos criadores de skill nativos das ferramentas."
allowed-tools: Read Edit Bash(vostok *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok skill create, vostok skill finalize"
  templates: "templates/skill/skill.md templates/skill/redirect.md"
---

# Criar skill

Cria uma skill no local certo e no formato padrão do harness, pronta para ser invocada por linguagem natural em qualquer ferramenta configurada.

## Termos

- **Skill:** pasta com um `SKILL.md` em `skills/custom/` (do usuário) ou `skills/default/` (do harness).
- **Subcomando:** comando do `vostok` (`vostok <grupo> <ação>`) que executa uma operação determinística.
- **Redirecionamento:** `SKILL.md` curto, criado na pasta de skills de cada ferramenta (`config/skills.yml`), que aponta para a skill.
- **Catálogo:** `context/skill-catalog.md`, carregado em toda sessão.
- **Operação determinística:** passo que sempre produz o mesmo resultado para a mesma entrada (ler arquivos, validar, gerar a partir de template).

## Regras

[create-skill-01]: Nunca use o criador de skills nativo da ferramenta. Toda skill é criada por esta skill.
[create-skill-02]: Nunca crie ou edite à mão os redirecionamentos nem a linha do catálogo. Eles são gerados no passo 6.
[create-skill-03]: Operações determinísticas são executadas por subcomandos do `vostok`. O SKILL.md só manda executá-los, com o comando exato. Nunca crie scripts na pasta da skill.
[create-skill-04]: A `description` fica em terceira pessoa e diz o que a skill faz e quando usar, com os termos que o usuário diria.
[create-skill-05]: Use um único termo para cada conceito, definido em "Termos".
[create-skill-06]: Todo ponto em que a skill deve parar e esperar o usuário é marcado com **PARE** e a condição.
[create-skill-07]: No máximo 1 rodada de perguntas ao usuário. O que continuar em aberto vira decisão sua, informada na resposta final.
[create-skill-08]: Respostas ao usuário na skill criada usam os templates de `templates/responses/` ([agent/responses-01]). A seção "Formatos de resposta" traz só formatos próprios da skill.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Levantar os requisitos
- [ ] 3. Criar a skill
- [ ] 4. Propor os subcomandos
- [ ] 5. Preencher o SKILL.md
- [ ] 6. Validar e finalizar
- [ ] 7. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill create-skill
```

### 2. Levantar os requisitos

Extraia do pedido do usuário:

| Item | Exemplo |
|---|---|
| Nome, em kebab-case | `review-code` |
| Objetivo, em uma frase | Revisa o diff atual contra as regras do projeto. |
| Gatilhos: frases que o usuário diria | "revisa meu código", "faz code review" |
| Entradas | ID da spec, caminho, nenhuma |
| Passos e pontos de parada | — |
| Operações determinísticas | listar arquivos, validar formato |
| Escopo: `custom` ou `default` | `custom`, a menos que o usuário peça uma skill do próprio harness |

Se faltar algum item que não pode ser inferido, **PARE** e pergunte com o template `question`, numa única mensagem.

### 3. Criar a skill

Execute:

```bash
vostok skill create <nome>
```

Para uma skill do próprio harness, use `vostok skill create --default <nome>`. Se o comando falhar (nome inválido ou skill já existente), **PARE** e responda com o template `blocker`.

### 4. Propor os subcomandos

Para cada operação determinística, procure um subcomando que já a execute com `vostok --help` e `vostok <grupo> --help`. Use os que existem no SKILL.md, com o comando exato.

Para cada operação sem subcomando, proponha ao usuário um subcomando novo do `vostok`, com o template `question`: o grupo, a ação, os argumentos, o que ele lê e grava, as mensagens de erro e os códigos de saída. **PARE** até o usuário decidir. A implementação do subcomando é feita no código do `vostok`, fora desta skill; até ela existir, o passo da skill descreve a operação para o agente executar.

Pule este passo se a skill não tiver operações determinísticas.

### 5. Preencher o SKILL.md

Substitua as variáveis do template:

| Variável | Conteúdo | Opcional |
|---|---|---|
| `#{SKILL_DESCRIPTION}` | Até 1024 caracteres, seguindo [create-skill-04]. Escape aspas duplas com `\"`. | Não |
| `#{SKILL_ALLOWED_TOOLS}` | Ferramentas liberadas, separadas por espaço. Ex.: `Read Edit Bash(vostok *)` | Sim |
| `#{SKILL_SCRIPTS}` | Subcomandos do `vostok` executados pela skill, separados por vírgula. Ex.: `vostok context load, vostok spec list` | Sim |
| `#{SKILL_TEMPLATES}` | Templates usados pela skill, relativos à raiz do harness. | Sim |
| `#{SKILL_TITLE}` | Nome da skill em português, como ação. Ex.: `Revisar código`. | Não |
| `#{SKILL_SUMMARY}` | Uma frase com o resultado da skill. | Não |
| `#{SKILL_TERMS}` | Lista `- **Termo:** definição.` | Sim |
| `#{SKILL_RULES}` | Uma regra por linha, no formato `[<nome>-NN]: regra.` | Sim |
| `#{SKILL_CHECKLIST}` | Uma linha `- [ ] N. Passo` para cada passo, começando por `- [ ] 1. Carregar o contexto`. | Não |
| `#{SKILL_STEPS}` | Uma seção `### N. Passo` para cada passo, a partir do `### 2.` (o passo 1, de carregar o contexto, já vem no template), com comandos exatos e condições **PARE**. | Não |
| `#{SKILL_RESPONSE_FORMATS}` | Só formatos próprios da skill, como uma tabela extra. Perguntas, conclusão e bloqueios usam `templates/responses/`. | Sim |

Para um campo opcional que não se aplica, remova a linha dele do front-matter. Para uma seção opcional que não se aplica, remova a seção inteira.

O passo 1 da skill criada já vem do template e carrega o contexto dela com `vostok context load --skill <nome>`. As regras e arquivos da skill são ligados no mapa `skills` do `config/context.yml`, pela `adjust-rules` ou à mão (RN-02); a criação da skill só acrescenta a entrada vazia.

### 6. Validar e finalizar

Execute:

```bash
vostok skill finalize <nome>
```

O comando valida a skill e lista todos os problemas encontrados: variáveis sem preencher, `name` diferente do nome da pasta, `description` vazia, longa demais ou com tags XML, SKILL.md com mais de 500 linhas e caminhos de `metadata` e da entrada da skill no mapa que não existem. Sem problemas, ele gera os redirecionamentos e atualiza o catálogo.

Corrija os problemas e execute de novo. Se falhar pela segunda vez, **PARE** e responda com o template `blocker`.

### 7. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** o caminho do SKILL.md e dos redirecionamentos gerados.
- **Pendências:** as decisões tomadas sem perguntar ([create-skill-07]) e os subcomandos propostos no passo 4 que ainda não existem no `vostok`.
