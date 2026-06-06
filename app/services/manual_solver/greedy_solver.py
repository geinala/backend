from __future__ import annotations
import time
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class Node:
    id: int
    x: float
    y: float
    label: str = ""

    def __post_init__(self):
        if not self.label:
            self.label = f"Node-{self.id}"


@dataclass
class TSPResult:
    tour: List[int]
    total_distance: float
    algorithm: str
    elapsed_ms: float
    iterations: int = 0
    improvement_pct: float = 0.0


def tour_distance(tour: List[int], dist: List[List[float]]) -> float:
    """Hitung total jarak sebuah tur (termasuk kembali ke depot)."""
    total = 0.0
    n = len(tour)
    for i in range(n):
        total += dist[tour[i]][tour[(i + 1) % n]]
    return total


# ---------------------------------------------------------------------------
# Algoritma 1: Nearest Neighbor Greedy (NN)
# ---------------------------------------------------------------------------

def nearest_neighbor_tsp(
    nodes: List[Node],
    dist: List[List[float]],
    start: int = 0
) -> TSPResult:
    """
    Nearest Neighbor Greedy TSP.

    Strategi: Mulai dari depot, selalu kunjungi node terdekat yang belum
    dikunjungi. Kompleksitas O(n²).

    Args:
        nodes : daftar node
        dist  : distance matrix
        start : index node awal (depot)

    Returns:
        TSPResult dengan tur terbaik dari semua titik awal (multi-start).
    """
    t0 = time.perf_counter()
    n = len(nodes)
    best_tour: List[int] = []
    best_dist = float("inf")

    # Multi-start: coba semua titik awal untuk hasil lebih baik
    for start_node in range(n):
        visited = [False] * n
        tour = [start_node]
        visited[start_node] = True
        current = start_node

        for _ in range(n - 1):
            nearest = -1
            nearest_d = float("inf")
            for j in range(n):
                if not visited[j] and dist[current][j] < nearest_d:
                    nearest_d = dist[current][j]
                    nearest = j
            tour.append(nearest)
            visited[nearest] = True
            current = nearest

        d = tour_distance(tour, dist)
        if d < best_dist:
            best_dist = d
            best_tour = tour[:]

    elapsed = (time.perf_counter() - t0) * 1000
    return TSPResult(
        tour=best_tour,
        total_distance=best_dist,
        algorithm="Nearest Neighbor (Multi-start)",
        elapsed_ms=round(elapsed, 3),
        iterations=n,
    )


# ---------------------------------------------------------------------------
# Algoritma 2: Greedy Edge Insertion
# ---------------------------------------------------------------------------

def greedy_edge_tsp(
    nodes: List[Node],
    dist: List[List[float]],
) -> TSPResult:
    """
    Greedy Edge Insertion TSP.

    Strategi: Urutkan semua edge dari terpendek ke terpanjang, tambahkan
    edge jika tidak membentuk siklus prematur dan degree node ≤ 2.
    Kompleksitas O(n² log n) karena sorting.

    Returns:
        TSPResult
    """
    t0 = time.perf_counter()
    n = len(nodes)

    # Buat & urutkan semua edge
    edges: List[Tuple[float, int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            edges.append((dist[i][j], i, j))
    edges.sort()  # ascending by distance

    degree = [0] * n
    adj: List[List[int]] = [[] for _ in range(n)]

    # Union-Find untuk deteksi siklus prematur
    parent = list(range(n))
    rank = [0] * n

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]   # path compression
            x = parent[x]
        return x

    def union(x: int, y: int) -> bool:
        rx, ry = find(x), find(y)
        if rx == ry:
            return False
        if rank[rx] < rank[ry]:
            rx, ry = ry, rx
        parent[ry] = rx
        if rank[rx] == rank[ry]:
            rank[rx] += 1
        return True

    edge_count = 0
    for _, u, v in edges:
        if edge_count == n:
            break
        # Tolak jika degree sudah 2 (node sudah terhubung di 2 sisi)
        if degree[u] >= 2 or degree[v] >= 2:
            continue
        # Tolak jika akan membentuk siklus sebelum tur lengkap
        if edge_count < n - 1 and find(u) == find(v):
            continue
        union(u, v)
        adj[u].append(v)
        adj[v].append(u)
        degree[u] += 1
        degree[v] += 1
        edge_count += 1

    # Rekonstruksi tur dari adjacency list
    tour = _reconstruct_tour(adj, n)
    total_d = tour_distance(tour, dist)
    elapsed = (time.perf_counter() - t0) * 1000

    return TSPResult(
        tour=tour,
        total_distance=total_d,
        algorithm="Greedy Edge Insertion",
        elapsed_ms=round(elapsed, 3),
        iterations=len(edges),
    )


def _reconstruct_tour(adj: List[List[int]], n: int) -> List[int]:
    """Rekonstruksi urutan tur dari adjacency list Hamiltonian path."""
    # Cari node dengan degree 1 (ujung path) atau mulai dari 0
    start = 0
    for i in range(n):
        if len(adj[i]) == 1:
            start = i
            break

    tour = [start]
    prev = -1
    current = start

    for _ in range(n - 1):
        for nxt in adj[current]:
            if nxt != prev:
                tour.append(nxt)
                prev = current
                current = nxt
                break

    return tour


# ---------------------------------------------------------------------------
# Algoritma 3: 2-opt Local Search (Post-improvement)
# ---------------------------------------------------------------------------

def two_opt_improve(
    tour: List[int],
    dist: List[List[float]],
    max_iter: int = 1000,
) -> Tuple[List[int], float, int]:
    """
    2-opt improvement untuk memperhalus tur greedy.

    Menukar dua edge jika swap mengurangi total jarak.
    Kompleksitas per iterasi: O(n²). Berjalan sampai tidak ada improvement
    atau mencapai max_iter.

    Returns:
        (improved_tour, total_distance, iteration_count)
    """
    best = tour[:]
    n = len(best)
    improved = True
    iteration = 0

    while improved and iteration < max_iter:
        improved = False
        iteration += 1
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                # Hitung delta tanpa komputasi ulang seluruh tur
                a, b = best[i - 1], best[i]
                c, d = best[j], best[(j + 1) % n]
                delta = (dist[a][c] + dist[b][d]) - (dist[a][b] + dist[c][d])
                if delta < -1e-10:
                    # Reverse segmen [i..j]
                    best[i:j + 1] = best[i:j + 1][::-1]
                    improved = True

    return best, tour_distance(best, dist), iteration

def solve_tsp_greedy(
    nodes: List[Node],
    use_2opt: bool = True,
    verbose: bool = True,
) -> dict:
    """
    Pipeline lengkap TSP Greedy:
      1. Build distance matrix
      2. Nearest Neighbor (multi-start)
      3. Greedy Edge Insertion
      4. 2-opt improvement pada hasil terbaik

    Args:
        nodes    : list of Node
        use_2opt : aktifkan 2-opt improvement
        verbose  : print hasil ke stdout

    Returns:
        dict berisi semua hasil per algoritma
    """
    if len(nodes) < 2:
        raise ValueError("Butuh minimal 2 node untuk TSP.")

    dist = build_distance_matrix(nodes)

    results = {}

    # --- Nearest Neighbor ---
    nn_result = nearest_neighbor_tsp(nodes, dist)
    results["nearest_neighbor"] = nn_result

    # --- Greedy Edge ---
    ge_result = greedy_edge_tsp(nodes, dist)
    results["greedy_edge"] = ge_result

    # --- Pilih hasil terbaik untuk 2-opt ---
    best_greedy = min(
        [nn_result, ge_result],
        key=lambda r: r.total_distance
    )

    if use_2opt:
        t0 = time.perf_counter()
        improved_tour, improved_dist, iters = two_opt_improve(
            best_greedy.tour, dist
        )
        elapsed = (time.perf_counter() - t0) * 1000
        improvement = (
            (best_greedy.total_distance - improved_dist)
            / best_greedy.total_distance * 100
        )
        opt_result = TSPResult(
            tour=improved_tour,
            total_distance=improved_dist,
            algorithm=f"{best_greedy.algorithm} + 2-opt",
            elapsed_ms=round(best_greedy.elapsed_ms + elapsed, 3),
            iterations=iters,
            improvement_pct=round(improvement, 2),
        )
        results["two_opt"] = opt_result

    if verbose:
        _print_results(nodes, results)

    return results