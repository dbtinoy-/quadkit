"""Shared authored use-case fixtures; independent of pytest module names."""

from quadkit.result import Ok


def spec():
    return {
        "validate_inputs": True,
        "typed_outcomes": True,
        "related_reads": [
            {"name": "category", "key": "input.category_id", "fields": ["title"]}
        ],
        "writes": [{"field": "category_title", "source": "related.category.title"}],
    }


class Repository:
    def __init__(self, result):
        self.result = result
        self.reads = []
        self.updates = []

    async def get(self, key):
        self.reads.append(key)
        return self.result

    async def update(self, key, values):
        self.updates.append((key, values))
        return Ok(values)
