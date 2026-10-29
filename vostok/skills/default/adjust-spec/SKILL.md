---
name: adjust-spec
description: "Ajusta uma especificação (spec) já refinada, com status refined ou approved. Aplica um ou vários ajustes pedidos numa mesma mensagem, em prosa, em lista ou citando o trecho exato, registra edições feitas à mão e mantém o histórico de ajustes da spec, validando-a com as mesmas regras do refinamento. Use quando o usuário pedir para ajustar, corrigir, mudar, alterar, acrescentar ou remover algo de uma spec refinada ou aprovada, ou comentar a spec logo depois de ela ser refinada ou ajustada."
allowed-tools: Read Edit Bash(vostok *)
metadata:
  version: "1.2.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok spec list, vostok memory search, vostok spec adjust record-manual, vostok spec adjust validate, vostok spec adjust record"
  templates: "templates/spec/sections"
---

# Ajustar spec

Aplica à spec refinada certa todos os ajustes que o usuário pediu, deixando a spec válida e cada ajuste registrado no histórico.

## Termos

- **Refinada:** a spec em `refined/`, com status `refined` ou `approved`. É a única que esta skill edita.
- **Aprovada:** a refinada com status `approved`. Todo ajuste registrado nela derruba a aprovação e volta o status para `refined`.
- **Rascunho:** a spec original, em `draft/`. Nunca é editada por esta skill e deixa de existir quando a spec é aprovada.
- **Pedido:** a mensagem do usuário com um ou mais ajustes.
- **Ajuste:** uma mudança pedida, com um único alvo e uma única ação. Um pedido pode ter vários ajustes.
- **Alvo:** o ponto da refinada que o ajuste muda: uma seção, um ID (`RF-03`, `CB-02`) ou um trecho de texto.
- **Edição manual:** mudança feita à mão na refinada, fora desta skill. O comando a detecta pelo hash do conteúdo.
- **Histórico:** a seção "Histórico de ajustes" da refinada, escrita só pelo comando.
- **Inferência:** decisão tomada pelo agente sem perguntar ao usuário.

## Regras

[adjust-spec-01]: Só ajuste specs com status `refined` ou `approved`. Nunca edite o rascunho nem uma spec com status `planned`.
[adjust-spec-02]: Nunca edite uma spec sem ter certeza de que é a correta. Na dúvida, pergunte (passo 2).
[adjust-spec-03]: Nunca edite à mão o front-matter nem o "Histórico de ajustes". Só o comando os altera.
[adjust-spec-04]: Todo ajuste do pedido é aplicado ou vira pergunta. Nenhum é descartado sem aviso.
[adjust-spec-05]: No máximo 1 rodada de perguntas, sempre antes de qualquer edição.
[adjust-spec-06]: Não amplie o pedido. O que não foi pedido e for necessário para a spec continuar coerente é inferência e entra no "Registro de decisões".
[adjust-spec-07]: O tipo da spec não muda num ajuste. Se o pedido exige outro tipo, **PARE** e responda com o template `blocker`.
[adjust-spec-08]: Todos os ajustes de um pedido são registrados juntos, com um único `vostok spec adjust record`.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Identificar a spec
- [ ] 3. Registrar edições manuais
- [ ] 4. Decompor o pedido em ajustes
- [ ] 5. Analisar os ajustes
- [ ] 6. Rodada de perguntas (máx. 1)
- [ ] 7. Editar a refinada
- [ ] 8. Validar
- [ ] 9. Registrar o ajuste
- [ ] 10. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill adjust-spec
```

### 2. Identificar a spec

Use a spec sem perguntar em qualquer um destes casos:

- O usuário a cita por ID, título ou arquivo.
- O pedido vem logo depois de a spec ser refinada ou ajustada nesta conversa.
- Existe uma única spec refinada ou aprovada.

Para saber quais specs podem ser ajustadas, execute `vostok spec list refined` e `vostok spec list approved` e considere só as linhas com arquivo em `refined/`. O rascunho de uma spec refinada também aparece na lista, com o mesmo ID.

Nos demais casos:

1. Liste as specs refinadas e aprovadas como acima.
2. Nenhuma: **PARE** e informe que não há specs refinadas para ajustar.
3. Mais de uma: **PARE** e pergunte qual ajustar, com o template `question`, com uma opção por spec (ID e título). Aceite também resposta livre. Não edite nada antes da resposta.

Spec citada com status `draft`: **PARE** e informe o status atual. Só specs refinadas ou aprovadas são ajustadas.

Spec citada com status `planned`: **PARE** e informe que as tarefas dela já foram criadas e que mudá-la exige um novo ciclo, com uma nova spec.

### 3. Registrar edições manuais

Execute:

```bash
vostok spec adjust record-manual <SPEC_ID>
```

Se o comando registrar um ajuste manual e listar problemas de validação, corrija-os no passo 7, junto com os ajustes do pedido.

### 4. Decompor o pedido em ajustes

Leia a refinada inteira. Depois, separe o pedido em ajustes, qualquer que seja a forma:

| Forma do pedido | Como separar |
|---|---|
| Prosa | Cada verbo de mudança sobre um alvo diferente é um ajuste. "Troque X e remova Y" são dois. |
| Lista enumerada ou com marcadores | Cada item é um ajuste. Um item com dois alvos vira dois. |
| Citação exata (ID, seção, trecho entre aspas) | O alvo é o citado. Mude só ele. |
| Texto a substituir ("onde está A, coloque B") | O alvo é o trecho A. |
| Mistura das formas acima | Aplique cada regra à sua parte. |

O mesmo pedido repetido em formas diferentes (na prosa e na lista, por exemplo) é um único ajuste.

Para cada ajuste, anote o alvo e todas as seções e IDs afetados, incluindo os indiretos: um RF novo pede caso de teste e critério de aceite; um RF removido sai dos casos de teste e dos critérios de aceite.

### 5. Analisar os ajustes

Classifique cada ajuste:

| Situação | Ação |
|---|---|
| Claro, com alvo existente | Aplicar |
| Ambíguo: mais de uma interpretação válida | Pergunta |
| Contradiz outra parte da spec | Pergunta |
| Contradiz outro ajuste do mesmo pedido | Pergunta |
| Cita um alvo que não existe (ex.: `RF-40`) | Pergunta |
| Contradiz uma decisão ativa da memória (`vostok memory search decision <termos>`) | Pergunta, citando o ID da decisão |
| Exige outro tipo de spec | **PARE**: [adjust-spec-07] |

Sem perguntas, vá para o passo 7.

### 6. Rodada de perguntas

Envie numa única mensagem, com o template `question`, uma pergunta para cada ajuste classificado como pergunta, citando o ajuste e o trecho da spec. **PARE** e aguarde a resposta.

Não edite nada antes da resposta, nem os ajustes claros. Depois dela, aplique todos juntos. O que continuar sem resposta não é aplicado e aparece em "Pendências" da refinada.

### 7. Editar a refinada

Aplique os ajustes seguindo [sections.md](../refine-spec/references/sections.md): formato das tabelas, IDs sequenciais e rastreabilidade entre RF, casos de teste e critérios de aceite. Um ID removido não é reaproveitado.

Atualize também as seções fixas:

- **O que mudou:** continua comparando o rascunho com a versão atual da refinada. Acrescente ou ajuste as linhas dos assuntos afetados. Se o rascunho já foi removido (spec aprovada), acrescente uma linha por assunto alterado e não apague as existentes.
- **Registro de decisões:** uma linha por ajuste que decide algo, uma por resposta e uma por inferência. O motivo indica a origem: `ajuste N`, `ajuste N, resposta 1A` ou `ajuste N, inferência A`, em que N é o número que o ajuste terá no histórico.
- **Pendências:** perguntas sem resposta. Remova as pendências resolvidas pelo ajuste.

### 8. Validar

Execute:

```bash
vostok spec adjust validate <SPEC_ID>
```

O comando lista os problemas sem alterar nada. Corrija-os e execute de novo. Se falhar pela segunda vez, **PARE** e responda com o template `blocker`.

### 9. Registrar o ajuste

Execute, com um item por ajuste no resumo, separados por `; `:

```bash
vostok spec adjust record <SPEC_ID> "RF-03 aceita o título; CB-04 removido; nova RN-05"
```

O comando valida de novo, incrementa `adjustments`, atualiza as datas e o hash e acrescenta uma linha ao histórico. Numa spec aprovada, ele também derruba a aprovação e avisa na saída. Se ele recusar o ajuste, volte ao passo 8.

### 10. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** o caminho da refinada, o número do ajuste e a [tabela de ajustes](#tabela-de-ajustes).
- Se houve ajuste manual no passo 3, informe o número dele.
- Se o comando avisou que a aprovação foi derrubada, informe que a spec voltou para `refined` e precisa ser aprovada de novo.
- Acrescente a lista de inferências, se houver, com a letra e o que foi inferido.
- **Pendências:** os ajustes que ficaram sem resposta.

## Formatos de resposta

### Tabela de ajustes

Uma linha por ajuste identificado no pedido, na ordem em que aparecem.

```markdown
| # | Ajuste pedido | O que foi feito |
|---|---|---|
| 1 | Resumo do pedido, com o alvo. | Seções e IDs alterados. |
```
