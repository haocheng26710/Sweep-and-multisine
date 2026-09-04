from collections import deque


def component_count(nodes, edges):
    adjacency = {node: [] for node in nodes}
    for left, right, area in edges:
        if area > 0:
            adjacency[left].append(right)
            adjacency[right].append(left)
    seen = set()
    count = 0
    for start in sorted(nodes):
        if start in seen:
            continue
        count += 1
        seen.add(start)
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in sorted(adjacency[current]):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
    return count
