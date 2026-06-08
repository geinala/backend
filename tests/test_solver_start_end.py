from types import SimpleNamespace

from app.services.or_tools_solver.types import SolverProblem
from app.services.or_tools_solver.tabu_search_solver import TabuSearchSolver


def test_tabu_search_solver_supports_distinct_start_and_end_indices():
    solver = TabuSearchSolver()
    problem = SolverProblem(
        time_matrix=[
            [0, 1, 1],
            [1, 0, 1],
            [1, 1, 0],
        ],
        demands=[0, 0, 0],
        courier=SimpleNamespace(id=7, name="Courier 7"),
        start_index=1,
        end_index=2,
    )

    manager, routing, solution = solver.solve(problem)

    assert solution is not None

    index = routing.Start(0)
    route_nodes: list[int] = []

    while not routing.IsEnd(index):
        route_nodes.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))

    route_nodes.append(manager.IndexToNode(index))

    assert route_nodes[0] == 1
    assert route_nodes[-1] == 2