import json
import logging
import random
import sys
from dataclasses import dataclass
from logging import getLogger
from typing import Optional, Protocol, Self, TextIO, TypeVar, final
from representation import Connection, Plan, ShortestPath

import jsonschema
import matplotlib.pyplot as plt
import networkx
from roar_net_api.operations import (
    SupportsApplyMove,
    SupportsConstructionNeighbourhood,
    SupportsCopySolution,
    SupportsEmptySolution,
    SupportsLocalNeighbourhood,
    SupportsLowerBound,
    SupportsLowerBoundIncrement,
    SupportsMoves,
    SupportsObjectiveValue,
    SupportsObjectiveValueIncrement,
    SupportsRandomMove,
    SupportsRandomMovesWithoutReplacement,
    SupportsRandomSolution,
)

log = getLogger(__name__)


# ---------------------------------- Problem --------------------------------
@dataclass(
    init=False,
    repr=True,
    eq=True,
    order=False,
    unsafe_hash=False,
    frozen=True,
    match_args=False,
    kw_only=False,
    slots=False,
    weakref_slot=False,
)
class AttrDict:
    def __init__(self, d: dict):
        for k, v in d.items():
            object.__setattr__(self, k, v)

    def __str__(self) -> str:
        return "\n".join(
            f"{k}: {v}" for k, v in self.__dict__.items() if not k.startswith("_")
        )


@final
class Solution(SupportsCopySolution, SupportsObjectiveValue, SupportsLowerBound):
    def __init__(self, problem, representation: Plan):
        self.problem = problem
        self.representation = representation

    def __str__(self):
        return f"Solution({self.representation})"

    def __repr__(self) -> str:
        return f"Solution({self.representation})"

    @property
    def is_feasible(self) -> bool:
        pass

    def to_textio(self, f: TextIO) -> None:
        print(self.__str__())

    def copy_solution(self) -> Self:
        pass

    def objective_value(self) -> Optional[int]:
        pass

    def lower_bound(self) -> int:
        pass


@final
class Problem(
    # SupportsConstructionNeighbourhood[AddNeighbourhood],
    # SupportsLocalNeighbourhood[TwoOptNeighbourhood],
    # SupportsEmptySolution[Solution],
    # SupportsRandomSolution[Solution],
):
    def __init__(self, d: dict):
        self.data = AttrDict(d)

        self.name = self.data.name
        self.max_time = self.data.max_time
        self.nodes = {n["label"]: n for n in self.data.nodes}
        self.vehicles = {v["id"]: v for v in self.data.vehicles}
        self.depots = {d["label"]: d for d in self.data.depots}
        self.dwelling_nodes = {v["home"]: v for v in self.data.vehicles}
        self.arcs = {tuple(a["arc"]): a for a in self.data.A}
        self.arcs_required = {tuple(a["arc"]): a for a in self.data.A_R}
        self.edges_required = {tuple(a["edge"]): a for a in self.data.E_R}
        self.all_links = (
            set(self.arcs.keys())
            | set(self.arcs_required.keys())
            | set(self.edges_required.keys())
        )
        self.all_links |= {(a[1], a[0]) for a in self.edges_required.keys()}
        self.U = {n["label"]: n for n in self.data.U}

        self.distances = {
            (node1["label"], node2["label"]): ShortestPath([], random.randint(0, 200)) for node1 in self.nodes.values() for node2 in self.nodes.values() if node1["label"] != node2["label"]
        }


    def __str__(self) -> str:
        return str(self.data)

    def create_graph(self) -> networkx.DiGraph:
        graph = networkx.DiGraph()
        for node in self.nodes:
            if node in self.U:
                graph.add_node(node, u=True)
            else:
                graph.add_node(node, u=False)

        # print("ITEMS:", self.arcs.items())
        for item in self.arcs.items():
            # print("ITEM", item)
            arc = item[0]
            time = item[1]["time"]
            lenght = item[1]["len"]
            graph.add_edge(arc[0], arc[1], time=time, lenght=lenght)

        for item in self.arcs_required.items():
            # print("ARC_REQUIRED", arc)
            arc = item[0]
            time = item[1]["time"]
            lenght = item[1]["len"]
            dem = item[1]["dem"]
            graph.add_edge(arc[0], arc[1], time=time, lenght=lenght, dem=dem)

        for item in self.edges_required.items():
            # print("EDGE_REQUIRED", edge)
            arc = item[0]
            time = item[1]["time"]
            lenght = item[1]["len"]
            dem = item[1]["dem"]
            graph.add_edge(arc[0], arc[1], time=time, lenght=lenght, dem=dem)
            graph.add_edge(arc[1], arc[0], time=time, lenght=lenght, dem=dem)

        return graph

    def create_dual_graph(self, graph: networkx.DiGraph) -> networkx.DiGraph:
        dual_graph = networkx.DiGraph()
        for edge in graph.edges:
            # print("EDGE", edge)
            # dual_graph.add_node(f"{edge[0]},{edge[1]}")
            dual_graph.add_node(edge)

        for node in dual_graph.nodes:
            # print("NODE", node)
            exit_node = node[1]
            # print("NODE[EXIT_NODE]", graph.nodes[exit_node])
            if graph.nodes[exit_node]["u"]:
                out_edges = graph.out_edges(exit_node)
                # print("OUT_EDGES", out_edges)
                for out_edge in out_edges:
                    dual_graph.add_edge(node, out_edge)
            else:
                out_edges = graph.out_edges(exit_node)
                # print("OUT_EDGES", out_edges)
                for out_edge in out_edges:
                    permuted_node = (out_edge[1], out_edge[0])
                    if node != permuted_node:
                        dual_graph.add_edge(node, out_edge)

        return dual_graph

    def print_graph(self, graph: networkx.DiGraph) -> None:
        networkx.draw(graph, with_labels=True)
        plt.show()

    # def construction_neighbourhood(self) -> AddNeighbourhood:
    #     if self.c_nbhood is None:
    #         self.c_nbhood = AddNeighbourhood(self)
    #     return self.c_nbhood

    # def local_neighbourhood(self) -> TwoOptNeighbourhood:
    #     if self.l_nbhood is None:
    #         self.l_nbhood = TwoOptNeighbourhood(self)
    #     return self.l_nbhood

    @classmethod
    def from_textio(cls, f: TextIO) -> Self:
        """
        Create a problem from a text I/O source `f`
        """
        data = json.load(f)
        # Load JSON schema
        with open("support/schema_instance.json", "r") as f:
            schema = json.load(f)
        try:
            jsonschema.validate(instance=data, schema=schema)
            log.info("JSON is valid")
        except jsonschema.ValidationError as ve:
            log.info(f"Validation error: {ve.message}")
            sys.exit(0)
        except jsonschema.SchemaError as se:
            log.info(f"Schema error: {se.message}")
            sys.exit(0)
        return cls(data)  # , data.name)

    def empty_solution(self) -> Solution:
        return Solution(self, Plan(self.vehicles, self.depots))

    def random_solution(self) -> Solution:
        result = self.empty_solution()
        connections_to_salt = []

        for arc in self.arcs_required:
            connections_to_salt.append(Connection(arc[0], arc[1], self.arcs_required[arc]["dem"], "arc"))
        for edge in self.edges_required:
            if random.random() < 0.5:
                connections_to_salt.append(Connection(edge[0], edge[1], self.edges_required[edge]["dem"], "edge"))
            else:
                connections_to_salt.append(Connection(edge[1], edge[0], self.edges_required[edge]["dem"], "edge"))
        random.shuffle(connections_to_salt)
        for connection in connections_to_salt:
            random_vehicle = random.choice(list(result.representation.vehicle_plans.keys()))
            result.representation.vehicle_plans[random_vehicle].append_connection(connection)

        return result


if __name__ == "__main__":
    import roar_net_api.algorithms as alg

    logging.basicConfig(
        stream=sys.stderr, level="INFO", format="%(levelname)s;%(asctime)s;%(message)s"
    )

    log.info("Salt spreading problem")

    if len(sys.argv) < 2:
        problem = Problem.from_textio(sys.stdin)
    else:
        with open(sys.argv[1], "r") as f:
            problem = Problem.from_textio(f)

    original_graph = problem.create_graph()
    for item_edge in original_graph.edges.items():
        print("iEdge", item_edge)

    dual_graph = problem.create_dual_graph(original_graph)
    for edge in dual_graph.edges:
        print("edge", edge)

    # problem.print_graph(dual_graph)

    # log.info(problem)

    instance = problem.empty_solution()
    print(f"Empty solution: {instance}")

    instance = problem.random_solution()
    print(f"Random solution: {instance}")
    print(f"Route of a random solution: {instance.representation.vehicle_plans['1'].construct_route()}")

    # Run greedy construction to get an initial solution
    # solution = alg.greedy_construction(problem)
    # # solution = alg.beam_search(problem, bw=10)
    # # solution = alg.grasp(problem, 30.0)
    # log.info(f"Objective value after constructive search: {solution.objective_value()}")

    # # Run simulated annealing to improve the previous solution
    # solution = alg.sa(problem, solution, 10.0, 30.0)
    # # solution = alg.rls(problem, solution, 10.0)
    # # solution = alg.best_improvement(problem, solution)
    # # solution = alg.first_improvement(problem, solution)
    # log.info(f"Objective value after local search: {solution.objective_value()}")

    # # Print the final solution to stdout
    # solution.to_textio(sys.stdout)
