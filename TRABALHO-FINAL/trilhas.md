## Trilhas

### Trilha 1 — Predição tabular (classificação/regressão)

#### 1.1 Previsão de churn

- **Descrição:** preveja quais clientes têm alta probabilidade de cancelar o serviço, para apoiar ações de retenção. É uma classificação binária, você vai precisar lidar com classes desbalanceadas, escolher a métrica certa (não basta acurácia) e tornar a previsão interpretável, mostrando por que aquele cliente está em risco.
- **Dado:** Telco Customer Churn (amostra da IBM, 7.043 clientes e 21 colunas, com a coluna "Churn" como alvo) ou Bank Customer Churn (18 colunas, incluindo CreditScore, Geography, Age, Balance e NumOfProducts).
- **Link:** <https://www.kaggle.com/datasets/blastchar/telco-customer-churn>
- **Produto:** Agente de IA que recebe o perfil do cliente, raciocina sobre os fatores de risco e devolve a probabilidade de churn com explicação, exposto como API e integrado a um painel ou interface conversacional de retenção.

#### 1.2 Detecção de fraude em cartão

- **Descrição:** classifique transações como fraude ou legítimas em um cenário extremamente desbalanceado. Você vai ter que ir além da acurácia (precisão/recall, PR-AUC), escolher e justificar um limiar de decisão e raciocinar sobre o custo diferente de cada tipo de erro.
- **Dado:** Credit Card Fraud Detection. São transações de dois dias, com 492 fraudes em 284.807 transações (0,172% da classe positiva); as features V1–V28 são componentes de PCA, e só "Time" e "Amount" não foram transformadas.
- **Link:** <https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud>
- **Produto:** Agente que analisa uma transação em tempo real, decide fraude/legítima com raciocínio auditável e limiar justificado, exposto como API e integrado a um painel de monitoramento ou alerta.

#### 1.3 Previsão de atraso de entrega

- **Descrição:** estime se (ou quanto) um pedido vai atrasar em relação à data prometida, usando atributos do pedido, do frete e da geolocalização. Você pode tratar como regressão (dias de atraso) ou classificação (vai atrasar?).
- **Dado:** Brazilian E-Commerce Public Dataset by Olist, mais de 100 mil pedidos com avaliações e geolocalização de uma grande e-commerce brasileira.
- **Link:** <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>
- **Produto:** Agente que estima o risco ou prazo de atraso de um pedido, explica os fatores determinantes e sugere ação, exposto como API e integrado a um painel logístico ou chat de atendimento.
- **Bônus:** o mesmo dataset serve para sentimento de review e recomendação.

#### 1.4 Risco de crédito / aprovação de empréstimo

- **Descrição:** preveja a probabilidade de aprovação ou de inadimplência de uma solicitação de empréstimo a partir de renda, histórico e dados do crédito. Aqui o ponto mais rico do projeto está nos **Impactos e Ética**: você vai precisar investigar viés e fairness da sua decisão entre diferentes grupos, um caso concreto, não genérico.
- **Dado:** Loan Approval Prediction Dataset (com CIBIL score, renda, status de emprego, prazo, valor e o status do empréstimo) ou Credit Risk Dataset (renda, intenção do empréstimo, histórico, alvo de inadimplência).
- **Links:**
  - <https://www.kaggle.com/datasets/architsharma01/loan-approval-prediction-dataset>
  - <https://www.kaggle.com/datasets/laotse/credit-risk-dataset>
- **Produto:** Agente de apoio à decisão que avalia a solicitação, explica os critérios usados e devolve a probabilidade com análise de equidade entre grupos, exposto como API e integrado a um formulário ou painel de análise.

---

### Trilha 2 — NLP / classificação de texto (em português)

#### 2.1 Análise de sentimento de avaliações

- **Descrição:** classifique o sentimento ou a nota de uma avaliação de produto escrita em português. É um bom caso para fazer fine-tuning de um modelo já pré-treinado em PT e para enfrentar o desbalanceamento entre notas.
- **Dado:** B2W-Reviews01 (corpus aberto com mais de 130 mil avaliações coletadas na Americanas.com entre janeiro e maio de 2018, com a escala de 1 a 5 estrelas e o rótulo "recomenda a um amigo" (sim/não)) ou as reviews do Olist.
- **Links:**
  - <https://github.com/americanas-tech/b2w-reviews01>
  - Espelho no Hugging Face: <https://huggingface.co/datasets/ruanchaves/b2w-reviews01>
- **Atenção à licença (declare no Data Card):** o B2W-Reviews01 é CC BY-NC-SA 4.0, uso estritamente não comercial. Serve para o trabalho, mas precisa estar declarado.
- **Modelo sugerido:** fine-tune de BERTimbau.
- **Produto:** Agente que classifica o sentimento de uma avaliação, explica o raciocínio e sugere ação (responder, escalar, arquivar), exposto como API e integrado a um widget de ouvidoria ou painel de monitoramento de reviews.

#### 2.2 Moderação / detecção de toxicidade

- **Descrição:** sinalize comentários ofensivos ou de discurso de ódio em português. Pense bem no tratamento de erros: falso positivo silencia pessoas, falso negativo deixa passar o abuso, essa tensão deve aparecer no seu design e no relatório.
- **Dado:** HateBR, primeiro corpus grande anotado por especialistas, com 7.000 comentários do Instagram de políticos brasileiros, em três camadas: ofensivo × não ofensivo, nível de ofensa e alvos de discurso de ódio. Há alternativas em PT também no Hugging Face.
- **Link:** <https://huggingface.co/datasets/franciellevargas/HateBR> (repositório oficial mantido)
- **Atenção à licença (declare no Data Card):** uso estritamente acadêmico e de pesquisa; uso comercial proibido sem autorização.
- **Produto:** Agente moderador que analisa comentários, classifica o nível de ofensa com justificativa auditável e sugere ação (aprovar, sinalizar, bloquear), exposto como API e integrado a um painel de moderação.

---

### Trilha 3 — Recomendação


#### 3.1 Recomendador de filmes

- **Descrição:** recomende filmes a partir do histórico de notas (filtragem colaborativa). Seu maior desafio de sistema vai ser o **cold start**: o que recomendar para um usuário ou item novo, sem histórico?
- **Dado:** MovieLens (GroupLens / Univ. de Minnesota). A versão pequena (ml-latest-small) tem ~100 mil avaliações de 9 mil filmes por 600 usuários; a ml-25m, estável, tem 25 milhões de avaliações. Comece pela pequena.
- **Link:** <https://grouplens.org/datasets/movielens/>
- **Produto:** Agente que recebe um usuário (ou algumas preferências), raciocina sobre o histórico e contexto, e devolve recomendações com explicação, exposto como API e integrado a um app ou interface conversacional de descoberta. A versão brasileira é recomendar produtos sobre o Olist.

---

### Trilha 4 — Proponha uma ideia você mesmo


**Descrição:** escolha um problema que te interessa de verdade (uma dor da sua cidade, da universidade, de um hobby, de um trabalho) e resolva com um sistema de ML em produção. A liberdade é total no tema, mas a régua de saída é a mesma das outras trilhas: problema real, dado com fonte e licença claras, modelo treinado, sistema no ar e confiável. O risco desta trilha é o **escopo**: é fácil sonhar grande e não entregar nada no ar. Pense pequeno e completo, não grande e pela metade.

**Dado:** você é responsável por encontrá-lo. Use os hubs já indicados (Base dos Dados, Kaggle, Hugging Face, Google Dataset Search, dados.gov.br, IBGE, INMET, DataSUS, APIs públicas) ou colete o seu (scraping, API, formulário), desde que documente origem e licença. Antes de se apaixonar pelo problema, confirme que o dado existe e que você consegue acessá-lo.

**Produto:** um agente de IA acessível e demonstrável ao vivo, com lógica de raciocínio sobre o problema, exposto como API e integrado a um produto (bot, frontend ou dashboard). O tipo é livre; o que não muda é que o ciclo completo precisa estar no ar até o Demo Day: agente → API → produto.

**O que aprovar com a equipe docente antes de começar (até o fim da Semana 1):**

- O **problema e os stakeholders** — qual é a dor, de quem é, e por que vale resolver com ML em vez de uma regra simples.
- A **fonte de dados, já verificada** — o link real, a licença e a confirmação de que você consegue baixar/acessar o dado. *Proposta sem dado confirmado não é aprovada.*
- **De onde virão os dados de inferência** com o sistema no ar — o ponto que mais derruba projeto de tema livre. Um CSV estático treina o modelo, mas a sua API precisa receber entradas novas.
- O **escopo cabível em 3 semanas** — um recorte mínimo que funciona, não a visão completa.

---