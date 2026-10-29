---
name: adjust-rules
description: "Ajusta as regras do projeto, em rules/project/, e o mapa de carregamento do contexto, em config/context.yml. Aplica um ou vários ajustes pedidos numa mesma mensagem: criar, alterar ou remover uma regra, criar uma categoria de regras e incluir, mover ou retirar uma regra do mapa de uma skill ou do contexto obrigatório. Também grava a regra sugerida pelo agente depois que o usuário a aprova. Use quando o usuário pedir para criar, mudar, remover ou carregar uma regra ou categoria de regras do projeto, ou aprovar uma sugestão de regra."
allowed-tools: Read Edit Bash(vostok *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok rules next-id, vostok rules remove, vostok rules create-category, vostok rules load, vostok rules unload, vostok rules validate, vostok commit check"
  templates: "templates/rules/category.md templates/responses/question.md templates/responses/blocker.md templates/responses/completion.md"
---

# Ajustar regras

Aplica às regras do projeto e ao mapa de contexto todos os ajustes que o usuário pediu ou aprovou, sem reaproveitar o ID de nenhuma regra, e termina com o `vostok rules validate` sem erros.

## Termos

- **Categoria:** arquivo `vostok/rules/project/<categoria>.md`. O nome do arquivo, em kebab-case, é o nome da categoria.
- **Regra:** linha `[project/<categoria>-NN]: texto.` de uma categoria, com ID sequencial de dois dígitos.
- **Regra removida:** regra que vira `[project/<categoria>-NN]: Removida em AAAA-MM-DD.`. Ela continua no arquivo, e o ID não volta a ser usado.
- **Mapa:** o `vostok/config/context.yml`. O bloco `required` lista o que toda sessão carrega, e o bloco `skills` lista o que cada skill carrega, além de `required`.
- **Carregar:** registrar a categoria em `required` (`always`) ou na entrada de uma skill do mapa.
- **Pedido:** a mensagem do usuário com um ou mais ajustes.
- **Ajuste:** uma mudança pedida, com um único alvo e uma única ação. Um pedido pode ter vários ajustes.
- **Sugestão aprovada:** regra proposta pelo agente com o template `question` ([agent/rule-suggestions-02]) e aceita pelo usuário. Equivale a um pedido.
- **Inferência:** decisão tomada pelo agente sem perguntar ao usuário.

## Regras

[adjust-rules-01]: Só crie, altere ou remova uma regra, uma categoria ou uma entrada do mapa a pedido do usuário ou por sugestão aprovada. Nunca por iniciativa própria.
[adjust-rules-02]: O ID de uma regra nunca é reaproveitado. Para remover, use `vostok rules remove`; para o ID de uma regra nova, use `vostok rules next-id`. Nunca apague a linha de uma regra.
[adjust-rules-03]: Uma categoria pertence a um único arquivo, com o nome em kebab-case. Crie arquivos de categoria só com `vostok rules create-category`.
[adjust-rules-04]: Ligar ou desligar uma regra de uma skill é só editar o mapa (com `vostok rules load` e `vostok rules unload`). Nunca liste arquivos de contexto no SKILL.md.
[adjust-rules-05]: Todo ajuste do pedido é aplicado ou vira pergunta. Nenhum é descartado sem aviso.
[adjust-rules-06]: No máximo 1 rodada de perguntas, sempre antes de qualquer edição.
[adjust-rules-07]: Não amplie o pedido. O que não foi pedido e for necessário (registrar a categoria nova no mapa, por exemplo) é inferência e aparece na resposta.
[adjust-rules-08]: Termine sempre com `vostok rules validate` e corrija o que ele apontar antes de responder.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Decompor o pedido em ajustes
- [ ] 3. Analisar os ajustes
- [ ] 4. Rodada de perguntas (máx. 1)
- [ ] 5. Aplicar os ajustes
- [ ] 6. Validar
- [ ] 7. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill adjust-rules
```

### 2. Decompor o pedido em ajustes

Leia as categorias envolvidas em `vostok/rules/project/` e o `vostok/config/context.yml`. Separe o pedido em ajustes, de qualquer forma que ele venha (prosa, lista ou citação do ID da regra). Cada ajuste é um destes:

| Ajuste | Como aplicar |
|---|---|
| Criar regra | Acrescentar a linha ao fim da categoria, com o ID de `vostok rules next-id`. |
| Alterar regra | Editar o texto da linha, mantendo o ID. |
| Remover regra | `vostok rules remove`. |
| Criar categoria | `vostok rules create-category`, depois as regras dela. |
| Incluir ou mover a categoria no mapa | `vostok rules load` e, para mover, `vostok rules unload` do lugar antigo. |
| Retirar a categoria do mapa | `vostok rules unload`. |

Uma regra ou categoria sugerida pelo agente e aprovada pelo usuário ([agent/rule-suggestions-05]) entra aqui como um ajuste.

### 3. Analisar os ajustes

Classifique cada ajuste:

| Situação | Ação |
|---|---|
| Claro, com alvo existente | Aplicar |
| Ambíguo: mais de uma interpretação válida | Pergunta |
| Contradiz outra regra ou outro ajuste do mesmo pedido | Pergunta |
| Cita regra, categoria ou skill que não existe | Pergunta |
| Categoria nova sem dizer onde é carregada | Pergunta: em `required`, em quais skills ou em nenhuma |
| Altera regra já removida | Pergunta: o ID não volta, então a alteração vira uma regra nova |

Sem perguntas, vá para o passo 5.

### 4. Rodada de perguntas

Envie numa única mensagem, com o template `question`, uma pergunta para cada ajuste classificado como pergunta. **PARE** e aguarde a resposta.

Não edite nada antes da resposta, nem os ajustes claros. Depois dela, aplique todos juntos. O que continuar sem resposta não é aplicado e aparece em "Pendências".

### 5. Aplicar os ajustes

Aplique na ordem do pedido. Os comandos, a partir da raiz do projeto:

```bash
vostok rules next-id <categoria>
vostok rules remove <categoria> <NN>
vostok rules create-category <categoria> "<título>" "<propósito>"
vostok rules load <categoria> always|<skill>[,<skill>...]
vostok rules unload <categoria> always|<skill>[,<skill>...]
```

- `vostok rules next-id` imprime o próximo ID livre (`project/<categoria>-NN`), contando as regras removidas. Escreva a regra nova, numa linha, no fim do arquivo, com o formato `[project/<categoria>-NN]: regra.` ([adjust-rules-02]).
- `vostok rules remove` marca a regra como `Removida em AAAA-MM-DD.` com a data do dia. Remover a última regra de um arquivo também só a marca, e o próximo ID continua a sequência.
- `vostok rules create-category` cria o arquivo pelo template `templates/rules/category.md`, com o título e o propósito, sem regras. O propósito é uma frase só.
- `vostok rules load` e `vostok rules unload` editam o mapa: `always` é o bloco `required`, e cada skill é a entrada dela em `skills`. Mover uma regra de lugar é um `vostok rules unload` e um `vostok rules load`. `vostok rules load` de algo já carregado não duplica, e `vostok rules unload` do que não está carregado recusa.

Se um comando recusar, **PARE** e responda com o template `blocker`, com a mensagem do comando.

### 6. Validar

Execute:

```bash
vostok rules validate
```

Se ele apontar problemas, corrija cada um (arquivo e linha vêm na mensagem) e execute de novo, até terminar sem erros ([adjust-rules-08]). Se falhar pela terceira vez, **PARE** e responda com o template `blocker`.

### 7. Responder ao usuário

Execute `vostok commit check` e responda com o template `completion`:

- **O que foi feito:** os ajustes aplicados, um por linha, com o ID das regras e a categoria, e as mudanças no mapa.
- **Verificação:** o resultado do `vostok rules validate`.
- **Pendências:** os ajustes sem resposta e as inferências ([adjust-rules-07]).

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

### Lista de ajustes

```markdown
| Ajuste | Alvo | Resultado |
|---|---|---|
| Remover regra | project/language-05 | Marcada como removida em 2026-10-11 |
```
