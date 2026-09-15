from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CommandEntry:
    name: str
    help: str
    category: str
    source: str
    hidden: bool = False


@dataclass
class CommandRegistry:
    entries: dict[str, CommandEntry] = field(default_factory=dict)

    def register(self, entry: CommandEntry) -> None:
        self.entries[entry.name] = entry

    def get(self, name: str) -> CommandEntry | None:
        return self.entries.get(name)

    def all_entries(self) -> list[CommandEntry]:
        return list(self.entries.values())

    def by_category(self) -> dict[str, list[CommandEntry]]:
        groups: dict[str, list[CommandEntry]] = {}
        for entry in self.entries.values():
            groups.setdefault(entry.category, []).append(entry)
        return groups

    def names(self) -> list[str]:
        return sorted(self.entries.keys())
