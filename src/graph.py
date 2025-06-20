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

    def __str__(self) -> str:
        return str(self.data)

    def create_graph(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        
        # Add nodes with attributes
        for label, node in self.nodes.items():
            graph.add_node(label, u=(label in self.U),
                          is_depot=(label in self.depots)))
        
        # Add edges with attributes
        def add_edge_attributes(edge, data):
            attrs = {
                'time': data['time'],
                'length': data['len'],
            }
            if 'dem' in data:
                attrs['demand'] = data['dem']
            return attrs
        
        # Add all types of edges
        for (u, v), data in self.arcs.items():
            graph.add_edge(u, v, **add_edge_attributes((u, v), data))
        
        for (u, v), data in self.arcs_required.items():
            graph.add_edge(u, v, **add_edge_attributes((u, v), data))
        
        for (u, v), data in self.edges_required.items():
            graph.add_edge(u, v, **add_edge_attributes((u, v), data))
            graph.add_edge(v, u, **add_edge_attributes((v, u), data))
        
        return graph

    def create_dual_graph(self, graph: nx.DiGraph) -> nx.DiGraph:
        """Create a dual graph where edges become nodes"""
        dual_graph = nx.DiGraph()
        
        for edge in graph.edges():
            dual_graph.add_node(edge)
        
        # Connect edges based on traversal rules
        for node in dual_graph.nodes():
            exit_node = node[1]
            if graph.nodes[exit_node]['u']:
                # U-turn allowed - connect to all outgoing edges
                for out_edge in graph.out_edges(exit_node):
                    dual_graph.add_edge(node, out_edge)
            else:
                # No U-turn - connect to all outgoing edges except reverse
                for out_edge in graph.out_edges(exit_node):
                    if node != (out_edge[1], out_edge[0]):
                        dual_graph.add_edge(node, out_edge)
        
        return dual_graph
        
    def visualize_graph(self, graph: nx.DiGraph, title: str = "Graph Visualization"):
        """Visualize the graph with improved formatting"""
        plt.figure(figsize=(12, 8))   
        pos = nx.spring_layout(graph, k=0.15, iterations=50)
        
        # Draw nodes
        node_colors = []
        for n in graph.nodes():
            if graph.nodes[n].get('is_depot', False):
                node_colors.append('green')  # Depot nodes are green
            elif graph.nodes[n]['u']:
                node_colors.append('red')    # U-turn nodes are red
            else:
                node_colors.append('skyblue') # Regular nodes are blue
        nx.draw_networkx_nodes(graph, pos, node_color=node_colors, node_size=500)
        nx.draw_networkx_labels(graph, pos, font_size=14, font_weight='bold')
        
        # Draw edges with arrows
        nx.draw_networkx_edges(graph, pos, arrowstyle='->', arrowsize=10)


# Edge labels - only show for edges with demand
          # Create edge labels with no duplicates for bidirectional edges
        edge_labels = {}
        processed_pairs = set()

        for u, v, data in graph.edges(data=True):
            if (u, v) in processed_pairs:  # Skip if already processed
                continue
            
            # Get demands for both directions
            demand_uv = data.get('demand', 0)
            demand_vu = graph.edges.get((v, u), {}).get('demand', 0) if graph.has_edge(v, u) else 0
            
            # Mark both directions as processed
            processed_pairs.update({(u, v), (v, u)})
            
            # Only proceed if at least one direction has demand
            if demand_uv <= 0 and demand_vu <= 0:
                continue
            
            # Show label for direction with higher demand
            edge_key = (u, v) if demand_uv >= demand_vu else (v, u)
            edge_labels[edge_key] = str(max(demand_uv, demand_vu))
        
        nx.draw_networkx_edge_labels(
            graph, pos,
            edge_labels=edge_labels,
            font_size=12,
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.9),
            label_pos=0.5,  # Centered label position
            rotate=False,
            horizontalalignment='center',
            verticalalignment='center'
                )
                
        plt.title(title, fontsize=18)
        plt.axis('off')
        plt.tight_layout()
        plt.show()

    def visualize_dual_graph(self, dual_graph: nx.DiGraph, original_graph: nx.DiGraph, title: str = "Dual Graph"):
        """Visualize dual graph with U-turn information"""
        plt.figure(figsize=(18, 12))
        
        pos = nx.spring_layout(dual_graph, k=1.0, iterations=200, seed=42)
        
        node_colors = []
        for edge_node in dual_graph.nodes():
            # edge_node is a tuple (u,v) representing original edge
            target_node = edge_node[1] 
            node_colors.append('red' if graph.nodes[target_node].get('u', False) else 'skyblue')
    
        nx.draw_networkx_nodes(
            dual_graph, pos,
            node_color=node_colors,
            node_size=1000,
            alpha=0.8
        )
        
        nx.draw_networkx_edges(
            dual_graph, pos,
            arrowstyle='->',
            arrowsize=25,
            width=1.5,
            edge_color='gray'
        )
     
        node_labels = {
            edge: f"{edge[0]}→{edge[1]}" 
            for edge in dual_graph.nodes()
        }
        
        nx.draw_networkx_labels(
            dual_graph, pos,
            labels=node_labels,
            font_size=10,
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.8)
        )

        plt.scatter([], [], c='red', label='U-turn allowed', alpha=0.8)
        plt.scatter([], [], c='skyblue', label='No U-turn', alpha=0.8)
        plt.legend(loc='upper right')
        
        plt.title(title, fontsize=18)
        plt.axis('off')
        plt.tight_layout()
        plt.show()
if __name__ == "__main__":
    
    problem = Problem(gualandi_data)
    
    # Main Graph
    graph = problem.create_graph()
    problem.visualize_graph(graph, "Main Problem Graph")

    # Dual Graph

    dual_graph = problem.create_dual_graph(graph)
    problem.visualize_dual_graph(dual_graph, "Dual Graph") 
