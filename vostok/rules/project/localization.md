# Localização

Define as regras da tradução das legendas pela skill do Claude Code.

[project/localization-01]: A skill de tradução pergunta os idiomas de saída e lê o perfil de cada um, o glossário e o contexto do vídeo antes de traduzir.
[project/localization-02]: Cada `<idioma>.srt` mantém os ids e os timestamps do `pt.srt`.
[project/localization-03]: A skill só termina com a validação da CLI aprovada, que confere ids, timestamps, linhas e leitura por segundo.
[project/localization-04]: Um idioma novo é só um perfil novo em `config/idiomas/`, sem código.
