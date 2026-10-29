---
name: translate-subtitles
description: "Traduz e localiza a legenda pt-BR de um corte do Translunar para os idiomas escolhidos: recebe o caminho do pt.srt no server, pergunta os idiomas, lê perfis, glossário e contexto, grava um {idioma}.srt sincronizado ao lado do pt.srt e só termina com a validação do legendar aprovada. Use quando o usuário colar um caminho de pt.srt do Translunar ou pedir para traduzir/legendar um corte."
allowed-tools: Read Write Bash(ssh *) Bash(scp *)
metadata:
  version: "1.0.0"
  author: "Victor Batalha"
  scripts: "ssh -T server, scp, legendar validar"
  templates: "templates/responses/question.md templates/responses/completion.md templates/responses/blocker.md"
---

# Traduzir legendas

Localiza a legenda pt-BR de um corte para os idiomas escolhidos, grava cada `<idioma>.srt` ao lado do `pt.srt` no server e só termina com a validação do `legendar` aprovada em cada idioma.

## Termos

- **Server:** o MacBook dedicado, acessado por `ssh -T server` e `scp`. Nunca rode comandos de tradução localmente.
- **Corte:** pasta `~/translunar-dados/saida/<corte>/` (em caminho absoluto, `/Users/server/translunar-dados/saida/<corte>/`), com `pt.srt` e `estado.json`.
- **Projeto:** `~/apps/translunar` no server. Chega por rsync, não é um clone git. A CLI é `~/apps/translunar/.venv/bin/legendar`.
- **Perfil:** `~/apps/translunar/config/idiomas/<codigo>.yaml`, com variante, público, registro e regras do idioma.
- **Glossário:** `~/apps/translunar/config/glossario.yaml`, com termos de tradução fixa.
- **Contexto:** `~/translunar-dados/entrada/<nome do vídeo sem extensão>.contexto.md`, opcional.
- **Rodada:** uma passada de escrita e validação de um idioma.

## Regras

[translate-subtitles-01]: Mantenha exatamente os ids e os timestamps do `pt.srt`. Cada bloco da tradução tem o mesmo id e o mesmo timestamp do bloco de origem; só o texto muda.
[translate-subtitles-02]: Localize, não traduza ao pé da letra. Adapte expressões, humor e referências ao público do idioma; mantenha números e nomes.
[translate-subtitles-03]: Siga a variante, o público, o registro e as regras do perfil do idioma.
[translate-subtitles-04]: Aplique o glossário sempre. Termo com `traducoes` vazio nunca é traduzido: mantenha-o como está no original.
[translate-subtitles-05]: Respeite 2 linhas por legenda, 32 caracteres por linha e 17 caracteres por segundo. O máximo de caracteres de cada legenda é `floor(17 × segundos)`, com os segundos tirados do timestamp. Escreva já dentro do limite.
[translate-subtitles-06]: Nada de explicações, notas ou comentários dentro do `.srt`.
[translate-subtitles-07]: Grave sempre de forma atômica: `scp` para um temporário oculto e `mv` no server.
[translate-subtitles-08]: Nunca edite nem apague o `pt.srt`.
[translate-subtitles-09]: No máximo 3 rodadas de validação por idioma. Depois, pare e mostre os problemas restantes ao usuário.
[translate-subtitles-10]: Só declare um idioma pronto com o `legendar validar` aprovado (código de saída 0).
[translate-subtitles-11]: Use um comando `ssh -T server` por operação e sempre com o caminho absoluto ou `~` entre aspas simples, para o shell local não expandir.

## Checklist

Copie e marque o progresso:

```
- [ ] 1. Carregar o contexto
- [ ] 2. Conferir o caminho
- [ ] 3. Perguntar os idiomas
- [ ] 4. Ler o material
- [ ] 5. Localizar
- [ ] 6. Gravar de forma atômica
- [ ] 7. Validar
- [ ] 8. Responder ao usuário
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill translate-subtitles
```

### 2. Conferir o caminho

Aceite só um caminho absoluto terminado em `/pt.srt`, dentro de `~/translunar-dados/saida/<corte>/` (ou `/Users/server/translunar-dados/saida/<corte>/`). Guarde a pasta do corte como `<pasta>`.

```bash
ssh -T server 'test -f <caminho>' && echo existe || echo ausente
```

**PARE** se o caminho não tiver esse formato ou o arquivo não existir, e responda com o template `blocker`.

### 3. Perguntar os idiomas

Liste os perfis:

```bash
ssh -T server 'ls ~/apps/translunar/config/idiomas'
```

Pergunte com o template `question`, com as opções: A) todos os perfis (cite os códigos), B) um subconjunto (peça os códigos), C) outro idioma (peça o código). **PARE** até o usuário responder.

Idioma sem arquivo em `config/idiomas/` é recusado. Responda com o template `blocker`, sugerindo criar `config/idiomas/<codigo>.yaml` (um idioma novo é só um perfil novo, sem código), e siga com os demais idiomas.

### 4. Ler o material

Leia tudo pelo SSH, antes de traduzir:

```bash
ssh -T server 'cat <pasta>/pt.srt'
ssh -T server 'cat ~/apps/translunar/config/idiomas/<idioma>.yaml'
ssh -T server 'cat ~/apps/translunar/config/glossario.yaml'
ssh -T server 'cat <pasta>/estado.json'
```

O `estado.json` traz a chave `video`, com o nome do arquivo do vídeo. Com ela, leia o contexto, se existir:

```bash
ssh -T server 'cat ~/translunar-dados/entrada/<video sem extensão>.contexto.md'
```

Se o contexto não existir, siga sem ele e registre isso na resposta.

### 5. Localizar

Faça um idioma por vez. Escreva o `.srt` completo numa pasta temporária local, fora do projeto (por exemplo `/tmp/translate-subtitles/<corte>/<idioma>.srt`), com os mesmos blocos `id` e `timestamp` do `pt.srt` e só o texto trocado ([translate-subtitles-01]).

Para cada legenda, calcule o máximo de caracteres pela duração e quebre em até 2 linhas de 32 caracteres, equilibradas ([translate-subtitles-05]). Aplique o perfil e o glossário ([translate-subtitles-03], [translate-subtitles-04]).

### 6. Gravar de forma atômica

```bash
scp /tmp/translate-subtitles/<corte>/<idioma>.srt server:<pasta>/.<idioma>.srt.tmp
ssh -T server 'mv <pasta>/.<idioma>.srt.tmp <pasta>/<idioma>.srt'
```

### 7. Validar

```bash
ssh -T server '~/apps/translunar/.venv/bin/legendar validar <pasta>/<idioma>.srt --json'
```

A saída é `{"ok", "file", "language", "problems": [{"id", "kind", "detail"}]}`. Códigos de saída: 0 aprovado, 2 uso, 3 recusado, 5 dependência.

- **0:** o idioma está pronto. Siga para o próximo.
- **3:** reescreva **só** as legendas listadas em `problems` e volte ao passo 6. Por `kind`: `cps` e `chars`, encurte o texto; `lines`, reequilibre em até 2 linhas; `timestamp`, `missing_id`, `duplicate_id` e `extra_id`, restaure id e timestamp do `pt.srt`; `format`, corrija o formato SRT.
- **2 ou 5:** **PARE** e mostre a mensagem ao usuário com o template `blocker`.

Depois de 3 rodadas sem aprovar, **PARE** e mostre ao usuário os problemas restantes do idioma com o template `blocker` ([translate-subtitles-09]).

### 8. Responder ao usuário

Responda com o template `completion` e o formato abaixo. Oriente o usuário a conferir a prévia de cada idioma no painel antes de queimar.

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

Uma tabela por idioma tratado:

| Idioma | Legendas | Rodadas de validação | Resultado |
|---|---|---|---|
| en | 42 | 2 | aprovado |
