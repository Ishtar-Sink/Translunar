---
id: SPEC-001
title: "MVP — Pipeline de legendas multilíngues"
status: draft
author: "Victor Batalha"
created_at: 2026-10-28T21:56:13Z
updated_at: 2026-10-28T22:00:34Z
tags: [video, legendas, localizacao, whisper, ffmpeg, pipeline, painel]
---

# MVP — Pipeline de legendas multilíngues

Pipeline local, executada no Mac, que recebe cortes de vídeo em português (9:16) de uma pasta e gera, para cada um, versões legendadas em inglês, espanhol e francês, com a legenda queimada no vídeo e prontas para postar em Reels, TikTok, Shorts e X. O texto não é traduzido literalmente: é localizado, para que quem assiste entenda nos próprios termos. Um painel web, acessível pela máquina do Victor, permite subir os cortes para o Mac, acompanhar o processamento, baixar os vídeos prontos e apagar os antigos para liberar espaço.

## Contexto

### O que será construído

Um recurso novo, do zero: uma ferramenta de linha de comando que automatiza o fluxo transcrição → localização por IA → legenda queimada no vídeo, para virar uma rotina recorrente de espalhar conteúdo em outros idiomas.

### Dor e problema

- Legendar cada corte manualmente em cada idioma (ex.: editor de vídeo) não escala. Cada idioma novo multiplica o trabalho.
- Tradução literal soa estranha e perde o sentido: expressões, humor e referências brasileiras não funcionam em outros idiomas. O objetivo é que a pessoa de cada país entenda o conteúdo nos seus próprios termos.
- Erros de transcrição em português se propagam para todos os idiomas, então é preciso um ponto opcional de revisão antes da localização.
- Os vídeos ficam no Mac, e o Victor trabalha no Windows. Levar os cortes até o Mac e trazer os prontos de volta por linha de comando (SSH/scp) é trabalhoso, e os arquivos acumulam e ocupam espaço em disco sem um jeito simples de limpar.

### Entrada e destino

- Origem: cortes que o Victor baixa e deixa numa pasta local. Sempre em português (pt-BR), em formato vertical 9:16 e sem legenda queimada (o Victor garante isso na escolha dos vídeos).
- Destinos: Reels, TikTok, Shorts e X, todos em vídeo vertical 9:16, por isso a legenda precisa respeitar as áreas cobertas pela interface dessas plataformas.
- Idiomas de saída no MVP: inglês, espanhol e francês.

### Variantes de idioma (decisão)

O critério é adotar a variante mais comumente entendida por quem fala o idioma, evitando regionalismos:

- Inglês: inglês internacional, claro e sem gírias regionais.
- Espanhol: espanhol neutro (latino-americano), sem regionalismos nem vosotros, por ter muitos países com variações.
- Francês: francês da França (o do Canadá varia demais).

O registro (formal/informal) segue o do original, de forma natural e conversacional, e é configurável por idioma.

### Painel de gerenciamento

Além da linha de comando, o MVP inclui um painel web que roda no Mac e é acessado pelo navegador da máquina do Victor. Ele serve para:

- subir os cortes para o Mac;
- acompanhar e disparar o processamento;
- baixar os vídeos prontos;
- excluir cortes antigos para liberar espaço.

O painel é de uso pessoal (um único usuário) e fica restrito à rede local ou a uma VPN privada, nunca exposto à internet.

### Limitações e ambiente

- A pipeline roda no Mac (Apple Silicon, M1 Pro, 16 GB), sem interface gráfica.
- O desenvolvimento e a operação são feitos pelo Claude Code no Windows, conectado ao Mac por SSH. Jobs longos não podem morrer se a sessão SSH cair.
- Só o texto transcrito vai para a API de IA. O vídeo não sai da máquina.

### Fora do escopo do MVP (roadmap)

Specs futuras, em ordem provável:

1. Títulos, descrições e hashtags localizados por plataforma e idioma.
2. Dublagem.
3. Publicação automática (TikTok, Instagram e YouTube exigem app aprovado, e a API do X é paga; o MVP entrega só os arquivos prontos para postar).
4. Pasta monitorada que processa cortes novos sozinha. No MVP o processamento é disparado pela linha de comando ou pelo painel.
5. Idiomas com alfabeto não latino (japonês, árabe, etc.), que exigem tratamento de fontes.

## Recursos

1. Entrada por pasta. Processa todos os vídeos de `entrada/` (mp4, mov, mkv, webm, m4v), pulando os que já foram processados.
2. Transcrição em pt-BR. Whisper rodando localmente no Apple Silicon, gerando `pt.srt` com timestamps.
3. Revisão opcional. Com `--revisar`, a execução para depois da transcrição. O Victor edita o `pt.srt` e roda o comando de novo para continuar. A edição manual é sempre respeitada.
4. Segmentação para vídeo vertical. Reagrupa a transcrição em legendas curtas: no máximo 2 linhas, cerca de 30 caracteres por linha, duração entre ~1 s e ~6 s.
5. Localização por IA. Para cada idioma, o texto é adaptado (não traduzido literalmente) usando:
   - o perfil do idioma (variante, público, registro);
   - o glossário (termos fixos, nomes próprios, o que não se traduz);
   - o contexto do vídeo, opcional, num arquivo `<video>.contexto.md` ao lado do vídeo, para explicar referências que só brasileiros entendem.
6. Controle de leitura. Após localizar, valida a velocidade de leitura (máx. ~17 caracteres/segundo). Linhas acima do limite são reescritas de forma mais curta.
7. Legenda queimada em 9:16. Renderiza o vídeo com a legenda embutida, com estilo legível e posicionada fora das áreas cobertas pela interface das plataformas. Mantém resolução, proporção, duração e áudio.
8. Saída organizada por vídeo e idioma. Para cada vídeo, `saida/<video>/` contém `pt.srt`, `en.srt`, `en.mp4`, `es.srt`, `es.mp4`, `fr.srt`, `fr.mp4`.
9. Idempotência e retomada. Rodar de novo não refaz o que já está pronto. Mudou o `pt.srt`, o glossário, o perfil do idioma ou o contexto do vídeo: refaz só os idiomas afetados. `--forcar` refaz tudo.
10. Idioma novo sem código. Adicionar um idioma de alfabeto latino é criar um arquivo de perfil em `config/idiomas/`.
11. Resiliência. Falha em um vídeo ou idioma não derruba o lote. No final há um resumo com sucessos, falhas, tempo e custo estimado de tokens.
12. CLI simples. Comando `legendar`, com opções para pasta de entrada, idiomas, revisão, forçar, pular render e paralelismo.
13. Painel web. `legendar painel` sobe um servidor com interface no navegador, acessível pela máquina do Victor, protegido por senha.
14. Upload de cortes. Subir um ou vários vídeos (arrastar e soltar) direto para `entrada/` no Mac, com barra de progresso, validação de formato e de espaço em disco. Nomes duplicados recebem sufixo.
15. Lista e status. Tabela de cortes com miniatura, duração, tamanho e estado por etapa e idioma (aguardando, transcrevendo, aguardando revisão, localizando, renderizando, pronto, erro), atualizada em tempo real.
16. Disparar processamento. Selecionar cortes e idiomas, escolher se haverá revisão, informar o contexto do vídeo e iniciar. A execução entra numa fila.
17. Revisão no painel. Ver e editar o `pt.srt` (editor de texto simples) e o contexto do vídeo, e então continuar o processamento.
18. Download e prévia. Baixar o vídeo pronto e o `.srt` de cada idioma, ou todos os idiomas de um corte num `.zip`. Assistir à prévia no navegador.
19. Excluir e limpar espaço. Mostrar espaço livre e usado em disco e o tamanho de cada corte. Excluir um corte (original e/ou saídas), com seleção múltipla e filtro "mais antigos que N dias", sempre com confirmação e informando o espaço liberado.

## Detalhes Técnicos

### Stack sugerida (ajustável)

- Linguagem: Python 3.11+, gerenciado com `uv`.
- Transcrição: `mlx-whisper` com o modelo `mlx-community/whisper-large-v3-turbo` (configurável). `faster-whisper` como alternativa em outras máquinas.
- Localização: SDK `anthropic`, modelo configurável (padrão `claude-sonnet-5-5`), chave via variável de ambiente `ANTHROPIC_API_KEY`.
- Render: `ffmpeg` com libass (filtro `subtitles`) e `ffprobe`. A fonte vai embarcada no repositório e é carregada via `fontsdir`, sem depender das fontes do sistema.
- Configuração: arquivos YAML.

### Estrutura de pastas

```
entrada/
  corte-01.mp4
  corte-01.contexto.md      # opcional
saida/
  corte-01/
    pt.srt
    en.srt  en.mp4
    es.srt  es.mp4
    fr.srt  fr.mp4
    estado.json             # hashes e etapas concluídas
config/
  config.yaml               # modelos, estilo, limites, paralelismo
  glossario.yaml
  idiomas/
    en.yaml  es.yaml  fr.yaml
```

### Fluxo por vídeo

1. `ffprobe`: valida o arquivo, lê resolução, duração e se há faixa de áudio.
2. Transcrição para `pt.srt`.
3. Pausa opcional para revisão (`--revisar`).
4. Segmentação em legendas curtas para 9:16.
5. Localização por idioma.
6. Validação das legendas localizadas e reescrita das que estão rápidas demais.
7. Render com ffmpeg.
8. Atualização do `estado.json`.

### Localização (prompt e validação)

- O prompt de sistema recebe: idioma e variante de destino, público, registro, glossário, contexto do vídeo e regras (adaptar expressões e referências ao equivalente compreensível em vez de traduzir literalmente; manter números e nomes; legendas curtas; sem explicações no resultado).
- A entrada para a API é JSON com id de cada legenda e a saída volta no mesmo formato. A validação é por id, não por posição. Id faltando, duplicado ou JSON inválido gera nova tentativa (até 3x) e depois erro claro.
- As legendas são enviadas em lotes, com legendas vizinhas como contexto.

### Perfis de idioma (config/idiomas/*.yaml)

Cada perfil define: nome, variante, instruções de público e registro, e regras específicas (por exemplo, espanhol neutro sem vosotros; francês da França).

### Estilo da legenda

Texto branco em negrito com contorno preto, centralizado. Margem inferior de ~20% da altura (para ficar acima da interface das plataformas) e margens laterais de ~8%. Tamanho em torno de 5,8% da largura do vídeo. Todos os valores ficam em `config.yaml`.

### Render e desempenho

- `libx264`, `-preset veryfast`, `-crf 20`, `-pix_fmt yuv420p`, áudio copiado, `-movflags +faststart`. Avaliar `h264_videotoolbox` como otimização opcional.
- Um vídeo por vez na transcrição. Localização e render por idioma em paralelo (`--jobs`, padrão 2).

### Operação via SSH

- Documentar a execução dentro de `tmux`, para o job sobreviver à queda da conexão.
- A pipeline precisa ser retomável por construção (idempotência), sem depender de a sessão continuar viva.

### Painel web

- Arquitetura: backend Python no mesmo projeto, reutilizando o núcleo da pipeline como biblioteca, de modo que a CLI e o painel executem o mesmo código. FastAPI sugerido. O frontend é leve e servido pelo próprio backend, sem deploy separado. A stack do frontend é livre, com preferência por algo sem build complexo.
- Fila e estado: fila em processo com um único worker (a transcrição é pesada, então um corte por vez). O estado fica em disco (`estado.json` por corte; SQLite opcional) e sobrevive a reinício. Ao reiniciar, jobs interrompidos voltam para a fila ou ficam marcados como interrompidos.
- Progresso em tempo real: SSE (ou polling) com a etapa atual de cada corte.
- Upload: multipart em streaming direto para disco, sem carregar o arquivo na memória. Grava em arquivo temporário e renomeia ao concluir. Verifica o espaço livre antes de aceitar. Limite de tamanho configurável. Upload em partes retomável é opcional.
- Download: streaming com suporte a `Range` (prévia e avanço no player). O `.zip` é gerado sob demanda.
- Exclusão: opera só em `entrada/` e `saida/`. O cliente envia o id do corte, nunca um caminho, e o servidor valida contra path traversal. Bloqueada para cortes em processamento. Exclusão definitiva (sem lixeira), com confirmação explícita.
- Acesso e segurança: endereço e porta configuráveis, com padrão na rede local. Autenticação por senha única definida em config ou `.env`, sessão por cookie, proteção contra CSRF e limite de tentativas. Não expor à internet. O acesso remoto recomendado é por rede local ou VPN privada, e o README documenta isso. HTTPS é opcional.
- Execução: `legendar painel` roda como serviço no Mac, dentro de `tmux` ou via `launchd`.
- Concorrência CLI e painel: lock por corte, para que CLI e painel nunca processem o mesmo vídeo ao mesmo tempo.

### Segurança

- Chave de API só por variável de ambiente ou arquivo `.env` fora do git.
- Apenas texto transcrito é enviado à API.

## Roteiro de Testes

### Automatizados

1. Unitários: leitura e escrita de SRT, formatação de timestamps, segmentação e quebra de linhas, cálculo de caracteres por segundo, validação da resposta da IA por id (faltando, duplicado, JSON inválido) com a API simulada, chave de cache/hash.
2. Integração sem API real: vídeo sintético 9:16 gerado com ffmpeg + SRT fixo + localização simulada. Verificar com `ffprobe` que resolução, duração e faixa de áudio se mantêm.
3. Integração com API real (lento, opcional): um corte real curto (~30 s) nos 3 idiomas.

### Manuais

4. Corte real: rodar `legendar run` com um corte de verdade e conferir no celular se a legenda está legível e fora das áreas cobertas pela interface.
5. Qualidade da localização: conferir se expressões idiomáticas foram adaptadas e não traduzidas literalmente, e se a variante de cada idioma está correta.
6. Revisão: rodar com `--revisar`, editar o `pt.srt` e retomar. A edição deve aparecer nas legendas finais.
7. Idempotência: segunda execução sem mudanças não refaz nada. Alterar o glossário refaz só o que depende dele.
8. Glossário e contexto: um termo do glossário sai sempre como definido. O arquivo de contexto muda o resultado quando relevante.
9. Falhas: chave ausente (mensagem clara), vídeo sem áudio ou sem fala, arquivo corrompido no meio do lote (o lote continua), interrupção com Ctrl+C e retomada, queda de SSH com o job rodando no `tmux`.

### Painel

1. Automatizados (API, com worker e IA simulados): upload (ok, formato inválido, sem espaço, nome duplicado), listagem e status, disparo de job, download com `Range`, geração do `.zip`, exclusão (permitida, bloqueada em processamento, tentativa de path traversal rejeitada) e autenticação (sem login retorna 401, senha errada, limite de tentativas).
2. Manual, upload: subir pelo navegador do Windows um corte de 200 a 500 MB e acompanhar o progresso.
3. Manual, processamento: disparar pelo painel, acompanhar as etapas, editar o `pt.srt` na revisão e continuar.
4. Manual, download: baixar e assistir os 3 idiomas, individualmente e pelo `.zip`.
5. Manual, limpeza: excluir cortes antigos e conferir o espaço liberado.
6. Manual, resiliência: reiniciar o servidor no meio de um job e conferir o estado depois.
7. Manual, acesso: tentar acessar sem senha e de fora da rede.
8. Manual, concorrência: rodar CLI e painel no mesmo corte e conferir o lock.

## Critérios de Aceite

- [ ] `legendar run` em uma pasta com cortes pt-BR 9:16 gera, para cada vídeo, `pt.srt`, `en/es/fr.srt` e `en/es/fr.mp4` em `saida/<video>/`.
- [ ] Os vídeos de saída mantêm resolução, proporção, duração e áudio do original.
- [ ] As legendas queimadas têm no máximo 2 linhas, são legíveis e ficam fora das áreas cobertas pela interface de Reels, TikTok e Shorts.
- [ ] A localização segue as variantes definidas (inglês internacional, espanhol neutro, francês da França) e adapta expressões em vez de traduzir literalmente, validado em ao menos um corte com expressões idiomáticas.
- [ ] O glossário é aplicado de forma consistente e o contexto por vídeo influencia o resultado.
- [ ] `--revisar` pausa após a transcrição e respeita a edição manual do `pt.srt` ao retomar.
- [ ] A velocidade de leitura das legendas fica dentro do limite configurado.
- [ ] Segunda execução sem mudanças não refaz nada. Mudança em `pt.srt`, glossário, perfil ou contexto refaz só os idiomas afetados.
- [ ] Falha em um vídeo ou idioma não interrompe o lote, e o resumo final lista os erros e retorna código de saída diferente de zero.
- [ ] Apenas texto transcrito é enviado à API, e a chave não está no repositório.
- [ ] A pipeline funciona via SSH, e uma interrupção (inclusive queda de SSH) pode ser retomada sem perda do que já foi feito.
- [ ] Adicionar um idioma de alfabeto latino exige só um novo arquivo em `config/idiomas/`.
- [ ] README com instalação (ffmpeg, uv, chaves) e uso.
- [ ] `legendar painel` sobe a interface, acessível pelo navegador da máquina do Victor e protegida por senha.
- [ ] O upload de um ou vários cortes pelo navegador grava em `entrada/` no Mac, com progresso, rejeitando formatos inválidos e falta de espaço.
- [ ] A lista mostra cada corte com o estado por etapa e idioma, atualizada sem recarregar a página.
- [ ] É possível iniciar o processamento (idiomas, revisão, contexto) e editar o `pt.srt` pelo painel.
- [ ] Vídeos prontos e `.srt` podem ser baixados individualmente ou em `.zip`, e a prévia toca no navegador.
- [ ] Excluir cortes (originais e/ou saídas) funciona com confirmação, em lote e por idade, informando o espaço liberado. Nada fora de `entrada/` e `saida/` pode ser tocado, e cortes em processamento não podem ser excluídos.
- [ ] O painel não é exposto à internet por padrão, e o README documenta o acesso por rede local ou VPN.
- [ ] Reiniciar o painel não perde o estado dos cortes.
- [ ] CLI e painel funcionam sobre as mesmas pastas sem conflito.
- [ ] Testes automatizados passam.
