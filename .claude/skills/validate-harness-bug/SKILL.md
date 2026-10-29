---
name: validate-harness-bug
description: "Valida a correção de um defeito do próprio harness Vostok (CLI vostok, skills, regras, templates e configuração distribuídos), não do projeto do usuário: encontra as issues [harness-bug] do usuário respondidas com a correção, reinstala a versão citada, roda vostok update, segue os passos de retomada da resposta, confere se o defeito relatado deixou de acontecer e, com autorização, comenta o resultado e fecha a issue. Use quando o usuário pedir /validate-harness-bug, \"valida a correção do bug do harness\", ou disser que a issue #N foi respondida. Não use para defeitos do projeto do usuário."
allowed-tools: Read Glob Grep Bash
---

> Este é apenas um redirecionamento para a skill.
> Leia e siga o arquivo `vostok/skills/default/validate-harness-bug/SKILL.md`.
