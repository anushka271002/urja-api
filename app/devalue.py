"""Minimal decoder for SvelteKit's `devalue` format (flat array, ints are pointers)."""

def resolve(arr: list, i: int = 0):
    if i < 0:  # devalue uses negatives for undefined/NaN etc.
        return None
    v = arr[i]
    if isinstance(v, dict):
        return {k: resolve(arr, p) for k, p in v.items()}
    if isinstance(v, list):
        return [resolve(arr, p) for p in v]
    return v


def decode_data_json(payload: dict):
    """__data.json holds several nodes; the one with real data is the last 'data' node."""
    nodes = [n for n in payload["nodes"] if n and n.get("type") == "data"]
    if not nodes:
        raise ValueError("no data node in __data.json")
    return resolve(nodes[-1]["data"])