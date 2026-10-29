# Segurança

Define as regras de segurança da pipeline e do painel.

[project/security-01]: A pipeline e o painel não fazem chamada de rede para serviços externos: vídeo e transcrição ficam no Mac.
[project/security-02]: O cliente do painel envia o id do corte, nunca um caminho. O servidor rejeita path traversal e só mexe em `entrada/` e `saida/`.
[project/security-03]: Painel com senha única, sessão por cookie, proteção contra CSRF e limite de tentativas. Por padrão, só na rede local.
[project/security-04]: A senha do painel fica em config ou num `.env` fora do git.
[project/security-05]: O `ffmpeg` e o `ffprobe` são chamados com lista de argumentos, nunca com `shell=True`.
