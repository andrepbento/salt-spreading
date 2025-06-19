import json
import random


class Connection:
    # arc/edge to be salted, service connection represents depo visit or travel from/to home point
    supported_types = ["arc", "edge", "service"]
    def __init__(self, from_node, to_node, dem, type):
        self.from_node = from_node
        self.to_node = to_node
        self.dem = dem
        if type not in self.supported_types:
            raise ValueError(f"Type must be one of {self.supported_types}, got {type}")
        self.type = type

    def __str__(self):
        return f"Connection({self.from_node}, {self.to_node}, dem={self.dem}, type={self.type})"

    def __repr__(self):
        return self.__str__()


class VehiclePlan:
    def __init__(self, vehicle_id, vehicle_capacity, vehicle_home, depots, problem, connections=None):
        self.vehicle_id = vehicle_id
        self.vehicle_capacity = vehicle_capacity
        self.connections = connections if connections is not None else []
        self.vehicle_home = vehicle_home
        self.depots = depots
        self.problem = problem
        self.route = self.construct_route()

    def select_depot(self, from_node, to_node):
        random_depot = random.choice(list(self.depots.values()))
        return random_depot["label"]

    def append_connection(self, connection):
        self.connections.append(connection)
        # recalculate the route after adding a new connection
        self.route = self.construct_route()

    def construct_route(self):
        if not self.connections:
            return []
        demanded_salt = 0
        home2first_connection = Connection(self.vehicle_home, self.connections[0].from_node, 0, "service")
        last_depot = self.select_depot(self.connections[-1].to_node, self.vehicle_home)
        last2refill_depot = Connection(self.connections[-1].to_node, last_depot, 0, "service")
        lastrefill2home_connection = Connection(last_depot, self.vehicle_home, 0, "service")
        route = []
        for i in range(len(self.connections)):
            if demanded_salt > self.vehicle_capacity:
                demanded_salt = 0
                try:
                    next_connection = self.connections[i + 1]
                    depot = self.select_depot(self.connections[i].to_node, next_connection.from_node)
                    route.append(Connection(self.connections[i].to_node, depot, 0, "service"))
                    route.append(Connection(depot, next_connection.from_node, 0, "service"))
                except IndexError:
                    # We are at the last salting connection so there is no need to refill the salt
                    pass
            else:
                route.append(self.connections[i])
            demanded_salt += self.connections[i].dem

        # Input the service connections for start/end points and also final depo refill
        route.insert(0, home2first_connection)
        route.append(last2refill_depot)
        route.append(lastrefill2home_connection)
        return route

    def is_feasible(self):
        return True

    def evaluate(self):
        route = self.construct_route()
        total_distance = 0

        for i in range(len(route)):
            current_connection = route[i]
            total_distance += self.problem.distances[(current_connection.from_node, current_connection.to_node)].distance
            try:
                next_connection = route[i + 1]
                total_distance += self.problem.distances[(current_connection.to_node, next_connection.from_node)].distance
            except IndexError:
                pass
        return total_distance

    def move1(self):
        pass

    def move2(self):
        pass

    def __str__(self):
        return f"VehiclePlan(connections={self.connections})"

    def __repr__(self):
        return self.__str__()


class Plan:
    def __init__(self, vehicles, depots, problem):
        self.depots = depots
        self.problem = problem
        self.vehicle_plans = {vehicle["id"]: VehiclePlan(vehicle["id"], vehicle["capacity"],
                                                              vehicle["home"], self.depots, problem) for vehicle in vehicles.values()}

    def evaluate(self):
        return sum(vehicle_plan.evaluate() for vehicle_plan in self.vehicle_plans.values())

    def is_feasible(self):
        return all(vehicle_plan.is_feasible() for vehicle_plan in self.vehicle_plans.values())

    def __str__(self):
        return f"Plan(vehicle_plans={self.vehicle_plans})"

    def __repr__(self):
        return self.__str__()

    def generate_output_route(self, from_node, to_node, salted):
        result = []
        for path in self.problem.distances[(from_node, to_node)].paths:
            result.append({
                "arc": (path[0], path[1]),
                "salted": salted,
            })

        return result

    def generate_output(self):
        output = []
        for vehicle_id, vehicle_plan in self.vehicle_plans.items():
            output.append({})
            route = []
            for vehicle_plan in self.vehicle_plans.values():
                for i in range(len(vehicle_plan.route)):
                    transit = vehicle_plan.route[i]
                    # TODO update the second transit also for i + 1
                    if transit.type in ["arc", "edge"]:
                        route.append({
                            "arc": (transit.from_node, transit.to_node),
                            "salted": True
                        })
                    else:
                        route.extend(self.generate_output_route(transit.from_node, transit.to_node, False))
                    try:
                          next_transit = vehicle_plan.route[i + 1]
                          route.extend(self.generate_output_route(transit.to_node, next_transit.from_node, False))
                    except IndexError:
                        pass
                    
            output[-1] = {
                "vehicle": vehicle_id,
                "route": route
            }
        return output

class ShortestPath:
    def __init__(self, paths, distance,time=None):
        self.paths = paths
        self.distance = distance
        self.time=time

    def __str__(self) -> str:
        return f"ShortestPath(paths={self.paths},distance={self.distance})"
    
    def __repr__(self):
        return self.__str__()
