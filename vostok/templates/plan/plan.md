---
spec: #{SPEC_ID}
spec_hash: #{SPEC_HASH}
content_hash: null
adjustments: 0
adjusted_at: null
created_at: #{DATETIME}
updated_at: #{DATETIME}
---

# Plano de tarefas: #{SPEC_ID} - #{SPEC_TITLE}

Documento para revisão. É removido quando o plano é aprovado.

## Visão geral

#{PLAN_OVERVIEW}

## Tarefas

| ID | Título | Descrição | Tipo | Nível | Dependências | Cobre |
|---|---|---|---|---|---|---|
#{PLAN_TASKS}

## Fatos de esforço

| ID | Arquivos a criar | Arquivos a alterar | Contrato público | Inferência | Risco alto |
|---|---|---|---|---|---|
#{PLAN_FACTS}

## Níveis de esforço

| Nível | Descrição |
|---|---|
#{EFFORT_LEVELS}

#{ADJUSTMENT_HISTORY}
