"""
app/routes/graph_routing.py — Shortest Path Algorithm for Dynamic Re-routing

Implements Dijkstra's / A* Graph Algorithm to dynamically calculate the shortest, 
most optimal maritime route across global choke-points, avoiding high-risk delays.

Graph vertices: Maritime Hubs and Choke-points
Graph edges: Distances in shipping days
"""
import heapq
import math

class MaritimeGraph:
    def __init__(self):
        self.edges = {}

    def add_edge(self, from_node, to_node, weight_days):
        if from_node not in self.edges:
            self.edges[from_node] = []
        if to_node not in self.edges:
            self.edges[to_node] = []
        # Bi-directional graph
        self.edges[from_node].append((to_node, weight_days))
        self.edges[to_node].append((from_node, weight_days))

    def calculate_shortest_path(self, start, end, blocked_nodes=None):
        """
        Dijkstra's shortest-path algorithm for live traffic re-routing.
        Finds the fastest route from start to end, bypassing any blocked_nodes.
        """
        if blocked_nodes is None:
            blocked_nodes = set()
            
        distances = {node: float('inf') for node in self.edges}
        distances[start] = 0
        priority_queue = [(0, start)]
        previous_nodes = {node: None for node in self.edges}

        while priority_queue:
            current_distance, current_node = heapq.heappop(priority_queue)

            if current_node == end:
                break

            if current_distance > distances[current_node]:
                continue

            for neighbor, weight in self.edges.get(current_node, []):
                # Live traffic detection: treat blocked nodes as infinite cost
                if neighbor in blocked_nodes:
                    continue

                distance = current_distance + weight

                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    previous_nodes[neighbor] = current_node
                    heapq.heappush(priority_queue, (distance, neighbor))

        # Reconstruct path
        path = []
        curr = end
        while curr is not None:
            path.append(curr)
            curr = previous_nodes.get(curr)
        path.reverse()

        if path[0] == start:
            return path, distances[end]
        return None, float('inf')


def initialize_global_maritime_network() -> MaritimeGraph:
    g = MaritimeGraph()
    # Europe
    g.add_edge("Rotterdam", "Gibraltar", 4)
    g.add_edge("Hamburg", "Gibraltar", 5)
    # Mediterranean & Middle East
    g.add_edge("Gibraltar", "Suez", 6)
    g.add_edge("Suez", "Jebel Ali", 7)
    # Africa
    g.add_edge("Gibraltar", "Cape of Good Hope", 14)
    g.add_edge("Cape of Good Hope", "Jebel Ali", 12)
    g.add_edge("Cape of Good Hope", "Singapore", 15)
    # Asia
    g.add_edge("Jebel Ali", "Mumbai", 3)
    g.add_edge("Mumbai", "Malacca", 6)
    g.add_edge("Jebel Ali", "Singapore", 9)
    g.add_edge("Singapore", "Shanghai", 5)
    g.add_edge("Singapore", "Shenzhen", 4)
    # Trans-Pacific
    g.add_edge("Shanghai", "Los Angeles", 14)
    g.add_edge("Shenzhen", "Los Angeles", 15)
    g.add_edge("Los Angeles", "Panama", 8)
    return g

def calculate_dynamic_reroute(origin_region: str, dest_region: str, high_risk_chokepoints: list = None) -> dict:
    """
    Called by the Synthesizer logic to dynamically recalculate paths using Dijkstra.
    If 'Suez' is high risk, it completely bypasses it.
    """
    graph = initialize_global_maritime_network()
    
    # Map raw input to nearest graph nodes
    o_mapped = "Shanghai" if "shanghai" in origin_region.lower() or "china" in origin_region.lower() else "Singapore"
    d_mapped = "Rotterdam" if "rotterdam" in dest_region.lower() or "europe" in dest_region.lower() else "Jebel Ali"
    
    blocked = set(high_risk_chokepoints) if high_risk_chokepoints else set()
    
    # Calculate shortest baseline path (without blocks)
    base_path, base_cost = graph.calculate_shortest_path(o_mapped, d_mapped, set())
    
    # Calculate dynamic path (with blocks)
    alt_path, alt_cost = graph.calculate_shortest_path(o_mapped, d_mapped, blocked)
    
    if alt_path and alt_path != base_path:
        return {
            "via": " → ".join(alt_path),
            "extra_days": alt_cost - base_cost,
            "extra_cost_usd": (alt_cost - base_cost) * 55000,
            "risk_level": "LOW (Dynamic Reroute)",
            "description": f"Dijkstra shortest-path algorithm actively bypassed {', '.join(blocked)}. Reroute spans {alt_cost} days."
        }
        
    # Fallback to rule-based logic if graphing doesn't find a path
    return None
