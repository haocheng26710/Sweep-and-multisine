from __future__ import annotations

import pytest

from dataset_node_resolution import dataset_node_by_java_tag


class FakeDatasetNode:
    def __init__(self, java_tag: str, label: str):
        self._java_tag = java_tag
        self.label = label

    def tag(self) -> str:
        return self._java_tag


class FakeModel:
    def __init__(self, datasets: list[FakeDatasetNode]):
        self.datasets = datasets

    def __truediv__(self, group: str):
        assert group == "datasets"
        return self.datasets

    def evaluate(self, _expression: str, *, dataset):
        if isinstance(dataset, str):
            raise ValueError(f'Dataset "{dataset}" does not exist.')
        return [1.0]


def test_java_tag_resolver_returns_node_when_label_contains_slash():
    node = FakeDatasetNode("dset1", "研究/解 1")
    model = FakeModel([node])

    with pytest.raises(ValueError, match='Dataset "dset1" does not exist'):
        model.evaluate("freq", dataset="dset1")

    resolved = dataset_node_by_java_tag(model, "dset1")
    assert resolved is node
    assert model.evaluate("freq", dataset=resolved) == [1.0]


@pytest.mark.parametrize("nodes", [[], [FakeDatasetNode("dset1", "a"), FakeDatasetNode("dset1", "b")]])
def test_java_tag_resolver_requires_exactly_one_match(nodes):
    with pytest.raises(RuntimeError, match="Expected exactly one dataset"):
        dataset_node_by_java_tag(FakeModel(nodes), "dset1")
