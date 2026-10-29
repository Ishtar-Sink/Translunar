# Anti-loop

Define as regras para que o agente evite loops e mitigar gastos desnecessários.

[agent/anti-loop-01]: Ao encontrar um erro, antes da primeira tentativa de correção, execute `vostok memory search issue <trecho estável da mensagem>`. Se houver uma entrada, aplique a solução dela primeiro.
[agent/anti-loop-02]: No máximo 2 tentativas de correção para o mesmo erro com a mesma abordagem. Depois disso, mude de abordagem ou pare e responda com o template `blocker`.
[agent/anti-loop-03]: Um erro resolvido que exigiu investigação é registrado como issue, conforme [agent/memory-04].
