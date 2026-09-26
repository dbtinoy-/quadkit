from __future__ import annotations

import pathlib
import tomllib

from quadkit.contracts.cli.protocols import CliContributorProtocol
from quadkit.storage.cli.contributor import StorageCliContributor


def test_storage_contributor_implements_protocol_shape() -> None:
    contributor = StorageCliContributor()

    assert isinstance(contributor, CliContributorProtocol)
    assert contributor.contributor_id == "storage"


def test_storage_contributor_exposes_storage_driver_generator() -> None:
    contributor = StorageCliContributor()
    definitions = contributor.get_generators()

    assert [definition.name for definition in definitions] == ["storage_driver"]
    assert definitions[0].generator_path == (
        "quadkit.storage.cli.generators.storage_driver:StorageDriverGenerator"
    )
    assert definitions[0].default_output_dir == "src/storage/backends"
    assert definitions[0].contributor == "storage"


def test_storage_pyproject_declares_cli_contributor_entry_point() -> None:
    pyproject_path = pathlib.Path(__file__).resolve().parents[2] / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text())
    group = data["project"]["entry-points"]["quadkit.cli.contributors"]

    assert group["storage"] == "quadkit.storage.cli.contributor:StorageCliContributor"
