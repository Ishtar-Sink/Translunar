# Arquitetura

Define a organização da pipeline, do painel e da CLI.

[project/architecture-01]: O núcleo da pipeline é uma biblioteca. A CLI e o painel são camadas finas que a chamam, sem duplicar lógica.
[project/architecture-02]: Cada etapa (probe, transcrição, segmentação, conversão para WebVTT, validação, queima) é um módulo isolado, com entrada e saída explícitas.
[project/architecture-03]: A pipeline não chama nenhum modelo de IA. As traduções entram como arquivos `<idioma>.srt` gravados pela skill ao lado do `pt.srt` (DEC-002).
[project/architecture-04]: Toda etapa é idempotente: decide se roda pelo hash das entradas, gravado no `estado.json` do corte. Uma entrada alterada marca o que depende dela como desatualizado, sem refazer sozinha.
[project/architecture-05]: O estado e o progresso de cada etapa e idioma ficam em disco e sobrevivem a reinício.
[project/architecture-06]: Antes de processar um corte, adquirir o lock por corte (CLI e painel).
[project/architecture-07]: A falha num vídeo ou idioma é capturada e mostrada, sem derrubar o resto da fila.
[project/architecture-08]: Todo comando da CLI é não interativo, tem a opção `--json` e usa códigos de saída com significado.
[project/architecture-09]: Os jobs longos (transcrição e queima) rodam no worker do painel, sem depender de sessão SSH.
[project/architecture-10]: Modelos, estilo, limites e paralelismo ficam em `config/*.yaml`, nunca fixos no código.
