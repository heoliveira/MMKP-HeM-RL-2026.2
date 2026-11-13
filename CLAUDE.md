# CLAUDE.md — MMKP IoT-EC-CC

Responda em **português (pt-BR)**. O usuário está aprendendo o projeto etapa por etapa: explique o *porquê* de cada passo, curto.
Roteiro e status das etapas: [docs/ROTEIRO.md](docs/ROTEIRO.md) — atualize o status ao concluir uma etapa.

## O que é
Simulador **C++17 header-only** (não é C#) para o MMKP: alocar dispositivos IoT (demanda CPU/MEM/STO, custo de penalidade)
em servidores de Borda (EC, 499) e Nuvem (CC, 1). Objetivo: **minimizar a penalidade dos não atendidos**
(= maximizar penalidade evitada). Fork de `BrunoLRodrigues/MMKP-HeM-RL-2026.2` (disciplina Heurística e Metaheurística, UFMG).

## Mapa de arquivos (leia só o necessário)
| Arquivo | Conteúdo |
|---|---|
| `src/main.cpp` | Parâmetros (`constexpr` no topo), `run_simulation(option)`, laço tamanhos × runs × opções |
| `include/mmkp.hpp` (1267 linhas — use `grep -n` antes de ler) | `core::Device/Server/Supply` (~L28-181), `data::generate/load` (~L188-440), `metrics::*` + CSV (~L444-1050), `display::*` |
| `include/heuristic.hpp` | `greedy_cost_benefit`, `greedy_random`, `greedy_random_fallback`, `boot()` |
| `include/metaheuristic.hpp` | SA: `apply_neighbor` (shift/insert/swap), `revert_neighbor`, `simulated_annealing`, `boot()` |
| `include/exact.hpp` | Modelo ILP no CPLEX (`solver_maximum_cost`) |
| `include/tools.hpp` | CSV, `randomness::random_number` (mt19937 global), `convert`, `sorting` |

**Não ler**: `docs/html/`, `docs/latex/` (Doxygen gerado), `results/Default.xlsm`, arquivos de `data/` inteiros.
Para `results/*/*.txt` (CSV `;`, até 3300 linhas) use `head`, `cut -d';'` ou pandas — nunca leia inteiro.

## Opções de algoritmo (`option` em `run_simulation`)
`0` EXACT (CPLEX) · `-1` GREEDY_CB · `-2` GREEDY_RANDOM · `-3` GREEDY_RANDOM_FALLBACK · `-4` GREEDY_WF (nova) · `1/2/3/4` SA iniciado por CB/R/RF/WF.
GREEDY_WF (worst-fit): ordem de utilidade da GCB, cada dispositivo vai ao servidor viável com **maior** folga residual normalizada. Escolhida em piloto (semente 999, 3 instâncias) entre `tight` e `loose`; a avaliação final usa outra semente.
Adicionar algoritmo = `metrics::Algorithm` + `to_string` (mmkp.hpp) + função e `boot()` (heuristic.hpp) + `option` (main.cpp).

## Build e execução
- CPLEX NÃO está instalado aqui. `./build.sh --no-cplex --no-run` compila só heurísticas + SA (sem `-DUSE_CPLEX`; a opção 0 fica indisponível). Sem a flag, `-DUSE_CPLEX` entra no build. g++ 13.3; sem cmake.
- O binário lê/grava `data/` e `results/` na **pasta atual** (rode numa pasta de experimento). Parâmetros por CLI (`--help`): `--devices-start/step/end --runs --alpha --temperature --fixed-penalty 0|1 --seed --instance --options`. Padrão atual: α=0,999 (como o artigo).
- Experimento completo: `scripts/run_experiment.sh OUT_DIR` (variáveis `INSTANCES RUNS START STEP END ALPHA OPTIONS CPU SEED`), um processo por vez, os dois cenários sobre as mesmas demandas.
- Análise estatística: `.venv/bin/python analysis/analyze.py PASTA_DO_EXPERIMENTO` (venv do projeto com `analysis/requirements.txt`; cria `PASTA/analysis/` com relatório, CSVs e figuras). Não instalar pacotes nem rodar análise durante uma rodada de medição de tempo.
- Teste rápido: `--devices-start 12000 --devices-end 13000 --runs 3` numa pasta nova.

## Armadilhas conhecidas (importantes para a estatística)
1. **Resolvido (Etapa 1):** `data/Services.txt` e `Devices_*.txt` guardam o custo variável e nunca são reescritos; o cenário fixo troca o custo por 1,0 na leitura (`data::load::devices`). Os dois cenários usam as mesmas demandas.
2. **Resolvido (Etapa 1):** `--seed`/`--instance`; cada (instância, tamanho, run, algoritmo) tem seu fluxo via `randomness::mix_seed`. Mesmo comando ⇒ mesmos resultados (exceto `Execution_time`).
3. `results/` e o artigo (Seção 3.5) usam `ALPHA=0.999`; o código atual tem `0.9999`. Medido em 20k variável, 1 processo: SA 0,18–0,66 s (α=0,999) → 1,0–1,8 s (α=0,9999), penalidade 23–25% → 19–20%. Com 0,9999 o SA **estoura a hipótese do artigo (< 1 s)**. Para reproduzir o artigo use 0,999; 0,9999 vira fator de sensibilidade.
8. **Tempo só vale com 1 processo por vez.** Medido (13k, SA, α=0,9999): 1 processo 0,27 s; 8 em paralelo 1,25 s (4,6×); 16 em paralelo 2,6 s (9,5×). O artigo fixa 1 thread só no CPLEX; o C++ não usa threads. Paralelizar serve no máximo para métricas de qualidade (custo), nunca para `Execution_time`. Ganho de vazão medido: ~1,7× com 8 processos.
4. O laço do `main` só roda opções `0..3`; os arquivos `results/HEURISTIC/*` são a solução inicial gravada dentro do SA (run k da heurística ↔ run k do SA). GREEDY_CB é gravado só no run 1.
5. **Mitigado:** o binário recusa rodar se `results/` já existe (`--append` para permitir). No baseline antigo, o EXACT do repo rodou em instância diferente (Max_cost difere).
6. Tempo do SA inclui o tempo da heurística inicial. CPLEX: 1 thread, 3600 s; ≥13k dispositivos termina por tempo (ver `Gap`).
7. Instâncias 10k–11k são triviais (todos atendem 100% → empates nos testes).

## Convenções do código
Indexação **1-based** (posição 0 de `devices`/`servers` é placeholder). Comentários Doxygen bilíngues EN/PT. Namespaces por domínio.
Estilo: `snake_case`, funções `inline` em headers, `std::shared_ptr<metrics::Metrics>` polimórfico em `metrics::Result::stats`.

## Futuro (Python / PyPI)
Pacote Python generalizável (heurísticas/metaheurísticas/cenários/critérios plugáveis) — ver Etapas 6–9 do ROTEIRO.
Estatística: Friedman → Nemenyi + Wilcoxon pareado com Holm (scipy, scikit-posthocs, statsmodels).
