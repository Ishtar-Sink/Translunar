# Memória

Define quando o agente consulta e registra a memória do projeto: decisões, issues e conhecimentos.
As operações são os subcomandos de `vostok memory`.

[agent/memory-01]: Nunca carregue um arquivo de memória inteiro. Consulte com `vostok memory search <tipo|all> [termos]`. Sem termos, o comando lista o índice. Com termos, ele devolve as entradas com qualquer um deles, das mais relevantes para as menos. Passe cada termo como um argumento, incluindo sinônimos (ex.: `mongodb banco dados`).
[agent/memory-02]: Antes de decidir algo que afete arquitetura, stack, dados, contratos ou convenções, ou quando houver ambiguidade sobre o projeto, busque em `decision` com os termos do assunto.
[agent/memory-03]: Se uma ação conflita com uma decisão com status `ativa`, pare antes de executá-la e responda com o template `decision-conflict`.
[agent/memory-04]: Ao resolver um erro que exigiu investigação, registre uma issue com `vostok memory add issue "Título"` e preencha a entrada. A Assinatura é um trecho estável e literal da mensagem de erro, sem caminhos ou valores que mudam a cada execução.
[agent/memory-05]: Antes de pesquisar ou investigar um assunto pouco documentado, busque em `knowledge`. Ao descobrir algo que não está na documentação primária, registre com `vostok memory add knowledge "Título"`.
[agent/memory-06]: Uma decisão só é registrada depois de o usuário confirmar a proposta feita com o template `decision-proposal`. Ao substituir uma decisão, registre a nova com o campo Substitui preenchido e marque a antiga com `vostok memory update <ID> Status substituída`.
[agent/memory-07]: Issues e conhecimentos são registrados sem pedir confirmação e aparecem na seção Memória da resposta `completion`.
[agent/memory-08]: Não registre o que já está no código, no histórico do git, nas specs ou na documentação do projeto.
[agent/memory-09]: Altere campos de entradas existentes só com `vostok memory update`. Nunca edite o Status à mão.
