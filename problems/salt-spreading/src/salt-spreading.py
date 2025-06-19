from __future__ import annotations

import json
import logging
import random
import sys
from dataclasses import dataclass
from logging import getLogger
from typing import Iterable, Optional, Protocol, Self, TextIO, TypeVar, final
from representation import Connection, Plan, ShortestPath

import jsonschema
import matplotlib.pyplot as plt
import networkx
import itertools
import copy

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

class _SupportsLT(Protocol):
    def __lt__(self, other: Self) -> bool: ...


_T = TypeVar("_T", bound=_SupportsLT)


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


# ---------------------------------- Solution --------------------------------


@final
class Solution(SupportsCopySolution, SupportsObjectiveValue, SupportsLowerBound):
    def __init__(self, problem, representation: Plan):
        self.problem = problem
        self.representation = representation
        self.remaining_connections = []
        for arc in self.problem.arcs_required.values():
            self.remaining_connections.append(Connection(arc["arc"][0], arc["arc"][1], arc["dem"], "arc"))
        for edge in self.problem.edges_required.values():
            self.remaining_connections.append(Connection(edge["edge"][1], edge["edge"][0], edge["dem"], "edge"))

    def __str__(self):
        return f"Solution({self.representation})"

    def __repr__(self) -> str:
        return f"Solution({self.representation})"

    @property
    def is_feasible(self) -> bool:
        # check if all needed connections are traversed
        all_connections = [vehicle_plan.connections for vehicle_plan in self.representation.vehicle_plans.values()]
        all_connections = list(itertools.chain.from_iterable(all_connections))
        reversed_edges = []
        for connection in all_connections:
            if connection.type == "edge":
                reversed = copy.copy(connection)
                reversed.from_node, reversed.to_node = connection.to_node, connection.from_node
                reversed_edges.append(reversed)
        all_connections.extend(reversed_edges)
        traversed_connections = [(connection.from_node, connection.to_node) for connection in all_connections]

        for arc in self.problem.arcs_required:
            if arc not in traversed_connections:
                return False
        for edge in self.problem.edges_required:
            if edge not in traversed_connections:
                return False

        return True

    def to_textio(self, f: TextIO) -> None:
        print(self.__str__())

    def copy_solution(self) -> Self:
        pass

    def objective_value(self) -> Optional[int]:
        return self.representation.evaluate()

    def lower_bound(self) -> int:
        pass


# ----------------------------------- Moves -----------------------------------


@final
class AddMove(SupportsApplyMove[Solution], SupportsLowerBoundIncrement[Solution]):
    def __init__(self, neighbourhood: AddNeighbourhood, connection: Connection, vehicle_id: Optional[str] = None):
        self.neighbourhood = neighbourhood
        self.connection = connection
        self.vehicle_id = vehicle_id

    def apply_move(self, solution: Solution) -> Solution:
        solution.representation.vehicle_plans[self.vehicle_id].append_connection(self.connection)
        solution.remaining_connections.remove(self.connection)
        return solution

    def lower_bound_increment(self, solution: Solution) -> float:
        new_salting = solution.problem.distances[(self.connection.from_node, self.connection.to_node)].distance
        if not solution.representation.vehicle_plans[self.vehicle_id].route:
            return new_salting
        last_depot2home = solution.representation.vehicle_plans[self.vehicle_id].route[-1]
        last_point2last_depot = solution.representation.vehicle_plans[self.vehicle_id].route[-2]
        last_point = last_point2last_depot.from_node

        last_point2depot = solution.problem.distances[(last_point, self.connection.from_node)].distance
        new_salting2depot = solution.problem.distances[(self.connection.to_node, last_depot2home.from_node)].distance

        # applied = copy.deepcopy(solution)
        # applied.representation.vehicle_plans[self.vehicle_id].append_connection(self.connection)
        # incr = applied.representation.evaluate() - solution.representation.evaluate()
        return last_point2depot + new_salting + new_salting2depot


@final
class SwapMove(SupportsApplyMove[Solution], SupportsObjectiveValueIncrement[Solution]):
    def __init__(self, neighbourhood: SwapNeighbourhood, iveh1: int, veh1:VehiclePlan, iveh2: int, veh2: VehiclePlan):
        self.neighbourhood = neighbourhood
        # ix and jx are indices
        self.iveh1 = iveh1
        self.iveh2 = iveh2
        self.veh1=veh1
        self.veh2=veh2

    def apply_move(self, solution: Solution) -> Solution:
        #prob = solution.problem
        # n, ix, jx = prob.n, self.ix, self.jx
        # # Update tour length
        # t = solution.tour
        # solution.lb -= prob.dist[t[ix - 1]][t[ix]] + prob.dist[t[jx - 1]][t[jx % n]]
        # solution.lb += prob.dist[t[ix - 1]][t[jx - 1]] + prob.dist[t[ix]][t[jx % n]]
        # # Update solution
        # solution.tour[ix:jx] = solution.tour[ix:jx][::-1]
        return solution

    def objective_value_increment(self, solution: Solution) -> float:
        prob = solution.problem

        befSwap=self.veh1.evaluate()+self.veh2.evaluate()

        hVar=self.veh1[self.iveh1]
        self.veh1[self.iveh1]=self.veh2[self.iveh2]
        self.veh2[self.veh2]=hVar
        
        afterSwap=self.veh1.evaluate()+self.veh2.evaluate()
        # n, ix, jx = prob.n, self.ix, self.jx
        # # Tour length increment
        # t = solution.tour
        # incr = prob.dist[t[ix - 1]][t[jx - 1]] + prob.dist[t[ix]][t[jx % n]]
        # incr -= prob.dist[t[ix - 1]][t[ix]] + prob.dist[t[jx - 1]][t[jx % n]]

        #return incr
        return afterSwap-befSwap


# ------------------------------- Neighbourhood ------------------------------


@final
class AddNeighbourhood(SupportsMoves[Solution, AddMove]):
    def __init__(self, problem: Problem):
        self.problem = problem

    def moves(self, solution: Solution) -> Iterable[AddMove]:
        assert self.problem == solution.problem
        for connection in solution.remaining_connections:
            for vehicle_id in solution.problem.vehicles.keys():
                yield AddMove(self, connection, vehicle_id)


@final
class SwapNeighbourhood(
    SupportsMoves[Solution, SwapMove],
    SupportsRandomMovesWithoutReplacement[Solution, SwapMove],
    SupportsRandomMove[Solution, SwapMove],
):
    def __init__(self, problem: Problem):
        self.problem = problem

    def moves(self, solution: Solution) -> Iterable[SwapMove]:
        assert self.problem == solution.problem

        for key1 in solution.representation.vehicle_plans.keys():
            vehicle1 = solution.representation.vehicle_plans[key1]
            vehicle1Connections = vehicle1.connections
            for indexConnVeh1 in enumerate(vehicle1Connections):
                for key2 in solution.representation.vehicle_plans.keys():
                    if key1==key2:
                        continue
                    else:
                        vehicle2 = solution.representation.vehicle_plans[key2]
                        vehicle2Connections = vehicle2.connections
                        for indexConnVeh2 in enumerate(vehicle2Connections):
                            yield SwapMove(self, indexConnVeh1, vehicle1, indexConnVeh2, vehicle2)
                # TODO: Finish this!! 

        # n = self.problem.n
        # # This is only meant to be used as a local neighbourhood, so solution should be feasible
        # assert solution.is_feasible
        # for ix in range(1, n - 1):
        #     for jx in range(ix + 2, n + (ix != 1)):
        #         yield SwapMove(self, ix, jx)

    def random_moves_without_replacement(self, solution: Solution) -> Iterable[SwapMove]:
        raise NotImplementedError

    def random_move(self, solution: Solution) -> Optional[SwapMove]:
        return next(iter(self.random_moves_without_replacement(solution)), None)


# ---------------------------------- Problem --------------------------------


@final
class Problem(
    SupportsConstructionNeighbourhood[AddNeighbourhood],
    SupportsLocalNeighbourhood[SwapNeighbourhood],
    SupportsEmptySolution[Solution],
    SupportsRandomSolution[Solution],
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
            (node1["label"], node2["label"]): ShortestPath([], random.randint(0, 200)) if node1["label"] != node2["label"] else ShortestPath([], 0)
                for node1 in self.nodes.values() for node2 in self.nodes.values()
        }

        self.c_nbhood: Optional[AddNeighbourhood] = None
        self.l_nbhood: Optional[SwapNeighbourhood] = None
    
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
            length = item[1]["len"]
            graph.add_edge(arc[0], arc[1], time=time, length=length)

        for item in self.arcs_required.items():
            arc = item[0]
            time = item[1]["time"]
            length = item[1]["len"]
            dem = item[1]["dem"]
            graph.add_edge(arc[0], arc[1], time=time, length=length, dem=dem)

        for item in self.edges_required.items():
            arc = item[0]
            time = item[1]["time"]
            length = item[1]["len"]
            dem = item[1]["dem"]
            graph.add_edge(arc[0], arc[1], time=time, length=length, dem=dem)
            graph.add_edge(arc[1], arc[0], time=time, length=length, dem=dem)

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
                    # print("OUT_EDGE", out_edge)
                    edge = graph.edges[out_edge]
                    # print("EDGE", edge)
                    dual_graph.add_edge(node, out_edge, length=edge["length"])
            else:
                out_edges = graph.out_edges(exit_node)
                # print("OUT_EDGES", out_edges)
                for out_edge in out_edges:
                    permuted_node = (out_edge[1], out_edge[0])
                    if node != permuted_node:
                        edge = graph.edges[out_edge]
                        # edge[1]["length"]
                        dual_graph.add_edge(node, out_edge, length=edge["length"])

        #problem.print_graph(dual_graph)
        self.distances = {}
        for node in graph.nodes:
            dual_graph.add_node((None, None))
            for dNode in dual_graph.nodes:
                # print("dNode", dNode)
                if node == dNode[0]:
                    edge = graph.edges[dNode]
                    dual_graph.add_edge((None, None), dNode, length=edge["length"]) # TODO: Add edges from dummy node for each "home" node "dummy"
            return_of_dijkstra = networkx.single_source_dijkstra(dual_graph, (None, None), weight="length")
            
            for endNode in graph.nodes:
                newKey=(node,endNode)
                if node==endNode:
                    self.distances[newKey] = ShortestPath([], 0, 0)
                else:
                    bestKey=None
                    bestValue=float("inf")
                    #listRes=[]
                    for key in return_of_dijkstra[0].keys():
                        if key == (None, None) or key[1]!=endNode:
                            continue
                        #listRes.append({"k":key,"v":return_of_dijkstra[0][key],"p":return_of_dijkstra[1][key]})
                        if return_of_dijkstra[0][key]<bestValue:
                            bestValue=return_of_dijkstra[0][key]
                            bestKey=key
                    #print("LIST",listRes)
                    
                    time=0
                    for newEdge in return_of_dijkstra[1][bestKey][1:]:
                        time+=graph[newEdge[0]][newEdge[1]]['time']

                    self.distances[newKey] = ShortestPath(return_of_dijkstra[1][bestKey][1:], return_of_dijkstra[0][bestKey], time)
            dual_graph.remove_node((None,None))
        #print("DISTANCES", self.distances)
        #print(len(self.distances))
        # check=0
        # check2=0
        # check3=0
        # l=[('0', '1'), ('1', '3'), ('3', '2'), ('2', '1')]
        # for t in l:
        #     print(t)
        #     check+=self.distances[t].distance
        #     print(self.distances[t].distance)
        #     check2+=graph[t[0]][t[1]]["length"]
        #     print(graph[t[0]][t[1]]["length"])
            
            
        #     print()
        
        # for i in range(len(l)-1):
        #     s1=l[i]
        #     s2=l[i+1]
        #     check3+=dual_graph[s1][s2]["length"]
        # print(check3)

        #print(self.distances[('3','2')])
        return dual_graph

    def print_graph(self, graph: networkx.DiGraph) -> None:
        networkx.draw(graph, with_labels=True)
        plt.show()

    def construction_neighbourhood(self) -> AddNeighbourhood:
        if self.c_nbhood is None:
            self.c_nbhood = AddNeighbourhood(self)
        return self.c_nbhood

    def local_neighbourhood(self) -> SwapNeighbourhood:
        if self.l_nbhood is None:
            self.l_nbhood = SwapNeighbourhood(self)
        return self.l_nbhood

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
        return Solution(self, Plan(self.vehicles, self.depots, self))

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
    # for item_edge in original_graph.edges.items():
    #     print("iEdge", item_edge)

    dual_graph = problem.create_dual_graph(original_graph)
    # for edge in dual_graph.edges.items():
    #     print("edge", edge)

    # print("DISTANCES", problem.distances)

    # problem.print_graph(dual_graph)

    # log.info(problem)

    # instance = problem.empty_solution()
    # print(f"Empty solution: {instance}")
    #
    # instance = problem.random_solution()
    # print(f"Random solution: {instance}")
    # print(f"Route of a random solution: {instance.representation.vehicle_plans['1'].construct_route()}")
    # print(f"Is feasible: {instance.is_feasible}")
    # print(f"Objective: {instance.objective_value()} m")
    # Run greedy construction to get an initial solution
    solution = alg.greedy_construction(problem)
    print(solution)
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
