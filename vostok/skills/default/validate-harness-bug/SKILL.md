---
name: validate-harness-bug
description: "Valida a correção de um defeito do próprio harness Vostok (CLI vostok, skills, regras, templates e configuração distribuídos), não do projeto do usuário: encontra as issues [harness-bug] do usuário respondidas com a correção, reinstala a versão citada, roda vostok update, segue os passos de retomada da resposta, confere se o defeito relatado deixou de acontecer e, com autorização, comenta o resultado e fecha a issue. Use quando o usuário pedir /validate-harness-bug, \"valida a correção do bug do harness\", ou disser que a issue #N foi respondida. Não use para defeitos do projeto do usuário."
allowed-tools: Read Glob Grep Bash
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok update"
  templates: "templates/responses/question.md templates/responses/blocker.md templates/responses/completion.md"
---

# Validar correção de defeito do harness

Aplica no projeto do usuário a correção respondida numa issue de defeito do harness, confere se o defeito sumiu e, com autorização, registra o resultado na issue.

## Termos

- **Repositório do harness:** o valor de `harness.repository` em `vostok/config/main.yml` (por padrão, `Ishtar-Sink/Vostok`). Todas as issues são lidas e escritas nele.
- **Issue de defeito:** issue do repositório do harness com o título prefixado por `[harness-bug]`, aberta pela skill `report-harness-bug` ou à mão.
- **Resposta da correção:** comentário da issue que contém o marcador `<!-- vostok:fix -->`, com a versão que corrige o defeito e os passos (reinstalar, `vostok update`, retomar o que travou). Havendo mais de uma, vale a mais recente.
- **Versão citada:** a versão `X.Y.Z` da resposta da correção. A release correspondente tem a tag `vX.Y.Z` no repositório do harness.
- **Defeito relatado:** o comportamento descrito no corpo da issue, nas seções "Comportamento atual" e "Como reproduzir".
- **Comentário de validação:** o texto que esta skill propõe publicar na issue, com o que foi feito, a versão instalada e o resultado.
- **Com `gh`:** o `gh` está instalado e `gh auth status` termina com código 0. Instalado sem autenticação conta como sem `gh`.

## Regras

[validate-harness-bug-01]: Só trate de defeitos do próprio harness Vostok. Se o pedido for sobre um defeito do projeto do usuário, explique que a skill não se aplica e encerre.
[validate-harness-bug-02]: Nunca escreva no GitHub (comentar, fechar, reabrir) sem a autorização explícita do usuário, dada numa mensagem dele depois de ver o texto exato do comentário (RN-01).
[validate-harness-bug-03]: Siga só respostas com o marcador `<!-- vostok:fix -->` numa issue com `[harness-bug]` no título. Sem prefixo ou sem marcador, avise e pare.
[validate-harness-bug-04]: Só reinstale uma versão citada que já esteja publicada como release e seja mais nova que a instalada. Caso contrário, pare e informe.
[validate-harness-bug-05]: Os passos da resposta são executados como estão. Se um passo pedir algo fora do harness (apagar arquivos do projeto, mudar código do usuário, comandos com `sudo`), pare e pergunte antes de executá-lo.
[validate-harness-bug-06]: Decisões que os passos da resposta exigem, como aceitar uma regressão no `vostok task resume`, são do usuário. Siga as regras da skill envolvida (por exemplo, [finish-task-03]) e nunca decida por ele.
[validate-harness-bug-07]: O resultado é "corrigido" só se o defeito relatado deixou de acontecer, reproduzido pelos mesmos passos do relato. Na dúvida, o resultado é "não corrigido" ou "não conferido", nunca "corrigido".
[validate-harness-bug-08]: O comentário de validação não leva dados do projeto do usuário (caminhos, nomes, trechos de código, saídas) nem segredos. Troque por exemplos neutros, como no relato.
[validate-harness-bug-09]: Não faça commit nem stage ([agent/boundaries-01], [agent/boundaries-02]).

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Verificar o acesso ao GitHub
- [ ] 3. Encontrar a issue respondida
- [ ] 4. Conferir a versão citada
- [ ] 5. Aplicar a correção
- [ ] 6. Conferir o defeito
- [ ] 7. Montar o comentário de validação
- [ ] 8. Publicar o resultado
- [ ] 9. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill validate-harness-bug
```

### 2. Verificar o acesso ao GitHub

Leia `harness.repository` em `vostok/config/main.yml`; nos comandos abaixo, `<repo>` é esse valor. Execute:

```bash
gh auth status
```

Código 0: siga **com `gh`**. Comando inexistente ou código diferente de 0: siga **sem `gh`**, lendo pela API pública com `curl`.

### 3. Encontrar a issue respondida

**Issue citada pelo usuário** (número ou link): leia só ela, como abaixo, conforme o acesso.

**Com `gh`, sem issue citada:** liste as issues abertas do usuário:

```bash
gh issue list --repo <repo> --author @me --search "[harness-bug] in:title" --state open
```

Para cada uma, leia corpo e comentários e mantenha só as que têm a resposta da correção:

```bash
gh issue view <N> --repo <repo> --json title,state,body,url,comments
```

Use o `--json`: fora de um terminal, `gh issue view --comments` imprime só os comentários e sai vazio numa issue sem comentários.

**Sem `gh`:** **PARE** e peça ao usuário o número da issue, com o template `question`. Com o número, leia corpo e comentários pela API pública:

```bash
curl -s https://api.github.com/repos/<repo>/issues/<N>
curl -s https://api.github.com/repos/<repo>/issues/<N>/comments
```

Use `title`, `state` e `body` da issue e o `body` de cada comentário. A API pública tem limite de 60 requisições por hora: leia uma issue por vez.

Depois da leitura:

1. Nenhuma issue respondida (CB-08): **PARE** e informe que não há issues de defeito do harness respondidas para validar. Encerre.
2. Issue inexistente, sem `[harness-bug]` no título ou sem a resposta da correção (CB-06): **PARE** e avise o motivo, com o link `https://github.com/<repo>/issues/<N>`. Não aplique nada.
3. Issue fechada: **PARE** e informe que ela já foi encerrada.
4. Mais de uma issue respondida: **PARE** e pergunte qual validar, com o template `question`, uma opção por issue (número e título). Valide uma issue por vez.

Da issue escolhida, guarde o defeito relatado e, da resposta da correção, a versão citada e os passos.

### 4. Conferir a versão citada

Execute:

```bash
vostok --version
```

Confira se a release da versão citada está publicada. Com `gh`:

```bash
gh release view v<X.Y.Z> --repo <repo>
```

Sem `gh`, o código HTTP deve ser 200:

```bash
curl -s -o /dev/null -w '%{http_code}' https://api.github.com/repos/<repo>/releases/tags/v<X.Y.Z>
```

- Release não publicada (CB-09): **PARE** e informe que a versão `X.Y.Z` ainda não está disponível; peça para validar depois da release.
- Versão instalada igual ou mais nova que a citada: não reinstale; siga para o passo 5 a partir do `vostok update`.
- Versão instalada mais antiga: siga para o passo 5.

### 5. Aplicar a correção

Siga os passos da resposta da correção, na ordem, conforme [validate-harness-bug-05] e [validate-harness-bug-06]:

1. **Reinstalar.** Use o comando de reinstalação da resposta. Sem comando, use o instalador das releases, o script de instalação na raiz de `https://github.com/<repo>` (branch `main`), executado com `sh` e a opção `--version <X.Y.Z>`; ele baixa o binário da release, confere o checksum e instala em `~/.local/bin`.

   Se o `vostok` instalado vier do `cargo install` (`command -v vostok` aponta para `~/.cargo/bin`), **PARE** e pergunte, com o template `question`, entre instalar pelo instalador das releases ou reinstalar pelo `cargo install` a partir do código da versão citada. Depois, confira que `vostok --version` mostra `X.Y.Z`; se não mostrar (por exemplo, outra instalação vem antes no `PATH`), **PARE** e responda com o template `blocker`.

2. **Atualizar o harness do projeto.** Na raiz do projeto, execute:

   ```bash
   vostok update
   ```

3. **Retomar o que travou.** Execute os passos de retomada da resposta (por exemplo, `vostok task resume <SPEC_ID> <TASK_ID> --accept-regression <N> "decisão"` seguido da skill `finish-task`). Um passo que exige decisão do usuário: **PARE** e pergunte com o template `question`.

Um passo que falhe: guarde o comando e a saída, não improvise uma correção e siga para o passo 7 com o resultado "não corrigido".

### 6. Conferir o defeito

Reproduza o defeito relatado com os mesmos passos de "Como reproduzir" da issue, adaptados ao projeto, e compare com "Comportamento esperado". Classifique conforme [validate-harness-bug-07]:

- **Corrigido:** o comportamento esperado acontece.
- **Não corrigido:** o comportamento atual do relato se repete, ou outro defeito do harness aparece no mesmo fluxo.
- **Não conferido:** não foi possível reproduzir o cenário (por exemplo, depende de um estado que o projeto não tem mais). Explique o motivo.

### 7. Montar o comentário de validação

Monte o comentário no formato da seção "Formatos de resposta", conforme [validate-harness-bug-08]. **PARE** e mostre ao usuário o texto inteiro, o link `https://github.com/<repo>/issues/<N>` e o que será feito:

- Corrigido: comentar e fechar a issue.
- Não corrigido ou não conferido: comentar e manter a issue aberta (FA-04).

Peça a autorização explícita. Se o usuário pedir mudanças no texto, ajuste e mostre de novo. Se ele recusar, não publique nada e siga para o passo 9.

### 8. Publicar o resultado

Só com a autorização do passo 7 ([validate-harness-bug-02]).

**Com `gh`:** grave o texto num arquivo temporário fora do projeto e execute:

```bash
gh issue comment <N> --repo <repo> --body-file <arquivo>
```

Se o resultado for "corrigido", feche a issue:

```bash
gh issue close <N> --repo <repo>
```

Se o comando falhar, **PARE** e responda com o template `blocker`, com a mensagem do comando.

**Sem `gh` (FA-05):** não publique. Entregue ao usuário o texto do comentário e o link `https://github.com/<repo>/issues/<N>`, para ele comentar e, se o resultado for "corrigido", fechar a issue à mão.

### 9. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** a issue validada (número e link), a versão instalada, os passos aplicados e o resultado (corrigido, não corrigido ou não conferido).
- **Verificação:** os comandos executados, a reprodução do defeito e o que foi publicado na issue (comentário, fechamento) ou entregue para publicação à mão.
- **Pendências:** a issue que ficou aberta e o motivo, ou o comentário recusado pelo usuário.

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

### Comentário de validação

```markdown
Validação da correção (versão X.Y.Z).

**Resultado:** corrigido | não corrigido | não conferido

**O que foi feito:**
1. Reinstalado o vostok X.Y.Z.
2. `vostok update` no projeto.
3. Passos de retomada da resposta, com o resultado de cada um.

**Conferência:** os passos de "Como reproduzir" e o comportamento observado, com exemplos neutros.
```

No resultado "não corrigido" ou "não conferido", acrescente o comando que falhou ou o motivo, com a saída relevante neutralizada.
