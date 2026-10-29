# Respostas

Define o formato das respostas do agente ao usuário.

[agent/responses-01]: Toda resposta ao usuário segue um template de `templates/responses/`, escolhido pela `description` do template.
[agent/responses-02]: Não crie formatos de resposta. Se nenhum template específico se aplica, use `general`.
[agent/responses-03]: Siga o `usage` do template. Partes opcionais que não se aplicam são omitidas inteiras, inclusive o título da seção. Nenhuma variável `#{...}` fica na resposta.
[agent/responses-04]: Uma skill pode acrescentar conteúdo próprio a um template, como uma tabela extra, mas não muda a estrutura dele.
