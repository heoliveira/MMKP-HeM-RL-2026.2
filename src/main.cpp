/**
 * @file main.cpp
 * @brief Entry point and benchmark runner for the MMKP IoT-EC-CC resource allocation simulator.
 * @details Defines the experimental parameters (scaling of IoT devices, server counts,
 * CPLEX time limit, and Simulated Annealing cooling schedule) and orchestrates
 * the execution across Exact, Heuristic, and Meta-heuristic paradigms.
 * Every parameter can be overridden on the command line (see `--help`), and all random
 * streams are derived from `--seed`, so the same command always yields the same results.
 */

#include "mmkp.hpp"
#ifdef USE_CPLEX
#include "exact.hpp"
#endif
#include "heuristic.hpp"
#include "metaheuristic.hpp"

constexpr int SERVICES = 100;             ///< @brief Total number of distinct service profiles generated.
constexpr int DEVICES_START = 10000;      ///< @brief Initial number of IoT devices in the scaling benchmark.
constexpr int DEVICES_STEP = 1000;        ///< @brief Increment step for the number of IoT devices per batch.
constexpr int DEVICES_END = 20000;        ///< @brief Maximum number of IoT devices in the scaling benchmark.
constexpr int EC_LENGTH = 499;            ///< @brief Total number of Edge Computing (EC) servers available.
constexpr int CC_LENGTH = 1;              ///< @brief Total number of Cloud Computing (CC) servers available.
constexpr int MAX_RUNS = 50;              ///< @brief Number of independent runs per instance configuration.
constexpr double CPLEX_TIME_LIMIT = 3600; ///< @brief Time limit in seconds for the CPLEX exact solver.
constexpr double TEMPERATURE = 50.0;      ///< @brief Initial temperature for Simulated Annealing.
constexpr double ALPHA = 0.999;           ///< @brief Geometric cooling factor for Simulated Annealing (value used in the paper).
constexpr bool FIXED_PENALTY = false;     ///< @brief Whether the penalty (cost) of each device is fixed or can vary.

/**
 * @brief Experiment parameters; the defaults are the constants above and `--name value` overrides them.
 */
struct Config {
    int services = SERVICES;                ///< @brief `--services`: number of service profiles.
    int devices_start = DEVICES_START;      ///< @brief `--devices-start`: first instance size.
    int devices_step = DEVICES_STEP;        ///< @brief `--devices-step`: increment between sizes.
    int devices_end = DEVICES_END;          ///< @brief `--devices-end`: last instance size.
    int ec = EC_LENGTH;                     ///< @brief `--ec`: number of Edge servers.
    int cc = CC_LENGTH;                     ///< @brief `--cc`: number of Cloud servers.
    int runs = MAX_RUNS;                    ///< @brief `--runs`: independent runs per size.
    double temperature = TEMPERATURE;       ///< @brief `--temperature`: initial SA temperature.
    double alpha = ALPHA;                   ///< @brief `--alpha`: SA cooling factor.
    bool fixed_penalty = FIXED_PENALTY;     ///< @brief `--fixed-penalty 0|1`: unit penalty for every device.
    std::uint64_t seed = 1;                 ///< @brief `--seed`: master seed of the whole experiment.
    int instance = 1;                       ///< @brief `--instance`: instance id; each id gets its own data/ and random streams.
    bool append = false;                    ///< @brief `--append`: allow writing into an existing `results/` directory.
    std::vector<int> options;               ///< @brief `--options 1,2,3`: algorithm options to run (see `run_simulation`).
};

/// @brief Identifies which random stream a seed belongs to (see `randomness::mix_seed`).
enum SeedTag { TAG_SERVICES = 1, TAG_SERVERS = 2, TAG_DEVICES = 3, TAG_RUN = 4 };

/**
 * @brief Parses `--name value` pairs into a `Config`.
 * @param argc Argument count from `main`.
 * @param argv Argument vector from `main`.
 * @param cfg The configuration to fill (starts with the defaults).
 * @return `false` if an argument is unknown or `--help` was requested.
 */
bool parse_args(int argc, char** argv, Config& cfg) {
    for (int i = 1; i < argc; i++) {
        std::string key = argv[i];
        if (key == "--append") { cfg.append = true; continue; }
        if (key == "--help" || i + 1 >= argc) {
            std::cerr << "Usage: " << argv[0] << " [--devices-start N] [--devices-step N] [--devices-end N]\n"
                      << "          [--services N] [--ec N] [--cc N] [--runs N] [--alpha X] [--temperature X]\n"
                      << "          [--fixed-penalty 0|1] [--seed N] [--instance N] [--options 1,2,3] [--append]\n"
                      << "Run it from the experiment folder: data/ and results/ are relative to the current directory.\n";
            return false;
        }
        std::string value = argv[++i];
        try {
            if (key == "--services") cfg.services = std::stoi(value);
            else if (key == "--devices-start") cfg.devices_start = std::stoi(value);
            else if (key == "--devices-step") cfg.devices_step = std::stoi(value);
            else if (key == "--devices-end") cfg.devices_end = std::stoi(value);
            else if (key == "--ec") cfg.ec = std::stoi(value);
            else if (key == "--cc") cfg.cc = std::stoi(value);
            else if (key == "--runs") cfg.runs = std::stoi(value);
            else if (key == "--alpha") cfg.alpha = std::stod(value);
            else if (key == "--temperature") cfg.temperature = std::stod(value);
            else if (key == "--fixed-penalty") cfg.fixed_penalty = (std::stoi(value) != 0);
            else if (key == "--seed") cfg.seed = std::stoull(value);
            else if (key == "--instance") cfg.instance = std::stoi(value);
            else if (key == "--options") {
                cfg.options.clear();
                std::stringstream ss(value);
                std::string item;
                while (std::getline(ss, item, ',')) cfg.options.push_back(std::stoi(item));
            } else {
                std::cerr << "Error: unknown argument " << key << "\n";
                return false;
            }
        } catch (const std::exception&) {
            std::cerr << "Error: invalid value '" << value << "' for " << key << "\n";
            return false;
        }
    }
    if (cfg.options.empty()) {
#ifdef USE_CPLEX
        cfg.options = {0, 1, 2, 3, 4};
#else
        cfg.options = {1, 2, 3, 4};
#endif
    }
    return true;
}

/**
 * @brief Records the parameters of this execution in `params.txt` (current directory).
 * @param cfg The configuration in use.
 * @param argc Argument count from `main`.
 * @param argv Argument vector from `main`.
 */
void write_params(const Config& cfg, int argc, char** argv) {
    std::ofstream out("params.txt");
    out << "command=";
    for (int i = 0; i < argc; i++) out << argv[i] << (i + 1 < argc ? " " : "");
    out << "\nservices=" << cfg.services << "\ndevices_start=" << cfg.devices_start
        << "\ndevices_step=" << cfg.devices_step << "\ndevices_end=" << cfg.devices_end
        << "\nec=" << cfg.ec << "\ncc=" << cfg.cc << "\nruns=" << cfg.runs
        << "\ntemperature=" << cfg.temperature << "\nalpha=" << cfg.alpha
        << "\nfixed_penalty=" << cfg.fixed_penalty << "\nseed=" << cfg.seed
        << "\ninstance=" << cfg.instance << "\noptions=" << convert::vector_to_string(cfg.options) << "\n";
}

/**
 * @brief Executes a specific algorithm configuration for the network resource allocation simulation.
 * @details Instantiates the appropriate metrics tracker based on the selected option, dispatches
 * the simulation state to the corresponding solver paradigm (Exact, Heuristic, or Meta-heuristic),
 * computes final utilization/cost metrics, and saves the results to disk.
 *
 * @param base The initial system state containing untouched devices and servers.
 * @param option The identifier for the algorithm combination to execute:
 *               - `0`: Exact CPLEX solver (`solver_maximum_cost`, needs a build with `-DUSE_CPLEX`)
 *               - `-1`: Constructive heuristic (`greedy_cost_benefit`)
 *               - `-2`: Constructive heuristic (`greedy_random`)
 *               - `-3`: Constructive heuristic (`greedy_random_fallback`)
 *               - `-4`: Constructive heuristic (`greedy_worst_fit`)
 *               - `1`: Simulated Annealing + `greedy_cost_benefit`
 *               - `2`: Simulated Annealing + `greedy_random`
 *               - `3`: Simulated Annealing + `greedy_random_fallback`
 *               - `4`: Simulated Annealing + `greedy_worst_fit`
 * @param run_id The current execution run number (1-indexed).
 * @param cfg The experiment configuration (SA temperature and cooling factor).
 */
void run_simulation(const metrics::Result& base, int option, int run_id, const Config& cfg) {
    metrics::Paradigm paradigm = metrics::Paradigm::NONE;
    metrics::Algorithm algorithm = metrics::Algorithm::NONE;
    metrics::Algorithm initial_heuristic = metrics::Algorithm::NONE;

    if (option == 0) {
#ifndef USE_CPLEX
        std::cerr << "Error: option 0 (CPLEX) needs a build with -DUSE_CPLEX.\n";
        return;
#endif
        paradigm = metrics::Paradigm::EXACT;
        algorithm = metrics::Algorithm::solver_maximum_cost;
    } else if (option == -1) {
        paradigm = metrics::Paradigm::HEURISTIC;
        algorithm = metrics::Algorithm::greedy_cost_benefit;
    } else if (option == -2) {
        paradigm = metrics::Paradigm::HEURISTIC;
        algorithm = metrics::Algorithm::greedy_random;
    } else if (option == -3) {
        paradigm = metrics::Paradigm::HEURISTIC;
        algorithm = metrics::Algorithm::greedy_random_fallback;
    } else if (option == -4) {
        paradigm = metrics::Paradigm::HEURISTIC;
        algorithm = metrics::Algorithm::greedy_worst_fit;
    } else if (option == 1) {
        paradigm = metrics::Paradigm::METAHEURISTIC;
        algorithm = metrics::Algorithm::simulated_annealing;
        initial_heuristic = metrics::Algorithm::greedy_cost_benefit;
    } else if (option == 2) {
        paradigm = metrics::Paradigm::METAHEURISTIC;
        algorithm = metrics::Algorithm::simulated_annealing;
        initial_heuristic = metrics::Algorithm::greedy_random;
    } else if (option == 3) {
        paradigm = metrics::Paradigm::METAHEURISTIC;
        algorithm = metrics::Algorithm::simulated_annealing;
        initial_heuristic = metrics::Algorithm::greedy_random_fallback;
    } else if (option == 4) {
        paradigm = metrics::Paradigm::METAHEURISTIC;
        algorithm = metrics::Algorithm::simulated_annealing;
        initial_heuristic = metrics::Algorithm::greedy_worst_fit;
    } else {
        std::cerr << "Error: Invalid option selected for simulation.\n";
        return;
    }

    metrics::Result state = base;

    if (paradigm == metrics::Paradigm::EXACT) {
        state.stats = std::make_shared<metrics::ExactMetrics>(algorithm, run_id, base.stats);
    } else if (paradigm == metrics::Paradigm::HEURISTIC) {
        state.stats = std::make_shared<metrics::HeuristicMetrics>(algorithm, run_id, base.stats);
    } else if (paradigm == metrics::Paradigm::METAHEURISTIC) {
        state.stats = std::make_shared<metrics::MetaHeuristicMetrics>(algorithm, run_id, base.stats, cfg.temperature, cfg.alpha, initial_heuristic);
    }

    if (paradigm == metrics::Paradigm::EXACT) {
#ifdef USE_CPLEX
        exact::boot(state, CPLEX_TIME_LIMIT);
#endif
    } else if (paradigm == metrics::Paradigm::HEURISTIC) {
        heuristic::boot(state);
    } else if (paradigm == metrics::Paradigm::METAHEURISTIC) {
        metaheuristic::boot(state);
    }

    metrics::calculate_metrics(state);
    metrics::save_results(state, false);
}

/**
 * @brief Main entry point for the network resource allocation simulation benchmark.
 * @details Iterates over the configured range of device counts and independent runs,
 * executing deterministic algorithms once per instance and stochastic algorithms across
 * all runs. Instance data (services, servers, devices) and every run use random streams
 * derived from `(seed, instance, ...)`, so results are reproducible.
 *
 * @param argc Argument count (see `parse_args` for the accepted options).
 * @param argv Argument vector.
 * @return int Exit status code (`0` on normal termination, `1` on invalid arguments or an existing `results/`).
 */
int main(int argc, char** argv) {
    Config cfg;
    if (!parse_args(argc, argv, cfg)) return 1;

    if (!cfg.append && std::filesystem::exists(metrics::RESULTS_PATH)) {
        std::cerr << "Error: " << metrics::RESULTS_PATH << " already exists; results are appended, so use a new folder (or pass --append).\n";
        return 1;
    }
    write_params(cfg, argc, argv);

    // Services and servers belong to the instance, not to a size: generate them once, with their own seeds.
    randomness::seed(randomness::mix_seed(cfg.seed, cfg.instance, TAG_SERVICES));
    data::generate::services(cfg.services, cfg.fixed_penalty);
    randomness::seed(randomness::mix_seed(cfg.seed, cfg.instance, TAG_SERVERS));
    data::generate::servers(cfg.ec, cfg.cc);

    for (int devices_length = cfg.devices_start; devices_length <= cfg.devices_end; devices_length += cfg.devices_step) {
        randomness::seed(randomness::mix_seed(cfg.seed, cfg.instance, TAG_DEVICES, devices_length));
        metrics::Result base_state(devices_length, cfg.services, cfg.ec, cfg.cc, cfg.fixed_penalty);

        for (int run = 1; run <= cfg.runs; run++) {
            for (int option : cfg.options) {
                if (run > 1 && (option == 0 || option == -1 || option == -4)) continue;
                randomness::seed(randomness::mix_seed(cfg.seed, cfg.instance, TAG_RUN, devices_length, run, option));
                run_simulation(base_state, option, run, cfg);
            }
        }
    }

    return 0;
}
