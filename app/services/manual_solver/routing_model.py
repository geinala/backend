
from __future__ import annotations

import math
import random
import time
from collections import deque
from datetime import datetime
from typing import Deque, List, Tuple, Union
from typing_extensions import Unpack
from .types import (
    Assignment, 
    OptimizationEvent, 
    RoutingSearchParameters, 
    LocalSearchMetaheuristic, 
    FirstSolutionStrategy, 
    LocalImprovementStrategy,
    ManualSolverProblem
)

# Type Aliasing
TwoOptMove = Tuple[int, int]
OrOptMove  = Tuple[str, int, int, int]
MoveKey    = Union[TwoOptMove, OrOptMove]
Candidate  = Tuple[float, MoveKey, List[int]]

class RoutingModel:
    def __init__(self, problem: ManualSolverProblem) -> None:
        distance_matrix = problem.distance_matrix
        time_matrix = problem.time_matrix
        depot = problem.depot

        if len(distance_matrix) != len(time_matrix):
            raise ValueError("Distance matrix and time matrix must be of the same size.")
        if len(distance_matrix) < 2:
            raise ValueError("Matrices must be at least 2×2 in size.")
            
        self.distance_matrix = distance_matrix
        self.time_matrix = time_matrix
        self.num_nodes = len(distance_matrix)
        self.depot = depot

    def SolveWithParameters(self, params: RoutingSearchParameters) -> Assignment:
        if params.optimization_target == "distance":
            self.cost_matrix = self.distance_matrix
        else:
            self.cost_matrix = self.time_matrix

        if params.local_search_metaheuristic == LocalSearchMetaheuristic.TABU_SEARCH:
            if self.num_nodes < 3:
                raise ValueError("Tabu Search requires at least 3 nodes.")
            return self._solve_tabu_search(params)

        return self._solve_greedy(params)

    def _get_metrics(self, tour: List[int]) -> Tuple[float, float, float]:
        cost = _tour_cost(tour, self.cost_matrix)
        dist = _tour_cost(tour, self.distance_matrix)
        time_val = _tour_cost(tour, self.time_matrix)
        return cost, dist, time_val

    # Helper function untuk membuat object log dengan nilai default TSP
    def _create_event(self, **kwargs: Unpack[OptimizationEvent]) -> OptimizationEvent:
        defaults: OptimizationEvent = {
            "timestamp": datetime.now(),
            "active_routes_count": 1,
            "unassigned_nodes_count": 0
        }
        defaults.update(kwargs)
        return OptimizationEvent(**defaults)

    def _solve_greedy(self, params: RoutingSearchParameters) -> Assignment:
        t0 = time.perf_counter()
        logs: List[OptimizationEvent] = []

        if params.first_solution_strategy == FirstSolutionStrategy.NEAREST_NEIGHBOR:
            best_tour = _nearest_neighbor_tsp(self.cost_matrix)
            algo_name = "Nearest Neighbor"
        elif params.first_solution_strategy == FirstSolutionStrategy.GREEDY_EDGE_INSERTION:
            best_tour = _greedy_edge_tsp(self.cost_matrix)
            algo_name = "Greedy Edge Insertion"
        else:
            tour_nn = _nearest_neighbor_tsp(self.cost_matrix)
            tour_ge = _greedy_edge_tsp(self.cost_matrix)
            if _tour_cost(tour_nn, self.cost_matrix) <= _tour_cost(tour_ge, self.cost_matrix):
                best_tour, algo_name = tour_nn, "Nearest Neighbor (Auto)"
            else:
                best_tour, algo_name = tour_ge, "Greedy Edge (Auto)"

        best_tour = _rotate_to_depot(best_tour, self.depot)
        best_cost, best_dist, best_time = self._get_metrics(best_tour)
        
        logs.append(self._create_event(
            event_type="NEW_BEST", iteration=0, elapsed_ms=round((time.perf_counter() - t0)*1000, 3),
            current_distance_in_meters=best_dist, current_duration_in_seconds=best_time,
            best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
            objective_value=best_cost, operator_used=algo_name, is_new_best=True,
            message=f"Initial solution constructed using {algo_name}.",
            intermediate_tour=best_tour[:] if params.save_intermediate_solutions else None
        ))

        iters = 0
        if params.local_improvement_strategy == LocalImprovementStrategy.TWO_OPT:
            prev_cost, prev_dist, prev_time = best_cost, best_dist, best_time
            best_tour, iters = _two_opt_improve(
                best_tour, self.cost_matrix, params.max_improvement_iterations, t0, params.max_execution_time_seconds
            )
            best_tour = _rotate_to_depot(best_tour, self.depot)
            best_cost, best_dist, best_time = self._get_metrics(best_tour)
            algo_name += " + 2-opt"
            
            logs.append(self._create_event(
                event_type="REOPTIMIZATION_COMPLETE", iteration=iters, elapsed_ms=round((time.perf_counter() - t0)*1000, 3),
                current_distance_in_meters=best_dist, current_duration_in_seconds=best_time,
                best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
                distance_improvement_in_meters=max(0, prev_dist - best_dist),
                duration_improvement_in_seconds=max(0, prev_time - best_time),
                improvement_percent=((prev_cost - best_cost) / prev_cost * 100) if prev_cost > 0 else 0,
                objective_value=best_cost, operator_used="2-opt", is_new_best=(best_cost < prev_cost),
                message="Reoptimization complete using 2-opt.",
                intermediate_tour=best_tour[:] if params.save_intermediate_solutions else None
            ))

        return Assignment(
            tour=best_tour, total_distance_in_meters=best_dist, total_duration_in_seconds=best_time,
            algorithm_used=algo_name, elapsed_ms=round((time.perf_counter() - t0)*1000, 3),
            iterations=iters, logs=logs
        )

    def _solve_tabu_search(self, params: RoutingSearchParameters) -> Assignment:
        t0 = time.perf_counter()
        rng = random.Random(params.random_seed)
        n = self.num_nodes
        logs: List[OptimizationEvent] = []

        # --- Solusi Awal ---
        starts = min(n, 5) if params.first_solution_strategy == FirstSolutionStrategy.AUTOMATIC else 1
        best_tour, best_cost = [], float("inf")
        for s in range(starts):
            t = _nearest_neighbor_init(self.cost_matrix, start=s)
            c = _tour_cost(t, self.cost_matrix)
            if c < best_cost: best_cost, best_tour = c, t[:]

        _, best_dist, best_time = self._get_metrics(best_tour)
        algo_name = "Nearest Neighbor + Tabu Search"
        history: List[float] = [best_cost]
        
        logs.append(self._create_event(
            event_type="NEW_BEST", iteration=0, elapsed_ms=round((time.perf_counter() - t0)*1000, 3),
            current_distance_in_meters=best_dist, current_duration_in_seconds=best_time,
            best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
            objective_value=best_cost, operator_used="Multi-start Nearest Neighbor", is_new_best=True,
            message="Initial solution found.", intermediate_tour=best_tour[:] if params.save_intermediate_solutions else None
        ))

        tenure = params.tabu_tenure if params.tabu_tenure is not None else max(7, int(math.sqrt(n)))
        tabu = _TabuList(tenure=tenure)

        current_tour, current_cost = best_tour[:], best_cost
        no_improve_count, global_no_improve_count = 0, 0
        iters_run = 0

        for idx_iter in range(1, params.max_local_search_iterations + 1):
            iters_run = idx_iter
            
            # Ekstraksi waktu berjalan
            cur_ms = round((time.perf_counter() - t0) * 1000, 3)
            
            # Pengecekan Batas Waktu & Iterasi
            if (time.perf_counter() - t0) > params.max_execution_time_seconds:
                logs.append(self._create_event(
                    event_type="PERIODIC_LOG", iteration=idx_iter, elapsed_ms=cur_ms,
                    current_distance_in_meters=best_dist, current_duration_in_seconds=best_time,
                    best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
                    iterations_without_improvement=global_no_improve_count,
                    message=f"Execution stopped: Maximum execution time reached ({params.max_execution_time_seconds} seconds)."
                ))
                break

            if global_no_improve_count >= params.early_stop_no_improvement_iterations:
                logs.append(self._create_event(
                    event_type="PERIODIC_LOG", iteration=idx_iter, elapsed_ms=cur_ms,
                    current_distance_in_meters=best_dist, current_duration_in_seconds=best_time,
                    best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
                    iterations_without_improvement=global_no_improve_count,
                    message = f"Early Stop: No improvement for {global_no_improve_count} consecutive iterations."
                ))
                break

            # Diversifikasi
            if no_improve_count >= params.diversify_after_iterations:
                div_tour = current_tour[:]
                for _ in range(params.diversification_strength): div_tour = _double_bridge(div_tour, rng)
                
                current_tour = div_tour
                current_cost = _tour_cost(current_tour, self.cost_matrix)
                tabu.clear()
                no_improve_count = 0
                
                cur_c, cur_d, cur_t = self._get_metrics(current_tour)
                logs.append(self._create_event(
                    event_type="DIVERSIFICATION", iteration=idx_iter, elapsed_ms=cur_ms,
                    current_distance_in_meters=cur_d, current_duration_in_seconds=cur_t,
                    best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
                    objective_value=cur_c, operator_used="Double-Bridge", triggered_diversification=True,
                    message=f"Diversification triggered: Applied Double-Bridge perturbation ×{params.diversification_strength}."
                ))

            # Ekspansi Neighborhood
            candidates = _generate_2opt_moves(current_tour, self.cost_matrix, params.max_neighbors_2opt)
            if params.use_oropt_neighborhood:
                oropt = _generate_oropt_moves(current_tour, self.cost_matrix, current_cost, params.max_neighbors_oropt)
                candidates = sorted(candidates + oropt, key=lambda x: x[0])

            chosen_tour, chosen_cost, chosen_move = None, float("inf"), None
            used_aspiration = False

            for _, move_key, new_tour in candidates:
                new_cost = _tour_cost(new_tour, self.cost_matrix)
                tabu_key = _normalize_move_key(move_key)

                if tabu.is_tabu(tabu_key):
                    if params.enable_aspiration and (new_cost < best_cost):
                        used_aspiration = True
                    else:
                        continue

                if new_cost < chosen_cost:
                    chosen_cost, chosen_tour, chosen_move = new_cost, new_tour, tabu_key

            if chosen_tour is None or chosen_move is None:
                if params.track_iteration_history: history.append(best_cost)
                no_improve_count += 1
                global_no_improve_count += 1
                continue

            # Menentukan string operator yang digunakan
            op_used = "2-opt" if len(chosen_move) == 2 else f"Or-opt (k={chosen_move[1]})"

            tabu.add(chosen_move)
            current_tour, current_cost = chosen_tour, chosen_cost
            imp_percent = ((best_cost - current_cost) / best_cost) * 100 if best_cost > 0 else 0

            # Cek New Best
            if current_cost < best_cost and imp_percent >= params.min_improvement_percent:
                prev_cost, prev_dist, prev_time = best_cost, best_dist, best_time
                best_cost, best_tour = current_cost, current_tour[:]
                no_improve_count, global_no_improve_count = 0, 0
                
                _, best_dist, best_time = self._get_metrics(best_tour)
                logs.append(self._create_event(
                    event_type="NEW_BEST", iteration=idx_iter, elapsed_ms=round((time.perf_counter() - t0)*1000, 3),
                    current_distance_in_meters=best_dist, current_duration_in_seconds=best_time,
                    best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
                    distance_improvement_in_meters=max(0, prev_dist - best_dist),
                    duration_improvement_in_seconds=max(0, prev_time - best_time),
                    improvement_percent=imp_percent, objective_value=best_cost,
                    operator_used=op_used, is_new_best=True, used_aspiration_criteria=used_aspiration,
                    iterations_without_improvement=0,
                    message=f"New best solution found: improved by {imp_percent:.4f}%.",
                    intermediate_tour=best_tour[:] if params.save_intermediate_solutions else None
                ))
            else:
                no_improve_count += 1
                global_no_improve_count += 1

            if params.track_iteration_history: history.append(best_cost)

            # Log Periodik
            if idx_iter % 10 == 0:
                cur_c, cur_d, cur_t = self._get_metrics(current_tour)
                logs.append(self._create_event(
                    event_type="PERIODIC_LOG", iteration=idx_iter, elapsed_ms=round((time.perf_counter() - t0)*1000, 3),
                    current_distance_in_meters=cur_d, current_duration_in_seconds=cur_t,
                    best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
                    objective_value=cur_c, operator_used=op_used, iterations_without_improvement=global_no_improve_count,
                    message = "Progress update (iteration 10): Search proceeding as expected."
                ))

        best_tour = _rotate_to_depot(best_tour, self.depot)

        # Tahap Reoptimization
        if params.local_improvement_strategy == LocalImprovementStrategy.TWO_OPT:
            prev_cost, prev_dist, prev_time = best_cost, best_dist, best_time
            best_tour, two_opt_iters = _two_opt_improve(
                best_tour, self.cost_matrix, params.max_improvement_iterations, t0, params.max_execution_time_seconds
            )
            best_tour = _rotate_to_depot(best_tour, self.depot)
            iters_run += two_opt_iters
            best_cost, best_dist, best_time = self._get_metrics(best_tour)
            
            logs.append(self._create_event(
                event_type="REOPTIMIZATION_COMPLETE", iteration=iters_run, elapsed_ms=round((time.perf_counter() - t0)*1000, 3),
                current_distance_in_meters=best_dist, current_duration_in_seconds=best_time,
                best_distance_in_meters=best_dist, best_duration_in_seconds=best_time,
                distance_improvement_in_meters=max(0, prev_dist - best_dist),
                duration_improvement_in_seconds=max(0, prev_time - best_time),
                improvement_percent=((prev_cost - best_cost) / prev_cost * 100) if prev_cost > 0 else 0,
                objective_value=best_cost, operator_used="2-opt", is_new_best=(best_cost < prev_cost),
                message = "Local 2-opt reoptimization completed after Tabu Search.",
                intermediate_tour=best_tour[:] if params.save_intermediate_solutions else None
            ))

        return Assignment(
            tour=best_tour, total_distance_in_meters=best_dist, total_duration_in_seconds=best_time,
            algorithm_used=algo_name, elapsed_ms=round((time.perf_counter() - t0)*1000, 3),
            iterations=iters_run, history=history, logs=logs
        )

# ---------------------------------------------------------------------------
# Internal Utilities (Sama seperti sebelumnya)
# ---------------------------------------------------------------------------

class _TabuList:
    def __init__(self, tenure: int) -> None:
        self.tenure = tenure
        self._queue: Deque[MoveKey] = deque()
        self._set: set[MoveKey] = set()
    def add(self, move: MoveKey) -> None:
        if len(self._queue) >= self.tenure: self._set.discard(self._queue.popleft())
        self._queue.append(move)
        self._set.add(move)
    def is_tabu(self, move: MoveKey) -> bool: return move in self._set
    def clear(self) -> None:
        self._queue.clear()
        self._set.clear()

def _tour_cost(tour: List[int], matrix: List[List[float]]) -> float:
    n = len(tour)
    return sum(matrix[tour[i]][tour[(i + 1) % n]] for i in range(n))

def _rotate_to_depot(tour: List[int], depot: int) -> List[int]:
    if depot not in tour: return tour
    idx = tour.index(depot)
    return tour[idx:] + tour[:idx]

def _normalize_move_key(move_key: MoveKey) -> MoveKey:
    if len(move_key) == 2:
        two_opt: TwoOptMove = move_key # type: ignore
        return (min(two_opt), max(two_opt))
    return move_key

def _nearest_neighbor_init(matrix: List[List[float]], start: int = 0) -> List[int]:
    n = len(matrix)
    visited, tour = [False] * n, [start]
    visited[start], current = True, start
    for _ in range(n - 1):
        nearest, nearest_c = -1, float("inf")
        for j in range(n):
            if not visited[j] and matrix[current][j] < nearest_c:
                nearest_c, nearest = matrix[current][j], j
        tour.append(nearest); visited[nearest] = True; current = nearest
    return tour

def _nearest_neighbor_tsp(matrix: List[List[float]]) -> List[int]:
    best_tour, best_cost = [], float("inf")
    for start in range(len(matrix)):
        tour = _nearest_neighbor_init(matrix, start)
        c = _tour_cost(tour, matrix)
        if c < best_cost: best_cost, best_tour = c, tour[:]
    return best_tour

def _greedy_edge_tsp(matrix: List[List[float]]) -> List[int]:
    n = len(matrix)
    edges = sorted((matrix[i][j], i, j) for i in range(n) for j in range(i + 1, n))
    degree: List[float] = [0] * n
    adj: List[List[int]] = [[] for _ in range(n)]
    parent: List[int] = list(range(n))
    rank: List[int] = [0] * n

    def find(x: int) -> int:
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rank[rx] < rank[ry]: rx, ry = ry, rx
        parent[ry] = rx
        if rank[rx] == rank[ry]: rank[rx] += 1

    edge_count = 0
    for _, u, v in edges:
        if edge_count == n: break
        if degree[u] >= 2 or degree[v] >= 2: continue
        if edge_count < n - 1 and find(u) == find(v): continue
        union(u, v); adj[u].append(v); adj[v].append(u)
        degree[u] += 1; degree[v] += 1; edge_count += 1

    start = next((i for i in range(n) if len(adj[i]) == 1), 0)
    tour, prev, current = [start], -1, start
    for _ in range(n - 1):
        for nxt in adj[current]:
            if nxt != prev:
                tour.append(nxt)
                prev, current = current, nxt
                break
    return tour

def _two_opt_improve(tour: List[int], matrix: List[List[float]], max_iter: int, t0: float, time_limit: float) -> Tuple[List[int], int]:
    best, n, improved, iteration = tour[:], len(tour), True, 0
    while improved and iteration < max_iter:
        if (time.perf_counter() - t0) > time_limit: break
        improved = False
        iteration += 1
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b, c, d = best[i - 1], best[i], best[j], best[(j + 1) % n]
                delta = (matrix[a][c] + matrix[b][d]) - (matrix[a][b] + matrix[c][d])
                if delta < -1e-10:
                    best[i : j + 1] = best[i : j + 1][::-1]
                    improved = True
    return best, iteration

def _generate_2opt_moves(tour: List[int], matrix: List[List[float]], top_k: int) -> List[Candidate]:
    n = len(tour)

    raw: list[tuple[float, tuple[int, int]]] = []
    
    for i in range(1, n - 1):
        for j in range(i + 1, n):
            a, b, c, d = tour[i - 1], tour[i], tour[j], tour[(j + 1) % n]
            delta = (matrix[a][c] + matrix[b][d]) - (matrix[a][b] + matrix[c][d])
            raw.append((delta, (i, j)))
    raw.sort(key=lambda x: x[0])
    return [(d, (i, j), tour[:i] + tour[i:j+1][::-1] + tour[j+1:]) for d, (i, j) in raw[:top_k]]

def _generate_oropt_moves(tour: List[int], matrix: List[List[float]], current_cost: float, top_k: int) -> List[Candidate]:
    n = len(tour)
    moves: List[Candidate] = []
    
    for k in (1, 2, 3):
        if k >= n: continue
        for i in range(n):
            seg_indices = [(i + s) % n for s in range(k)]
            seg_set, seg_nodes = set(seg_indices), [tour[idx] for idx in seg_indices]
            remaining = [tour[idx] for idx in range(n) if idx not in seg_set]
            if not remaining: continue
            for j in range(len(remaining)):
                new_tour = remaining[: j + 1] + seg_nodes + remaining[j + 1 :]
                delta = _tour_cost(new_tour, matrix) - current_cost
                moves.append((delta, ("oropt", k, i, j), new_tour))
    moves.sort(key=lambda x: x[0])
    return moves[:top_k]

def _double_bridge(tour: List[int], rng: random.Random) -> List[int]:
    n = len(tour)
    if n < 8:
        t = tour[:]
        if n > 2:
            i, j = sorted(rng.sample(range(1, n), 2))
            t[i:j] = rng.sample(t[i:j], len(t[i:j]))
        return t
    a, b, c = sorted(rng.sample(range(1, n), 3))
    return tour[:a] + tour[b:c] + tour[a:b] + tour[c:]