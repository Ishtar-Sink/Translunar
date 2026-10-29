---
name: report-harness-bug
description: "Relata um defeito do próprio harness Vostok (CLI vostok, skills, regras, templates e configuração distribuídos), nunca do projeto do usuário: monta o relato a partir do template em work/bugs/, troca dados do projeto por exemplos neutros, mascara segredos, valida com vostok bug check, mostra o relato inteiro e, só com a autorização do usuário, cria a issue no repositório do harness com gh ou entrega o link preenchido para abrir no navegador. Use quando o usuário pedir para reportar, relatar ou abrir uma issue de um bug do harness ou do vostok, como 'reporta esse bug do harness' ou /report-harness-bug. Não use para defeitos do código, das regras ou das skills customizadas do projeto do usuário."
allowed-tools: Read Write Edit Bash(vostok *) Bash(gh *) Bash(curl *) Bash(uname *) Bash(date *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "vostok context load, vostok --version, vostok bug check, vostok bug link, gh auth status, gh issue create, curl"
  templates: "templates/bug/report.md templates/responses/question.md templates/responses/blocker.md templates/responses/completion.md"
---

# Relatar defeito do harness

Transforma um defeito do próprio harness Vostok, encontrado no uso, num relato estruturado e neutro e, com a autorização do usuário, numa issue do repositório do harness.

## Termos

- **Harness:** o que o Vostok distribui: a CLI `vostok`, as skills padrão (`skills/default/`), as regras do agente (`rules/agent/`), os templates e a configuração. As regras em `rules/project/`, as skills em `skills/custom/` e o código do projeto são do usuário, não do harness.
- **Relato:** o arquivo `vostok/work/bugs/<AAAA-MM-DD>-<slug>.md`, criado a partir de `templates/bug/report.md`, com front-matter (`issue`, `title`, `created_at`) e as seções Versão, Comportamento atual, Comportamento esperado, Como reproduzir, Causa provável e O que já foi tentado.
- **Repositório do harness:** o valor de `harness.repository` em `vostok/config/main.yml` (por exemplo, `Ishtar-Sink/Vostok`).
- **Neutralizar:** trocar dados do projeto do usuário (caminhos, nomes, trechos de código, saídas, IDs e títulos de specs) por exemplos neutros que reproduzem o mesmo defeito, e mascarar segredos com `***`.
- **Autorização:** a resposta do usuário, numa mensagem dele, liberando o envio da versão do relato que acabou de ver.
- **Corpo:** o relato sem o front-matter e sem os comentários `<!-- -->`. É o texto que vai para a issue.

## Regras

[report-harness-bug-01]: Relate só defeitos do harness. Defeito do projeto do usuário (código, regras de `rules/project/`, skills de `skills/custom/`, ferramentas de terceiros): **PARE**, explique que a skill trata só do harness Vostok e não crie relato.
[report-harness-bug-02]: O relato leva só dados do harness. Antes de mostrá-lo, troque caminhos, nomes, trechos de código e saídas do projeto por exemplos neutros (`/caminho/do/projeto`, `src/exemplo.rs`, `SPEC-001`, `minha-feature`), troque o diretório pessoal por `~` e mascare segredos, tokens, senhas, e-mails, IPs e nomes de máquinas com `***`. Nunca leia `.env`, chaves ou credenciais para montar o relato.
[report-harness-bug-03]: Nada vai para o GitHub sem autorização: mostre o relato inteiro e **PARE** até o usuário autorizar. A autorização vale só para a versão mostrada; qualquer mudança no relato exige mostrar de novo e pedir de novo.
[report-harness-bug-04]: Esta skill só cria a issue do relato. Nunca comente, edite, rotule nem feche issues por ela.
[report-harness-bug-05]: O relato fica em `vostok/work/bugs/` mesmo se o usuário recusar o envio; nesse caso nada é publicado.
[report-harness-bug-06]: O `vostok bug check` confere a forma do relato, não o conteúdo. Ele não substitui a neutralização nem a revisão do usuário.
[report-harness-bug-07]: Use o `gh` só quando `gh auth status` terminar com sucesso. `gh` ausente ou sem autenticação segue pelo link do `vostok bug link`.
[report-harness-bug-08]: Não faça commit nem stage do relato ([agent/boundaries-01], [agent/boundaries-02]).

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Confirmar que o defeito é do harness
- [ ] 3. Montar o relato
- [ ] 4. Validar o relato
- [ ] 5. Pedir a autorização
- [ ] 6. Criar a issue
- [ ] 7. Gravar o número da issue
- [ ] 8. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill report-harness-bug
```

### 2. Confirmar que o defeito é do harness

Reúna o que se sabe do defeito: o comando ou a skill usada, o que aconteceu, o que era esperado e a mensagem de erro. Confira onde ele nasce:

| Origem | É do harness? |
|---|---|
| Saída ou comportamento da CLI `vostok` | Sim |
| Skill de `skills/default/`, regra de `rules/agent/`, template ou configuração distribuída | Sim |
| Regra de `rules/project/` ou skill de `skills/custom/` do usuário | Não |
| Código, testes, dependências ou ferramentas do projeto | Não |

Defeito do projeto: **PARE** e responda que a skill trata só de defeitos do harness Vostok, dizendo por que este não é ([report-harness-bug-01]). Na dúvida, pergunte com o template `question` antes de montar o relato.

### 3. Montar o relato

1. Leia `harness.repository` em `vostok/config/main.yml`.
2. Colete a versão e o sistema operacional:

   ```bash
   vostok --version
   uname -sr
   date -u +%Y-%m-%dT%H:%M:%SZ
   ```

3. Copie `vostok/templates/bug/report.md` para `vostok/work/bugs/<AAAA-MM-DD>-<slug>.md`, com a data de hoje e um slug curto em kebab-case do resumo (por exemplo, `2026-10-17-task-tests-ignora-codigo-de-saida.md`). Crie a pasta se não existir.
4. Preencha o relato, sem deixar variável de template:

   | Campo | Conteúdo |
   |---|---|
   | `title` | `[harness-bug] ` seguido de um resumo curto do defeito. |
   | `created_at` | A data e hora UTC coletadas. |
   | `issue` | Fica `null` até a issue existir. |
   | Versão | Saída de `vostok --version` e de `uname -sr`, e a ferramenta do agente quando importar. |
   | Comportamento atual | O comando ou a skill usada e o que aconteceu, com a mensagem de erro do harness. |
   | Comportamento esperado | O que deveria acontecer. |
   | Como reproduzir | Passos numerados, num projeto de exemplo, do zero até o defeito. |
   | Causa provável | Onde o defeito parece nascer no harness (comando, skill, regra ou template), ou "Não identificada". |
   | O que já foi tentado | Contornos e tentativas, com o resultado de cada um, ou "Nada". |

5. Neutralize o relato inteiro ([report-harness-bug-02]): releia cada seção e troque todo dado do projeto. Mantenha só o que o harness produziu ou recebeu, reduzido ao mínimo que reproduz o defeito.

### 4. Validar o relato

Execute:

```bash
vostok bug check vostok/work/bugs/<arquivo>.md
```

Com problemas (código 1), corrija cada linha listada e execute de novo, até o comando aceitar o relato.

### 5. Pedir a autorização

Mostre o relato inteiro, como está no arquivo, e o repositório de destino. **PARE** e pergunte com o template `question` ([report-harness-bug-03]):

| Opção | Descrição |
|---|---|
| A | Enviar o relato como está para `<harness.repository>`. |
| B | Ajustar o relato antes (diga o que mudar). |
| C | Não enviar; o relato fica só em `vostok/work/bugs/`. |

- **A:** siga para o passo 6.
- **B:** aplique as mudanças, neutralize de novo, volte ao passo 4 e mostre o relato outra vez.
- **C:** não publique nada ([report-harness-bug-05]) e vá para o passo 8.

### 6. Criar a issue

Execute:

```bash
gh auth status
```

**Com `gh` autenticado:** grave o corpo (o relato sem o front-matter e sem os comentários) num arquivo temporário fora do projeto, como `/tmp/harness-bug-<slug>.md`, e execute:

```bash
gh issue create --repo <harness.repository> --title "<title do front-matter>" --body-file /tmp/harness-bug-<slug>.md
```

O comando imprime o endereço da issue (`https://github.com/<repositório>/issues/<N>`); o número é o `<N>` do fim.

**Sem `gh` ou sem autenticação:** execute:

```bash
vostok bug link vostok/work/bugs/<arquivo>.md
```

Mostre o link ao usuário para ele abrir no navegador e criar a issue. Se o comando avisar que o relato passa do limite do link, o link traz só o título: mostre também o corpo, para o usuário colar na issue. **PARE** e peça o número da issue criada. Com o número, confira a issue pela API pública (veja "Ler uma issue sem gh") e verifique se o título começa com `[harness-bug]`.

### 7. Gravar o número da issue

Troque `issue: null` pelo número no front-matter do relato (por exemplo, `issue: 42`). O usuário não informou o número: deixe `null` e registre a pendência na resposta.

### 8. Responder ao usuário

Responda com o template `completion`:

- **O que foi feito:** o caminho do relato e, quando houver, o número e o endereço da issue (`https://github.com/<harness.repository>/issues/<N>`). Na recusa, diga que nada foi publicado.
- **Verificação:** o resultado do `vostok bug check` e do envio (`gh issue create` ou link entregue).
- **Pendências:** o número da issue, quando o usuário ainda não o informou.

## Ler uma issue sem gh

Sem `gh`, leia uma issue e os comentários dela pela API pública do GitHub, sem autenticação (limite de 60 requisições por hora):

```bash
curl -s https://api.github.com/repos/<harness.repository>/issues/<N>
curl -s https://api.github.com/repos/<harness.repository>/issues/<N>/comments
```

O primeiro traz `title`, `state`, `body` e `html_url`; o segundo, a lista de comentários com `body` e `user.login`. Uma resposta com `"message": "Not Found"` indica que a issue não existe. Para comentar sem `gh`, entregue ao usuário o texto e o link `html_url` da issue, para ele comentar à mão.

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. O relato é mostrado no passo 5 como está no arquivo, dentro de um bloco `markdown`, seguido da pergunta do template `question`.
