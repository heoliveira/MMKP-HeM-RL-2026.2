# Glossário

## O problema

| Sigla | Significa | Em uma frase |
|---|---|---|
| IoT | Internet of Things | Os dispositivos que pedem serviço (sensores, câmeras, carros). |
| EC | Edge Computing (computação de borda) | 499 servidores pequenos, perto dos dispositivos. |
| CC | Cloud Computing (computação em nuvem) | 1 servidor enorme, longe dos dispositivos. |
| MMKP | Multiple Multidimensional Knapsack Problem | Colocar itens (dispositivos) em várias mochilas (servidores) respeitando 3 recursos: CPU, memória e armazenamento. |
| SLA | Service Level Agreement | Contrato de serviço: quem não é atendido gera multa. |
| Penalidade | Multa por dispositivo não atendido | É o que queremos minimizar. Nos gráficos aparece como % do máximo possível. |
| OPEX | Operational Expenditure | Custo operacional; aqui, o total de multas. |

## Os algoritmos (como aparecem nos resultados)

Uma **heurística** é uma regra rápida que monta uma solução. Uma **meta-heurística** é uma estratégia que pega uma solução pronta e tenta melhorá-la várias vezes.

| Sigla | Nome completo | O que faz |
|---|---|---|
| GR | Greedy Random | Para cada dispositivo, sorteia um dos 500 servidores. Se não couber, ele fica sem atendimento. É a **baseline** (o ponto de comparação mais fraco). |
| GRF | Greedy Random with Fallback | Sorteia um servidor de borda; se não couber, sorteia a nuvem. |
| GCB | Greedy Cost Benefit | Ordena os dispositivos por custo ÷ demanda (os mais "valiosos por recurso" primeiro) e vai enchendo os servidores um a um, na ordem do índice. Determinística. |
| WF | Worst Fit (**a heurística nova**) | Mesma ordem da GCB, mas cada dispositivo vai para o servidor viável onde **sobraria mais folga**. Determinística. O nome vem do empacotamento: "pior encaixe" = o recipiente com mais espaço sobrando. |
| SA | Simulated Annealing (recozimento simulado) | Parte de uma solução e testa pequenas mudanças (mover, inserir, trocar um dispositivo). Aceita sempre as que melhoram e, às vezes, as que pioram, com uma probabilidade que diminui ao longo da busca. Isso ajuda a sair de soluções "travadas". O nome vem da metalurgia, mas na prática é só essa regra de aceitação. |
| SAGR, SAGRF, SAGCB, SAWF | SA começando da GR, GRF, GCB ou WF | É o mesmo SA; muda só a solução inicial. |
| ILP | Integer Linear Programming | O método exato (CPLEX), que acha o ótimo ou chega perto, mas demora até horas. Não rodamos nas instâncias novas. |

## Termos dos testes estatísticos

| Termo | Significa |
|---|---|
| Bloco | Uma instância de um certo tamanho, onde todos os algoritmos rodam. Comparar dentro do bloco é justo. |
| Friedman | Teste que responde: existe alguma diferença entre os algoritmos? |
| Wilcoxon pareado | Compara dois algoritmos nos mesmos blocos. |
| Holm | Correção que evita falsos positivos quando se fazem muitas comparações. |
| Nemenyi / CD | Comparação por ranks; o diagrama de diferença crítica (CD) mostra quais algoritmos não se distinguem. |
| p-valor | O quanto os dados seriam surpreendentes se não houvesse diferença real. Pequeno (< 0,05) indica diferença. |
| Tamanho de efeito | O quanto a diferença importa na prática, não só se é detectável. |
| α (alfa) | Duas coisas diferentes, cuidado: no **SA** é a velocidade de resfriamento (0,999); nos **testes** é o nível de significância (0,05). |
