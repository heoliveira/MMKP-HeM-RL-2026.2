# Registro do trabalho (local; nada foi commitado nem publicado no git)

Data de início: 2026-11-02. Este arquivo é atualizado ao final de cada bloco de trabalho.

## 1. Arquivos alterados (código e scripts existentes)

| Arquivo | O que mudou | Por quê |
|---|---|---|
| `include/tools.hpp` | + `randomness::seed()`, `randomness::mix_seed()`, `#include <cstdint>` | Semente reproduzível por (instância, tamanho, execução, algoritmo) |
| `include/mmkp.hpp` | `data::generate::services/devices` não reescrevem mais arquivos existentes; custo fixo (1,0) aplicado em `data::load::devices`; + `Algorithm::greedy_worst_fit` e nome `GREEDY_WF` | Instâncias imutáveis; os dois cenários usam as mesmas demandas |
| `include/heuristic.hpp` | + `greedy_worst_fit` e despacho em `boot()` | Heurística nova (Etapa 4) |
| `include/metaheuristic.hpp` | Heurística inicial determinística (GCB e WF) só é gravada no run 1 | Evita 50 linhas idênticas |
| `src/main.cpp` | Reescrito: parâmetros por CLI, sementes derivadas, `params.txt`, recusa `results/` existente, CPLEX só com `-DUSE_CPLEX`, opções `-4` e `4`, α padrão 0,999 | Etapa 1 e 4 |
| `build.sh` | + `--no-cplex`, `--no-run`; build com CPLEX passa `-DUSE_CPLEX` | Compilar sem `sed` |
| `CMakeLists.txt` | + `USE_CPLEX` nas definições | Mantém o build com CPLEX |
| `README.md`, `README.pt-BR.md` | + linhas `-4` e `4` na tabela de algoritmos | Documentação |
| `.gitignore` | + `.venv/`, `__pycache__/`, `*.pyc` | Ambiente Python |

## 2. Arquivos novos

`CLAUDE.md`, `docs/ROTEIRO.md`, `docs/REGISTRO.md` (este), `docs/GLOSSARIO.md`, `scripts/run_experiment.sh`, `analysis/analyze.py`, `analysis/requirements.txt`, `.venv/` (ignorado pelo git).

## 3. Mudanças de comportamento que você precisa saber

- `./build.sh` (sem flags) na raiz agora **recusa rodar** porque `results/` já existe. Use `./build.sh --no-cplex --no-run` e rode numa pasta de experimento.
- O α padrão do código passou de 0,9999 para **0,999** (valor do artigo).
- As opções padrão agora incluem `4` (SA a partir da WF).
- `Services.txt` e `Devices_*.txt` guardam sempre custo variável e nunca são reescritos.
- **O build com CPLEX não foi compilado** (CPLEX ausente). A mudança é só `-DUSE_CPLEX`.
- `./build.sh -b` apaga o conteúdo de `build/` (era só descartável).

## 4. Decisões tomadas e motivos

| # | Decisão | Motivo |
|---|---|---|
| D1 | α = 0,999 | Valor do artigo; com 0,9999 o SA passa de 1 s em 20k (medido: 1,0–1,8 s) e quebra a hipótese |
| D2 | Um processo por vez, fixado no núcleo 2 (`taskset`) | Em paralelo o tempo piorou 4,6× (8 proc.) e 9,5× (16 proc.) |
| D3 | Dados imutáveis, cenário fixo aplicado na leitura | Reprodutibilidade; mesmas demandas nos dois cenários, como no artigo |
| D4 | Semente = `mix_seed(seed, instância, tag, tamanho, run, opção)` | Cada execução tem fluxo próprio e repetível |
| D5 | Heurística nova = `GREEDY_WF` (worst-fit) | Piloto (semente 999, 3 inst., 5 runs): `loose` (WF) ganhou da `tight` (best-fit, minha proposta inicial) em todos os casos |
| D6 | Rodada final: semente 1, 10 instâncias, tamanhos 12k–20k passo 2k, 50 runs, 2 cenários | Tamanhos do artigo; 100 blocos (10×5×2) para os testes |
| D7 | Estatística: blocos = (instância, tamanho); resposta = média das execuções; Friedman, Nemenyi, Wilcoxon pareado em 28 pares com Holm; α = 0,05 | Protocolo de Demšar; Holm sobre todos os pares é o mais conservador |
| D8 | Ambiente Python (`.venv`) só depois da rodada terminar | Instalar pacotes durante a rodada poderia distorcer os tempos |
| D9 | ~~Nada commitado, nada publicado~~ Revisto em 2026-11-13: commit e push na branch `wf-experimentos` do fork no GitHub (nunca no GitLab da Hemominas) | Pedido do usuário |
| D10 | **Decidido pelo usuário:** não rodar o CPLEX (sem licença) e não testar sensibilidade a α = 0,9999 | O paper foca em tempo < 1 s. Consequência: nas instâncias novas não há limite exato; a comparação com o ótimo continua valendo só com os dados antigos do repositório (cenário fixo) |
| D11 | Análise de robustez com um bloco por instância (n = 10) e Holm sobre 4 pares planejados | Os tamanhos de uma instância compartilham serviços e servidores (blocos não totalmente independentes); com n = 10 o menor p possível é 2/2^10 e Holm em 28 pares nunca daria significância |

## 5. Rodadas executadas

| Rodada | Onde | Parâmetros | Observação |
|---|---|---|---|
| Baseline antigo | `~/mmkp-runs/completo_fixo`, `completo_variavel` | 11 tamanhos, 50 runs, α=0,999, 1 instância, sem semente | Reproduz o artigo; custo variável não é reprodutível (instância re-sorteada) |
| Piloto da WF | `scratchpad/pilot/out_tight`, `out_loose` (temporário) | semente 999, 3 inst., 14k/17k/20k, 5 runs | Base da decisão D5 |
| Final | `~/mmkp-runs/final_s1` | semente 1, 10 inst., 12k–20k passo 2k, 50 runs, α=0,999 | Concluída 22:19 (28 min 41 s). 20 pastas, contagens exatas, 0 erros nos logs. Análise em `final_s1/analysis/` |

## 6. Pendências e decisões para você

1. Combinar com o grupo se a WF e os testes estatísticos entram no paper (eles vão além do PDF).
2. ~~CPLEX na instância nova~~ Decidido: não (sem licença).
3. ~~Sensibilidade ao α~~ Decidido: não (foco em tempo < 1 s).
4. Commit: aguardando sua instrução.
5. Suas dúvidas conceituais (siglas, analogia do metal) e a conversa sobre o Python.

## 7. Como reproduzir

```bash
./build.sh --no-cplex --no-run
scripts/run_experiment.sh ~/mmkp-runs/final_s1          # ~1 h, um processo por vez
python analysis/analyze.py ~/mmkp-runs/final_s1          # precisa do .venv (analysis/requirements.txt)
```

## 8. Alterações feitas depois da rodada final (script `analysis/analyze.py`)

1. **Bug corrigido:** a direção das frases ("A é melhor que B") era decidida pelo sinal da mediana das diferenças. Com muitos empates a mediana vale 0 e o sinal virava aleatório (a frase "SAGRF melhor que SAWF" no cenário variável estava invertida). Agora a direção vem do efeito rank-biserial, e o relatório mostra também a diferença média.
2. Compatibilidade com matplotlib 3.11 (`boxplot(labels=...)` removido).
3. Diagrama de diferença crítica: barras de grupos agora ficam logo abaixo do eixo (antes a 5ª era cortada).
4. Novo gráfico `fig_diferenca_vs_gcb.png` (diferença pareada para a GCB, IC 95%).
5. Formatação numérica (3 algarismos significativos) e tamanhos como inteiros no texto.
6. **Matriz de vitórias-empates-derrotas** (`fig_vitorias.png` e seção no relatório), com `*` nos pares significativos no Wilcoxon + Holm e conferência de direção: 28/28 (fixo) e 25/25 (variável) concordam.

## 9. Resultados da rodada final (resumo; detalhes em `final_s1/analysis/relatorio.md`)

- Friedman: há diferença entre os 8 algoritmos nos dois cenários (fixo: χ²=277,6, W=0,79; variável: χ²=231,6, W=0,66).
- **Custo fixo:** WF melhor que GCB em todas as 10 instâncias (diferença média 2,3 p.p.; p_Holm 9,5e-7 com 50 blocos e 0,0078 com 10 instâncias). SAWF melhor que os outros três SA em 10/10 instâncias (1,7 a 2,1 p.p.).
- **Custo variável:** WF melhor que GCB com 50 blocos (p_Holm 3,4e-4; média 1,13 p.p.), mas **não robusto** com 10 instâncias (8/10; p_Holm 0,059). SAWF melhor que SAGCB de forma robusta (10/10); contra SAGR e SAGRF a diferença é pequena (0,23 a 0,24 p.p.) e não robusta (7/10; p_Holm 0,26). Em 18k e 20k a SAWF e a SAGRF são praticamente iguais.
- **Significativo não é importante:** no custo fixo todos os 28 pares são significativos, inclusive SAGR x SAGRF (diferença média 0,012 p.p.).
- **Tempo:** todas as execuções abaixo de 1 s, exceto 1 de 2500 do SAGRF no cenário variável (1,12 s). SAWF/SAGCB: mediana 0,04 s, máximo 0,13 s e 0,22 s no variável; SAGR/SAGRF no variável: mediana 0,21 s (5 vezes mais lentos que SAWF).

## 10. Material para o grupo

- Página de apresentação (privada, hospedada fora do git): https://claude.ai/artifact/7UKbu8C2NbXahjPmgQSTSt
- Cópia local autocontida: `~/mmkp-runs/final_s1/analysis/apresentacao.html`
- Relatório completo: `~/mmkp-runs/final_s1/analysis/relatorio.md`
- Nada foi commitado nem enviado ao git.

## 11. Texto do artigo para a WF e a SAWF

- Arquivo `docs/WF_SAWF_paper.tex` (texto, pseudocódigo, pacotes e referências em blocos separados). Compila: testado com `algpseudocode` (CTAN, numa pasta temporária fora do repositório) e o ambiente `algorithm` simulado com `float`; o pacote `algorithm` em si não pôde ser testado.
- Pendente de conversa (não alterado): os trechos do artigo que ainda citam três heurísticas, o comentário do Algoritmo 5 ("GR, GRF ou GCB") e a Tabela 11.
- Referências a conferir: páginas de Coffman et al. (1996) e se Johnson (1974) e Mommessin et al. (2025) tratam o worst-fit explicitamente.
- PDF de pré-visualização: `docs/WF_SAWF_paper.pdf` (estilo genérico, não o template SBC) e `docs/WF_SAWF_refs.bib`.
