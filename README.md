# Translunar

Pipeline de legendas multilíngues para vídeo vertical. Você envia cortes em português pelo painel e o Translunar devolve, para cada um, versões em inglês, espanhol e francês com a legenda queimada no vídeo, prontas para postar em Reels, TikTok, Shorts e X. O texto não é traduzido ao pé da letra: é localizado, para que quem assiste entenda nos próprios termos.

Faz parte do ecossistema [Ishtar Sink](https://github.com/Ishtar-Sink): código aberto (AGPL-3.0), pensado para autohospedagem, sem conta, sem plano pago e sem telemetria. O vídeo fica no seu servidor.

A pipeline não chama nenhuma API de IA externa: a transcrição roda local, com o Whisper, e a tradução é feita pelo Claude Code, com a skill `translate-subtitles`.

## Como funciona

1. **Subir:** envie o corte pelo painel (aba Acervo).
2. **Transcrever:** o Whisper, rodando local no servidor, gera o `pt.srt`.
3. **Revisar:** confira a prévia com a legenda sobreposta no vídeo e corrija o `pt.srt` no painel.
4. **Traduzir:** no Claude Code, use a skill `translate-subtitles` com o caminho do `pt.srt`. Ela grava um `.srt` por idioma.
5. **Conferir:** veja a prévia de cada idioma no painel (bloco "Idiomas e queima").
6. **Queimar e baixar:** gere os vídeos com a legenda queimada e baixe um a um ou em `.zip`.

```text
  Painel: envio do corte
        │
        ▼
  servidor: saida/corte-01/pt.srt ◄── transcrição (Whisper, local)
        │
        ▼
  Painel: revisão do pt.srt (prévia e edição)
        │
        ▼
  Claude Code (skill translate-subtitles)
        │  grava en.srt  es.srt  fr.srt  e valida com `legendar validar`
        ▼
  Painel: prévia de cada idioma
        │
        ▼
  ffmpeg-full: en.mp4  es.mp4  fr.mp4   (legenda queimada, áudio intacto)
        │
        ▼
  Painel: download (um a um ou .zip)
```

## Plataformas

Hoje o Translunar roda num **Mac com Apple Silicon**. O modelo Whisper é leve e roda em outras GPUs e até em CPU, mas o projeto ainda depende do macOS em três pontos:

| Parte | Hoje (macOS) | Outras plataformas |
|---|---|---|
| Transcrição | [`mlx-whisper`](https://github.com/ml-explore/mlx-examples), que usa o MLX da Apple | planejado: [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper), com GPU (CUDA) ou CPU |
| Serviço do painel | LaunchAgent (`launchctl`) | planejado: `systemd` no Linux |
| Nome na rede local | `dns-sd` (Bonjour) | planejado: Avahi no Linux |

O painel, a fila, a queima com o ffmpeg, a CLI e a skill de tradução já são independentes de sistema. O suporte a Linux e Windows está no [Roadmap](#roadmap), na SPEC-003.

## Requisitos

- Um Mac com Apple Silicon como servidor (desenvolvido num M1 Pro com 16 GB).
- [Homebrew](https://brew.sh/), Python 3.11+ e [`uv`](https://docs.astral.sh/uv/).
- `ffmpeg-full` do Homebrew. O `ffmpeg` padrão do Homebrew não tem libass, por isso não queima legenda.
- [Caddy](https://caddyserver.com/), para o acesso HTTPS pela rede local.
- O [Claude Code](https://claude.com/claude-code) numa máquina com acesso SSH ao servidor, para a tradução.

## Convenções

A skill de tradução e os arquivos de `deploy/` partem destas convenções. Se usar outras, ajuste os arquivos citados.

| O quê | Valor padrão | Onde aparece |
|---|---|---|
| Alias SSH do servidor | `server` (em `~/.ssh/config`) | skill `translate-subtitles` |
| Pasta do projeto | `~/apps/translunar` | skill, `deploy/local.translunar-painel.plist` |
| Pasta de dados | `~/translunar-dados` (`entrada/` e `saida/`) | skill, `config/config.local.yaml` |
| Logs | `~/logs` | `deploy/local.translunar-painel.plist` |
| Painel | `127.0.0.1:8770` | `config/config.yaml`, `deploy/caddyfile-translunar` |
| Endereço HTTPS | `translunar.local` e `<ip-do-servidor>:8771` | `deploy/caddyfile-translunar` |

## Instalação no servidor

Os comandos abaixo rodam no servidor.

1. Instale as dependências do sistema:

   ```bash
   brew install uv ffmpeg-full caddy
   ```

   Os binários do ffmpeg com libass ficam em `$(brew --prefix ffmpeg-full)/bin/`.

2. Clone o projeto e crie as pastas:

   ```bash
   mkdir -p ~/apps ~/logs ~/translunar-dados/entrada ~/translunar-dados/saida
   git clone https://github.com/Ishtar-Sink/Translunar.git ~/apps/translunar
   cd ~/apps/translunar
   ```

3. Crie `config/config.local.yaml`, só com os valores desta máquina. Ele fica fora do git e sobrepõe o `config/config.yaml`:

   ```yaml
   pasta_dados: ~/translunar-dados
   queima:
     ffmpeg: /opt/homebrew/opt/ffmpeg-full/bin/ffmpeg
     ffprobe: /opt/homebrew/opt/ffmpeg-full/bin/ffprobe
   ```

   Confira os caminhos do ffmpeg com `brew --prefix ffmpeg-full`.

4. Crie o `.env` com a senha do painel:

   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

   Troque `TRANSLUNAR_PAINEL_SENHA` por uma senha forte. `TRANSLUNAR_PAINEL_SEGREDO` pode ficar vazio: o painel gera um e grava na pasta de dados.

5. Instale o projeto com o extra do Mac e confira:

   ```bash
   uv sync --extra mac
   .venv/bin/legendar --version
   ```

   O modelo do Whisper é baixado na primeira transcrição.

6. Suba o painel como LaunchAgent, para ele voltar sozinho depois de um reinício. O arquivo de `deploy/` usa `/Users/server` como pasta pessoal; troque pela sua ao copiar:

   ```bash
   sed "s|/Users/server|$HOME|g" deploy/local.translunar-painel.plist > ~/Library/LaunchAgents/local.translunar-painel.plist
   launchctl load -w ~/Library/LaunchAgents/local.translunar-painel.plist
   curl -s http://127.0.0.1:8770/api/sessao
   ```

   A resposta esperada é `{"autenticado":false,"csrf":null}`. Os logs ficam em `~/logs/translunar-painel.log` e `~/logs/translunar-painel.err`. O painel escuta só em `127.0.0.1:8770`; o acesso de fora passa pelo Caddy.

7. Configure o Caddy. Troque o IP do bloco de `deploy/caddyfile-translunar` pelo IP do servidor na rede local e importe o bloco no seu Caddyfile (`$(brew --prefix)/etc/Caddyfile`), com backup antes:

   ```bash
   CADDYFILE="$(brew --prefix)/etc/Caddyfile"
   cp "$CADDYFILE" "$CADDYFILE.bak"
   echo "import $HOME/apps/translunar/deploy/caddyfile-translunar" >> "$CADDYFILE"
   caddy validate --config "$CADDYFILE" --adapter caddyfile
   caddy reload --config "$CADDYFILE" --adapter caddyfile
   ```

   Se o Caddy ainda não roda como serviço, suba com `brew services start caddy` em vez do `reload`.

8. Publique o nome `translunar.local` na rede local com o `dns-sd` do macOS. Para ficar permanente, crie um LaunchAgent `~/Library/LaunchAgents/local.translunar-mdns.plist` que roda, com `RunAtLoad` e `KeepAlive`:

   ```bash
   /usr/bin/dns-sd -P Translunar _https._tcp local 443 translunar.local <ip-do-servidor>
   ```

   e carregue com `launchctl load -w ~/Library/LaunchAgents/local.translunar-mdns.plist`.

## Acesso

- Na rede local: `https://translunar.local`.
- Quando o `.local` não resolve (uma VPN costuma impedir o mDNS): `https://<ip-do-servidor>:8771`.
- O certificado vem da CA local do Caddy (`tls internal`). Instale e confie na CA em cada aparelho, para o navegador não avisar. Ela fica na pasta de dados do Caddy, em `pki/authorities/local/root.crt` (com o Caddy rodando como seu usuário, `~/Library/Application Support/Caddy/`).
- **Nunca exponha o painel à internet.** Ele é de um usuário só e protegido por senha, mas não foi feito para ficar público.

## Uso do painel

- **Acervo:** envie os cortes arrastando e soltando na área de envio. Cada cartão tem um seletor de formato 9:16 ou 16:9.
- **Revisão:** rode a transcrição, veja a prévia com a legenda sobreposta e edite o `pt.srt`. Também é aqui que você edita o contexto do vídeo e copia o caminho do `pt.srt` com o botão "Copiar", para usar na skill.
- **Idiomas e queima:** no bloco "Idiomas e queima", veja a prévia de cada idioma, gere a queima e assista ou baixe os vídeos. Você pode baixar os vídeos um a um ou em `.zip`.
- **Armazenamento:** veja o uso do disco e filtre por Tudo, Vídeos originais ou Legendas e queimas. Marque o que não precisa mais e apague em definitivo para liberar espaço.

## Tradução com o Claude Code

Para traduzir um corte, use a skill `translate-subtitles` no Claude Code, com o caminho do `pt.srt` no servidor:

```text
/translate-subtitles ~/translunar-dados/saida/corte-01/pt.srt
```

Ou cole o caminho no chat e peça para traduzir. A skill:

1. Pergunta quais idiomas você quer. As opções são os perfis em `config/idiomas/`.
2. Lê o `pt.srt`, o perfil de cada idioma, o glossário e o contexto do vídeo, se existir.
3. Grava um `<idioma>.srt` ao lado do `pt.srt`, sem mexer no `pt.srt`.
4. Valida cada arquivo com `legendar validar`. Só termina quando a validação estiver aprovada.

Para acrescentar um idioma, crie um perfil em `config/idiomas/<codigo>.yaml`, no mesmo formato de `config/idiomas/es.yaml`:

```yaml
codigo: es
nome: Espanhol
variante: espanhol neutro (latino-americano)
publico: hispanofalantes de vários países, sem regionalismos
registro: segue o do original, natural e conversacional
regras:
  - não usar vosotros
  - evitar gírias de um país específico
```

Para editar o glossário, use `config/glossario.yaml`. Um termo com `traducoes` vazio nunca é traduzido. Um termo com traduções fixas usa a tradução de cada idioma. Os perfis e o glossário fazem parte do projeto: versione as mudanças no git.

## Linha de comando

Os comandos rodam no servidor, com `~/apps/translunar/.venv/bin/legendar`:

| Comando | O que faz |
|---|---|
| `legendar painel` | Sobe o servidor do painel (usado pelo LaunchAgent). |
| `legendar transcrever [VIDEO...] [--forcar] [--json]` | Transcreve os vídeos informados e gera o `pt.srt`. `--forcar` refaz mesmo o que já está pronto. |
| `legendar validar <CAMINHO_SRT> [--json]` | Confere um `.srt` contra os limites da legenda e contra o `pt.srt`. |
| `legendar queimar <CORTE> <IDIOMA>[,<IDIOMA>...] [--forcar] [--json]` | Queima a legenda de um ou mais idiomas no vídeo do corte. |
| `legendar status [CORTE] [--json]` | Mostra o estado de cada etapa e idioma, de um corte ou de todos. |

`--json` troca a saída de texto por JSON. A saída de `legendar validar --json` tem este formato:

```json
{
  "ok": false,
  "file": "/Users/voce/translunar-dados/saida/corte-01/en.srt",
  "language": "en",
  "problems": [
    {"id": 12, "kind": "cps", "detail": "19.4 > 17"},
    {"id": 15, "kind": "timestamp", "detail": "00:00:31,200 difere de 00:00:31,000"}
  ]
}
```

Códigos de saída:

| Código | Significado |
|---|---|
| 0 | sucesso |
| 1 | erro de execução (ffmpeg, whisper, E/S) |
| 2 | uso inválido (argumento ou corte inexistente) |
| 3 | validação recusada |
| 4 | corte bloqueado (lock ou em processamento) |
| 5 | dependência ausente (ffmpeg sem libass, mlx-whisper, fonte) |

## Atualização

No servidor, com a árvore do projeto limpa (`git -C ~/apps/translunar status`):

```bash
git -C ~/apps/translunar pull
cd ~/apps/translunar && uv sync --extra mac
launchctl kickstart -k gui/$(id -u)/local.translunar-painel
```

## Desenvolvimento

Na raiz do projeto:

```bash
uv sync
uv run pytest
uv run ruff check
uv run ruff format --check
uv run mypy
```

Para rodar os testes sem o `mlx-whisper`, defina `TRANSLUNAR_TRANSCRITOR=falso`.

## Roadmap

| Spec | Escopo | Situação |
|---|---|---|
| [SPEC-001](vostok/work/specs/refined/SPEC-001-mvp-pipeline-de-legendas-multilingues.md) | MVP: painel, transcrição local, revisão com prévia, tradução pela skill, queima e downloads, no Mac | em andamento |
| [SPEC-003](vostok/work/specs/draft/SPEC-003-suporte-a-outras-plataformas.md) | Outras plataformas: transcrição com `faster-whisper` (GPU ou CPU), serviço e nome na rede no Linux, instalação por plataforma | planejada (rascunho) |

## Especificação

A especificação do MVP está em [vostok/work/specs/refined/SPEC-001-mvp-pipeline-de-legendas-multilingues.md](vostok/work/specs/refined/SPEC-001-mvp-pipeline-de-legendas-multilingues.md).

## Sobre o nome

A injeção translunar é a queima de motor que tira a nave da órbita da Terra e a manda para outro mundo. O Translunar faz isso com o vídeo: tira o corte do público de origem e o lança para outros idiomas, com a legenda queimada na imagem.

## Licença

[AGPL-3.0](LICENSE).
