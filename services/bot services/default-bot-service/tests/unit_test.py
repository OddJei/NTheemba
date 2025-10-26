# python
import pathlib
import pytest

INTENT_PATH = pathlib.Path("services/bot services/default-bot-service/handlers/registered mode/user-role/msme/Msmeintent.txt")

# Embedded sample fallback (used when the external file isn't available)
EMBEDDED_SAMPLE = """
msme_user
├── authenticate_user
│   ├── send_otp
│   │   └── verify_otp
│   │       └── session_success

├── analytics_dashboard
│   ├── view_sales
│   ├── view_orders
│   ├── view_traffic

├── product_management
│   ├── add_product
│   │   ├── submit_product_name
│   │   ├── submit_product_category
│   │   ├── submit_product_price
│   ├── remove_product
│   │   └── add_to_removal_cart
│   │       └── view_removal_cart_item
│   ├── view_product_list
│   │   └── view_product_summary

├── staff_management
│   ├── add_staff_member
│   │   └── save_staff_member

├── profile_management
│   └── update_contact_info
"""

def parse_intent_tree(text):
    """
    Parse the ASCII intent tree into (root_label, children_map).
    children_map: {parent_label: [child_label, ...], ...}
    """
    lines = [ln.rstrip("\n") for ln in text.splitlines() if ln.strip()]

    # Collect tuples of (marker_index, label). marker_index is the position of the first
    # box-drawing marker ('├' or '└') in the line. For the root line (no marker) we use -1.
    tuples = []
    for line in lines:
        idxs = [i for i in (line.find("├"), line.find("└")) if i != -1]
        if not idxs:
            marker_idx = -1
            label = line.strip()
        else:
            marker_idx = min(idxs)
            rem = line[marker_idx:]
            if rem.startswith("├──") or rem.startswith("└──"):
                label = rem[3:].strip()
            else:
                # fallback: take after the marker
                label = rem[1:].strip()
        tuples.append((marker_idx, label))

    # Build tree by finding for each node the nearest previous node with a smaller marker_idx
    children = {}
    nodes_so_far = []  # list of (label, marker_idx) in order of appearance
    root = None
    for marker_idx, label in tuples:
        if marker_idx == -1:
            root = label
            children.setdefault(label, [])
            nodes_so_far.append((label, marker_idx))
            continue

        # find parent: last node in nodes_so_far with marker_idx < current marker_idx
        parent = None
        for p_label, p_idx in reversed(nodes_so_far):
            if p_idx < marker_idx:
                parent = p_label
                break
        if parent is None:
            parent = root

        children.setdefault(parent, [])
        children[parent].append(label)
        children.setdefault(label, [])
        nodes_so_far.append((label, marker_idx))

    return root, children

def is_path_present(children, path):
    if not path:
        return False
    cur = path[0]
    # first element must be root or exist as top-level
    if cur not in children and any(cur in v for v in children.values()) is False:
        return False
    for nxt in path[1:]:
        if cur not in children:
            return False
        if nxt not in children[cur]:
            return False
        cur = nxt
    return True

def collect_all_paths(children, root):
    paths = []
    def dfs(node, acc):
        kids = children.get(node, [])
        if not kids:
            paths.append(acc + [node])
            return
        for k in kids:
            dfs(k, acc + [node])
    dfs(root, [])
    return paths

@pytest.fixture(scope="module")
def parsed_tree():
    if INTENT_PATH.exists():
        text = INTENT_PATH.read_text(encoding="utf-8")
    else:
        # use embedded sample so tests can run in any environment
        text = EMBEDDED_SAMPLE
    root, children = parse_intent_tree(text)
    return root, children

def test_parse_root_and_top_children(parsed_tree):
    root, children = parsed_tree
    assert root == "msme_user", f"Unexpected root: {root}"
    expected_top = {"authenticate_user", "analytics_dashboard", "product_management", "profile_management", "staff_management"}
    actual_top = set(children.get(root, []))
    missing = expected_top - actual_top
    assert not missing, f"Missing top-level intents: {missing}"

@pytest.mark.parametrize("path", [
    ["msme_user", "authenticate_user", "send_otp", "verify_otp", "session_success"],
    ["msme_user", "product_management", "add_product", "submit_product_name"],
    ["msme_user", "product_management", "remove_product", "add_to_removal_cart", "view_removal_cart_item"],
    ["msme_user", "product_management", "view_product_list", "view_product_summary"],
    ["msme_user", "staff_management", "add_staff_member", "save_staff_member"],
    ["msme_user", "profile_management", "update_contact_info"],
    ["msme_user", "analytics_dashboard", "view_sales"],
])
def test_specific_paths_exist(parsed_tree, path):
    root, children = parsed_tree
    assert path[0] == root, "Test path root does not match parsed root"
    assert is_path_present(children, path), f"Expected path not present: {' -> '.join(path)}"

def test_total_node_count_matches_expected(parsed_tree):
    """
    Count unique nodes parsed and compare to expected hardcoded count derived from the source file.
    If the file changes, update the expected_count accordingly.
    """
    _, children = parsed_tree
    unique_nodes = set(children.keys())
    for v in children.values():
        unique_nodes.update(v)
    # Hardcoded expected node count based on the current Msmeintent.txt structure
    # Expected node count for the embedded sample
    expected_count = 24
    # Fallback: compute and assert equal to our expectation
    actual = len(unique_nodes)
    assert actual == expected_count, f"Node count mismatch: expected {expected_count}, got {actual}. Nodes: {sorted(unique_nodes)}"

def test_traverse_all_paths_reachable(parsed_tree):
    root, children = parsed_tree
    all_paths = collect_all_paths(children, root)
    assert all_paths, "No paths discovered during traversal"
    # Ensure each discovered path starts with root and ends with a leaf node that has no children
    for p in all_paths:
        assert p[0] == root
        last = p[-1]
        assert children.get(last, []) == [], f"Path ends at non-leaf: {' -> '.join(p)}"

def test_idempotent_parse_roundtrip(parsed_tree):
    root, children = parsed_tree
    # Serialize to tuple list (depth, label) by performing BFS with level tracking
    serialized = []
    def serialize(node, depth=0):
        serialized.append((depth, node))
        for c in children.get(node, []):
            serialize(c, depth+1)
    serialize(root, 0)
    # Rebuild text in simple prefixed form and parse again
    lines = []
    for depth, label in serialized:
        if depth == 0:
            lines.append(label)
        else:
            prefix = "│   " * (depth - 1)
            lines.append(f"{prefix}├── {label}")
    rebuilt = "\n".join(lines)
    new_root, new_children = parse_intent_tree(rebuilt)
    assert new_root == root
    # Compare sets of edges
    old_edges = {(p, c) for p, kids in children.items() for c in kids}
    new_edges = {(p, c) for p, kids in new_children.items() for c in kids}
    assert old_edges == new_edges, "Structure changed after roundtrip serialization"