---
description: Orquestra o fluxo completo de uma tarefa — analisa, planeja (com sua aprovação), implementa, revisa e valida antes de entregar para validação final
---

Você vai orquestrar a tarefa a seguir, chamando os agentes especializados do projeto na ordem certa. Não pule etapas e não implemente nada diretamente você mesmo — cada etapa é responsabilidade de um agente específico.

**Tarefa:** $ARGUMENTS

## Etapa 0 — Parser da Tarefa

0. Use a ferramenta Agent com `subagent_type: "task-parser"`, passando a tarefa acima crua (texto livre — este projeto não tem rastreador de tickets). Rode em foreground. Ele devolve o caminho de um arquivo com o resumo destilado — é isso que você passa adiante, não o texto bruto da tarefa.

## Etapa 1 — Análise e Plano

1. Use a ferramenta Agent com `subagent_type: "task-analyst"`, passando o **caminho do arquivo** gerado na Etapa 0 (não recole o texto da tarefa). Rode em foreground.
2. Com o relatório do task-analyst em mãos, monte um plano de implementação claro para o usuário.
3. Entre em modo de planejamento (`EnterPlanMode`) e apresente o plano, incluindo qualquer pergunta em aberto levantada pelo task-analyst (use `AskUserQuestion` se necessário para resolvê-las).
4. **Não avance para a etapa 2 sem o plano ser explicitamente aprovado** pelo usuário via `ExitPlanMode`.

## Etapa 2 — Implementação

5. Rode `git status` primeiro (nunca comece a mexer em cima de mudanças não commitadas de outra tarefa sem checar antes). Se fizer sentido isolar a tarefa (mudança não-trivial, ou já há trabalho em andamento na branch atual), crie uma branch nova a partir da atual com nome descritivo baseado no slug da tarefa (`git checkout -b <slug-da-tarefa>`) — para ajustes pequenos, pode seguir direto na branch atual.
6. Use a ferramenta Agent com `subagent_type: "implementer"`. **Não cole o plano inteiro de novo no prompt** — o plano já está salvo em arquivo (caminho informado pelo `ExitPlanMode`); passe esse caminho e um resumo de 2-3 linhas do que foi aprovado, e deixe o implementer ler o arquivo se precisar do detalhe completo. Rode em foreground.

## Etapa 3 — Code Review

**Controle de custo:** a revisão completa (esforço medium/high, via skill `code-review`) só roda **uma vez** nesta etapa. Depois disso, qualquer fix pontual que precise voltar pro `implementer` é seguido de uma checagem **leve** (o próprio `code-reviewer` lendo o diff daquele fix específico, sem invocar a skill de novo) — nunca uma nova rodada completa. No máximo **1 rodada extra** de correção, mesmo que sobre algo mais para ajustar; se sobrar mais coisa depois disso, reporte pro usuário em vez de continuar o loop sozinho.

7. Use a ferramenta Agent com `subagent_type: "code-reviewer"` pedindo explicitamente uma **revisão completa** da diff gerada pelo implementer. **Sempre passe o caminho do `task.md` da Etapa 0** (o arquivo com os critérios de aceite) — o revisor precisa validar a diff item a item contra ele, não só procurar bugs genéricos. Rode em foreground.
8. Se o revisor reportar achados que não deram para corrigir automaticamente (decisões de produto) **e** você concluir que são bugs reais (não ambiguidade de produto) — isso inclui qualquer critério de aceite marcado como não implementado/parcial no checklist do revisor — volte para o `implementer` com essas correções específicas.
9. Depois desse fix pontual, rode o `code-reviewer` **uma única vez mais**, pedindo explicitamente uma **revisão de fix pontual** (não uma revisão completa) sobre só o arquivo/trecho alterado. Se ainda sobrar algo, pare o loop e reporte ao usuário — não repita a etapa indefinidamente.

## Etapa 4 — Validação

10. Use a ferramenta Agent com `subagent_type: "test-engineer"` para validar a mudança (sanidade sintática, testes pytest de lógica pura quando aplicável, roteiro de validação manual). **Sempre passe o caminho do `task.md` da Etapa 0** — o test-engineer precisa confirmar que cada critério de aceite tem cobertura (teste ou roteiro manual claro), não só validar o que já está no diff. Rode em foreground.
11. Se algo falhar — incluindo qualquer critério de aceite sem cobertura correspondente — volte para o `implementer` com o problema específico reportado pelo test-engineer, e repita a etapa de validação **no máximo mais 1 vez**; se ainda falhar depois disso, pare e reporte ao usuário em vez de continuar sozinho.

## Etapa 5 — Entrega

12. Apresente ao usuário um resumo final e direto:
    - O que foi implementado (mapeado ao plano aprovado).
    - Achados do code review (o que foi encontrado e corrigido).
    - Resultado da validação (testes escritos, se passaram, e o roteiro de validação manual pendente do lado do usuário — inclua-o sempre que a mudança for de UI).
    - Um resumo rápido de custo: quantas chamadas de agente foram feitas e o total aproximado de tokens (a ferramenta Agent já retorna isso em `<usage>` a cada chamada — some e mostre, não precisa calcular nada novo).
    - Se a tarefa envolveu mudança de schema na planilha (coluna/aba nova): destaque isso separado, com o que foi adicionado e como dados antigos são tratados.
    - Lembre explicitamente que **nada foi commitado** — commit só acontece se o usuário pedir.

Durante todo o fluxo, o padrão de código a seguir é o `CLAUDE.md` do projeto, sem exceção. Priorize sempre a opção mais barata que ainda resolve o problema — não rode uma etapa "por garantia" se ela não foi pedida pelo fluxo.
