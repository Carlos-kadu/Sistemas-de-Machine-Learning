# Projeto Final

Este é o projeto que fecha a disciplina. Ao longo do semestre, os projetos individuais cobriram as fatias centrais do ciclo de um sistema com agentes de IA, concepção e arquitetura de agentes, rastreamento de experimentos, automação com n8n e construção auditável; aqui você vai juntar tudo em um único trabalho, do começo ao fim: escolher um problema real, construir um agente de IA que o resolva, expô-lo como API e integrá-lo a um produto.

Você trabalhará individual ou em equipe (até 5 pessoas). Como o prazo é de 3 semanas, a regra de ouro é pense pequeno e completo, não grande e pela metade: é melhor um sistema simples que funciona de ponta a ponta do que uma ideia ambiciosa.

Para começar, escolha uma das trilhas a seguir. As Trilhas 1 a 3 já vêm com um problema e um conjunto de dados sugeridos, bom para quem quer ir direto ao ponto. A Trilha 4 é aberta: você propõe o próprio problema, no tema que quiser, e encontra os dados. Em qualquer trilha, a régua de saída é a mesma: **problema real, dado com fonte e licença claras, agente construído, exposto como API e integrado a um produto no ar.**


> **Escolha sua trilha antes de começar:** [Ver as trilhas disponíveis](trilhas.md)

**Data da entrega: 13/07/26**

---

## O que você precisa fazer nesse projeto?

Independentemente da trilha, o trabalho percorre o mesmo ciclo: partir de um problema real, construir um agente de IA que o resolva, expô-lo como API e integrá-lo a um produto que qualquer pessoa abre e usa.

Um agente de IA não é só um modelo fazendo uma previsão isolada. É um sistema com raciocínio: recebe uma entrada, decide o que fazer com ela (consulta dados, chama ferramentas, aplica lógica), e devolve uma resposta útil e acionável. A diferença prática: um modelo classifica; um agente classifica, explica o raciocínio e sugere o próximo passo. É essa camada extra (de decisão e ação) que transforma uma previsão em um produto.

O ciclo que vocês vão completar é: **agente → API → produto**. O agente é o núcleo de raciocínio; a API é o contrato que permite que qualquer sistema o consuma; o produto é a interface que entrega valor para quem usa.

No fim, esse sistema precisa ser **deployable** e **reliable**.

#### Deployable → qualquer um pode usar

- Empacotado (Docker) e sobe com um comando.
- Uma pessoa de fora consegue usar sem você do lado explicando.
- Reproduzível: outra equipe faz clone → comando → sistema sobe.

#### Reliable → suporte para o mundo real

- Tem **guardrails**: valida o que entra (entrada inválida, fora de escopo, abusiva) e o que sai (resposta sem sentido, alucinação detectável, conteúdo inadequado) antes de chegar ao usuário.
- Tem um **fallback / degradação graciosa**: o que o sistema faz quando a API do LLM está fora do ar, uma ferramenta externa cai ou a resposta demora demais? (Ex.: devolver uma resposta padrão e avisar, em vez de estourar um erro.)
- Não mostra erro técnico cru para o usuário.
- Responde em tempo aceitável, agentes com múltiplas chamadas ao LLM acumulam latência; isso precisa ser medido e controlado.

### O caminho do trabalho

1. **Enquadre o problema.** Defina a métrica de sucesso de negócio (o que conta como "deu certo" para o stakeholder) e a métrica técnica que você vai otimizar. Defina os stakeholders, defina quem usa o sistema e como.
2. **Prepare os dados e o contexto.** Em projetos agentícos, os dados raramente são para treinar um modelo, são o contexto que o agente usa para raciocinar: base de conhecimento para RAG, exemplos de few-shot, dados estruturados que o agente consulta em tempo real. Registre a origem, licença e vieses conhecidos de tudo que alimenta o agente.
3. **Construa e itere o agente.** Comece por um baseline simples (um agente com ferramentas mínimas e um prompt direto) e evolua a partir dele. Documente as decisões de design: qual LLM escolheu e por quê, quais ferramentas o agente tem, como o prompt mudou entre versões, quais guardrails foram adicionados e por quê. Guarde o que **NÃO** funcionou: tentativas falhas bem explicadas entram no relatório e contam pontos.
4. **Avalie de verdade.** Defina critérios de sucesso e meça com métricas adequadas: qualidade da resposta do agente, latência ponta a ponta (cada chamada ao LLM soma), custo por interação (APIs pagas cobram por token), taxa de acionamento do fallback e taxa de erros dos guardrails. Teste casos extremos: entrada vazia, fora de escopo, tentativa de jailbreak.
5. **Coloque em produção.** Empacote o agente, exponha-o como API e integre-o a um produto (interface, bot ou dashboard) hospedado em um serviço acessível por link. O ciclo completo é: agente → API → produto.
6. **Monitore.** Deixe o sistema registrar o que está acontecendo: traces das chamadas ao agente (entrada, ferramentas acionadas, resposta), custo acumulado por chamada ao LLM, latência, taxa de fallback acionado e erros dos guardrails. São esses sinais que revelam se o agente está funcionando no mundo real — não só nos seus testes.

> **DICA:** Use Spec Driven Development (SDD) como apresentamos em sala de aula.


## O que você entrega no fim

- O **relatório** no template.
- O **repositório**.


## Avaliação e entrega

### 1. O relatório

Cada equipe entrega um report (pode ser um `.md`, um site, um .pdf) que vira página pública. Ele é onde você mostra as decisões que tomou e por quê. Um bom relatório permite que alguém entenda e avalie seu sistema sem precisar abrir o código. Cada seção abaixo diz o que esperamos.

#### Cabeçalho

Logo no topo, deixe o essencial visível: o link da aplicação, o link do repositório no GitHub e os integrantes da equipe.

#### Definição do problema

Descreva o problema que vocês estão resolvendo, dizendo qual trilha e qual projeto escolheram (ou, na Trilha 4, qual problema propuseram). Responda:

- Que dor é essa e por que importa?
- Quem são os stakeholders (os grupos que usam ou são afetados pelo sistema)?
- Qual a métrica de sucesso, tanto a de **negócio** (o que faz o stakeholder considerar que deu certo) quanto a **técnica**?

#### Como o sistema é montado

Aqui você descreve a engenharia da solução. Inclua:

- um **diagrama de arquitetura** mostrando as peças (entrada → agente → ferramentas → resposta → produto) e como elas se conectam;
- **agent/model exploration:** quais abordagens vocês consideraram antes de decidir (tipo de agente, ferramentas, prompts, modelo base);
- **deployment:** como o agente foi empacotado como API e como o produto consome essa API — onde está hospedado e como recebe entradas em produção;
- **CI/CD (se houver):** o que é testado ou implantado automaticamente. Mostre também a estratégia de confiabilidade: o que acontece quando uma dependência falha (o fallback).

#### Descrição do agente

- **Modelo base e ferramentas:** qual LLM vocês usaram e por quê (custo, capacidade, latência). Quais ferramentas o agente tem acesso e o que cada uma faz.
- **Dados e contexto:** qual dado alimenta o agente (base de conhecimento, exemplos, dados consultados em tempo real) — origem, licença e como foi preparado.
- **Guardrails:** o que o sistema valida na entrada (o que rejeita ou redireciona) e na saída (o que verifica antes de devolver ao usuário). O que acontece quando um guardrail é acionado?
- **Iterações de prompt e design:** o caminho do baseline simples até a versão final: como o prompt evoluiu, quais ferramentas foram adicionadas ou removidas, o que não funcionou. Tentativas falhas bem explicadas contam pontos.

#### Avaliação do sistema

Esta seção responde à pergunta: **como vocês sabem que o sistema funciona?** Apresente:

- **Performance:** os critérios de sucesso, o conjunto de teste e as métricas adequadas ao problema.
- **UX:** a experiência de quem usa (é claro? rápido? o que acontece quando o sistema erra ou não tem certeza?).

#### Demonstração

Grave um vídeo demonstrando o sistema funcionando em casos de uso reais. Pegue um usuário típico e siga o fluxo dele do início ao resultado. O objetivo é deixar claro o que o sistema faz na prática, não em teoria.

#### Reflexão sobre o que aprenderam

Sejam honestos. O que funcionou bem? O que não funcionou como planejado (decisões que voltaram atrás, limitações do dado, coisas que ficaram de fora)? E próximos passos: o que vocês fariam com mais tempo?

#### Impactos e ética

Pensando no seu problema (não em ética genérica): quem pode ser prejudicado por um erro do sistema, e como? Há risco de viés entre grupos (gênero, região, renda)? Há questões de privacidade ou segurança no dado ou no uso? O que vocês fizeram (ou recomendam fazer) para mitigar isso?

#### Referências

Dados, modelos, bibliotecas e materiais que vocês usaram.

---

## Datas e submissão

**Data da entrega: 13/07/26**

**Como submeter:**

1. Dentro da pasta do projeto final (projeto-final-2026-1), crie a subpasta no formato `(X-Y_nome_integrantes)`, onde **X** representa a trilha e **Y** o projeto;
2. Coloque todos os entregáveis dentro dessa pasta;
3. Abra um Pull Request para submissão seguindo o mesmo padrão da pasta: `(X-Y_nome_integrantes)`;