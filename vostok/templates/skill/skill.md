---
name: #{SKILL_NAME}
description: "#{SKILL_DESCRIPTION}"
allowed-tools: #{SKILL_ALLOWED_TOOLS}
metadata:
  version: "1.0.0"
  author: "#{AUTHOR}"
  scripts: "#{SKILL_SCRIPTS}"
  templates: "#{SKILL_TEMPLATES}"
---

# #{SKILL_TITLE}

#{SKILL_SUMMARY}

## Termos

#{SKILL_TERMS}

## Regras

#{SKILL_RULES}

## Checklist

Copie e marque o progresso:

```
#{SKILL_CHECKLIST}
```

## Passos

### 1. Carregar o contexto

Execute:

```bash
vostok context load --skill #{SKILL_NAME}
```

#{SKILL_STEPS}

## Formatos de resposta

Respostas ao usuário usam os templates de `templates/responses/`. Formatos próprios desta skill:

#{SKILL_RESPONSE_FORMATS}
