# Roteiro do projeto — do C++ ao pacote no PyPI

Status: `[x]` concluída · `[~]` em andamento · `[ ]` pendente.
Modelo/esforço = recomendação para a sessão do Claude Code daquela etapa (`/model` para trocar).

| # | Etapa | Status | Modelo · esforço |
|---|---|---|---|
| 0 | Leitura do repositório, mapa, infográfico, CLAUDE.md | [x] | Opus 5.5 · médio |
| 1 | Build reprodutível sem CPLEX + semente + parâmetros por CLI | [x] feito em 2026-11-02 (`--no-cplex`, `--seed/--instance`, dados imutáveis, `scripts/run_experiment.sh`) | Sonnet 5.5 · médio |
| 2 | Rodar baseline (fixo e variável) e coletar resultados | [x] feito em 2026-11-02 (α=0,999, 1 processo por vez, via `sed`, sem semente; saída em `~/mmkp-runs/completo_{fixo,variavel}`) | Haiku 5.5 · baixo |
| 3 | Análise descritiva em Python (tabelas, gráficos, gap) | [x] feito dentro de `analysis/analyze.py` (sem gap ao exato: CPLEX indisponível) | Sonnet 5.5 · médio |
| 4 | Nova heurística simples em C++ | [x] feito em 2026-11-02: `GREEDY_WF` (opções `-4` e `4`) | Opus 5.5 · alto (desenho) → Sonnet 5.5 · médio (código) |
| 5 | Desenho experimental e testes (Friedman, Nemenyi, Wilcoxon+Holm) | [x] feito em 2026-11-02, resultados em `~/mmkp-runs/final_s1/analysis/` (ver REGISTRO §9) | Opus 5.5 · alto |
| 6 | Arquitetura do pacote Python | [ ] | Opus 5.5 · muito alto (xhigh) |
| 7 | Port do núcleo + heurísticas + SA, com testes de equivalência | [ ] | Sonnet 5.5 · alto |
| 8 | Generalização: cenários, critérios, solver exato livre | [ ] | Opus 5.5 · alto → Sonnet 5.5 · médio |
| 9 | Empacotamento, CI, docs e publicação (TestPyPI → PyPI) | [ ] | Sonnet 5.5 · médio |
| 10 | Relatório final da disciplina | [ ] | Opus 5.5 · médio |

---

## Etapa 1 — Build reprodutível sem CPLEX
**Por quê:** hoje não compila aqui (sem CPLEX) e cada execução muda as instâncias. Sem isso, nenhum teste estatístico é confiável.
- Guardar `#include "exact.hpp"` e `exact::boot` atrás de `#ifdef USE_CPLEX`; `build.sh --no-cplex`.
- Semente explícita em `randomness::get_engine()` (ex.: `seed = base + run_id`) e gravá-la no CSV.
- Não reescrever `Services.txt`/`Devices_*.txt` quando já existem (gerar um arquivo por cenário fixo/variável).
- Parâmetros por linha de comando (tamanhos, runs, alpha, opções) e diretório de saída por experimento.
- Permitir rodar as heurísticas isoladas (`-1..-3`) sem duplicar linhas.
**Você vai entender:** compilação header-only, RNG, efeitos colaterais de I/O. **Entrega:** binário + `results/<experimento>/`.

## Etapa 2 — Rodar o baseline
11 tamanhos (10k–20k) × 50 runs × {fixo, variável}. **Um processo por vez** (paralelo distorce o tempo, ver CLAUDE.md item 8).
**α = 0,999** (valor do artigo). Estimativa sem CPLEX, a confirmar: ~7–10 min por cenário com α=0,999; ~25 min com α=0,9999.
EXACT: reaproveitar `results/EXACT` (CPLEX, 1 h por instância) **só** no cenário fixo, onde a instância é a mesma.

## Etapa 3 — Análise descritiva
pandas: penalidade normalizada (`Total_cost/Max_cost`), % atendidos, uso EC×CC, tempo; mediana/IQR por instância; gap ao EXACT.

## Etapa 4 — Nova heurística (proposta)
**Feito: `GREEDY_WF` (worst-fit).** Mesma ordem de utilidade da GCB; cada dispositivo vai ao servidor viável com **maior** folga residual normalizada (soma de CPU/MEM/STO restantes ÷ capacidade). O(n log n + n·m), ~20–27 ms em 14k–20k. Piloto (semente 999, 3 instâncias, 5 runs) comparou `tight` (menor folga = best-fit) e `loose` (maior folga): `loose` ganhou em todos os casos, p.ex. fixo 20k: GCB 28,1% → WF 22,6%; SA+GCB 24,7% → SA+WF 21,3%. A proposta inicial (best-fit) perdeu para a GCB.
Alternativas: utilidade dinâmica (recalcular sobre capacidade residual) ou regret-2.

## Etapa 5 — Estatística
- **Blocos** = instâncias (tamanho × cenário × réplica). Gerar ≥5 instâncias por tamanho em 13k–20k → ≥80 blocos.
- **Tratamentos** = algoritmos. **Resposta** = mediana da penalidade normalizada nos runs do bloco.
- Friedman (H0: mesmas distribuições) → se p<0,05: Nemenyi (diagrama de diferença crítica) e Wilcoxon pareado com correção de Holm.
- Tamanho de efeito: W de Kendall (Friedman), rank-biserial pareado (Wilcoxon). α = 0,05.
- Empates (10k–11k) reportados à parte; `zero_method="pratt"` ou excluir.

## Etapas 6–9 — Pacote Python
- Núcleo vetorizado (NumPy; Numba no laço do SA). Interfaces: `Instance`, `Solution`, `Constructive`, `Metaheuristic`, `Criterion`.
- Registro por plugin (entry points) para heurísticas/metaheurísticas; cenários em YAML; `Runner` com sementes; módulo `stats`.
- Solver exato opcional sem licença: HiGHS (`highspy`) ou OR-Tools CP-SAT.
- Equivalência: GREEDY_CB em Python deve reproduzir exatamente o C++ na mesma instância.
- `pyproject.toml` (hatchling), CLI `mmkp run cenario.yaml`, pytest, GitHub Actions, mkdocs, publicação via Trusted Publishing.
