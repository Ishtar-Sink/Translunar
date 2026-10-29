# Seções da spec refinada

Como preencher cada seção. As seções de cada tipo e a ordem delas estão em `config/specs.yml` (`sections_<tipo>`). O formato das tabelas já vem no template da seção. Substitua só as variáveis `#{...}`.

## Conteúdo

- Tipos de spec
- Regras gerais
- Seções de todos os tipos
- Seções de implementação (feature, improvement, fix)
- Seções de estudo (study)
- Seções de análise (analysis)
- Seções fixas

## Tipos de spec

| Tipo | Quando usar |
|---|---|
| `feature` | Algo novo será construído. |
| `improvement` | Algo que já existe será melhorado ou estendido. |
| `fix` | Um comportamento está errado e será corrigido. |
| `study` | É preciso investigar para responder perguntas, sem entregar código. |
| `analysis` | Um problema ou uma teoria será analisado para chegar a uma conclusão fundamentada. |

## Regras gerais

- Cada linha de tabela descreve um único item. Evite "e" que junte dois requisitos na mesma linha.
- IDs são sequenciais por tipo, com dois dígitos: `RF-01`, `RNF-01`, `RN-01`, `CB-01`, `CT-01`, `CA-01`, `PQ-01`, `T-01`, `A-01`, `S-01`.
- Seção de tabela que não se aplica recebe uma única linha com `-` em todas as colunas. O script recusa tabelas vazias.
- Caminhos de arquivo são relativos à raiz do projeto e ficam entre crases.
- Tudo o que não veio do rascunho nem das respostas do usuário é inferência ([refine-spec-04]).

## Seções de todos os tipos

| Seção | Conteúdo |
|---|---|
| Objetivo | 1 a 3 frases: o problema e o resultado esperado. |
| Escopo | "Dentro do escopo" e "Fora do escopo", em listas. O que ficar fora é dito explicitamente, para evitar trabalho a mais. |
| Premissas e dependências | Lista do que é assumido como verdadeiro e do que precisa existir antes. |
| Riscos | Uma linha por risco, com impacto (`alto`, `médio`, `baixo`) e mitigação. |
| Critérios de aceite | Checklist `- [ ] CA-01: critério verificável (RF-01, RF-02)`. Cada critério cita os requisitos que comprova. Nos tipos sem requisitos, cita os IDs da seção principal (`PQ-01`, `S-01`). |
| Referências | Tudo o que foi consultado no passo 3: `arquivo`, `memória` (ID da entrada) ou `documentação`, e para que foi usado. |

## Seções de implementação (feature, improvement, fix)

| Seção | Conteúdo |
|---|---|
| Estado atual | Só em `improvement`. Como funciona hoje, citando os arquivos envolvidos. |
| Defeito | Só em `fix`. Comportamento atual, comportamento esperado, passos para reproduzir e causa raiz (ou "desconhecida"). |
| Requisitos funcionais | O que o sistema deve fazer, com `RF-01`. Cada requisito começa com "O sistema deve" ou com o nome do componente. |
| Requisitos não funcionais | Desempenho, compatibilidade, segurança, portabilidade, com `RNF-01` e como verificar. |
| Regras de negócio | Restrições e invariantes que valem sempre, com `RN-01`. |
| Fluxos | Fluxo principal em passos numerados. Fluxos alternativos como `FA-01`, cada um com o passo em que se desvia. |
| Casos de borda | Situações fora do fluxo principal, com `CB-01`, o comportamento esperado e os requisitos relacionados. |
| Contratos e interfaces | Assinaturas exatas em blocos de código: comandos e argumentos, formatos de arquivo, campos de front-matter e configuração. |
| Componentes afetados | Um caminho por linha, com a ação `criar`, `alterar` ou `remover` e o motivo. O script confere que `alterar` e `remover` apontam para caminhos existentes, e que `criar` aponta para um caminho que ainda não existe. |
| Casos de teste | Com `CT-01`: cenário, passos, resultado esperado e requisitos cobertos. Todo `RF` aparece em ao menos um caso de teste. |

## Seções de estudo (study)

| Seção | Conteúdo |
|---|---|
| Perguntas da investigação | Com `PQ-01`: a pergunta e como ela será respondida (fonte, experimento, medição). |

## Seções de análise (analysis)

A análise segue tese, antítese e síntese. O objetivo é chegar a uma conclusão depois de confrontar as duas posições, e não só defender a primeira.

| Seção | Conteúdo |
|---|---|
| Tese | A posição ou hipótese inicial, em 1 a 3 frases, e os argumentos a favor dela (`T-01`), cada um com a evidência. |
| Antítese | A posição contrária, e os contra-argumentos (`A-01`), cada um com a evidência e o `T` que contesta. |
| Síntese | A conclusão que resolve o confronto, em 1 a 3 frases, e as conclusões (`S-01`), cada uma com os `T` e `A` em que se baseia. O script confere que todo `T` e todo `A` aparecem em alguma conclusão. |

## Seções fixas

| Seção | Conteúdo |
|---|---|
| Resumo (logo abaixo do título) | 1 ou 2 frases com o que a spec entrega. |
| O que mudou | Uma linha por assunto alterado em relação ao rascunho. |
| Registro de decisões | Uma linha por resposta do usuário e uma por inferência. O motivo indica a origem: `resposta 1B` ou `inferência A`. |
| Pendências | Uma linha por ambiguidade não resolvida, ou uma linha com `-` e `Nenhuma`. |
| Histórico de ajustes | Não preencha. O script da skill `adjust-spec` acrescenta uma linha a cada ajuste. |
