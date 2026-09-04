from __future__ import annotations

from typing import Any


def dataset_node_by_java_tag(model: Any, dataset_tag: str):
    """Resolve an MPh dataset Node by its stable COMSOL Java tag.

    MPh string dataset arguments are display names, not Java tags.  Returning
    the actual Node avoids both that ambiguity and path parsing of labels such
    as ``研究/解 1``.
    """

    datasets = model / "datasets"
    nodes = list(datasets)
    matches = [node for node in nodes if node.tag() == dataset_tag]
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one dataset with Java tag {dataset_tag}; "
            f"found {[node.tag() for node in nodes]}"
        )
    return matches[0]
