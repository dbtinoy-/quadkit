from typing import Annotated

import pytest

from quadkit.di.container import Container
from quadkit.di.markers import Named, OptionalDep


class Database:
    def __init__(self, name: str = "default"):
        self.name = name

class ServiceWithNamed:
    def __init__(self, db: Annotated[Database, Named("primary")]):
        self.db = db

class ServiceWithOptional:
    def __init__(self, db: Annotated[Database | None, OptionalDep()] = None):
        self.db = db

class SyncDep:
    pass

class SyncRoot:
    def __init__(self, dep: SyncDep):
        self.dep = dep

@pytest.mark.asyncio
async def test_named_injection():
    container = Container()
    db1 = Database("primary")
    db2 = Database("secondary")

    container.singleton((Database, "primary"), db1)
    container.singleton((Database, "secondary"), db2)
    container.transient(ServiceWithNamed, ServiceWithNamed)

    # Debug: Check if qualifier is correctly seen
    params = container._type_hint_resolver.get_injectable_parameters(ServiceWithNamed)
    db_param = params["db"]
    print(f"DEBUG: db_param qualifier: {db_param.qualifier}")

    service = await container.resolve(ServiceWithNamed)
    assert service.db.name == "primary"

@pytest.mark.asyncio
async def test_optional_injection_missing():
    container = Container()
    container.transient(ServiceWithOptional, ServiceWithOptional)

    service = await container.resolve(ServiceWithOptional)
    assert service.db is None

@pytest.mark.asyncio
async def test_optional_injection_present():
    container = Container()
    db = Database()
    container.singleton(Database, db)
    container.transient(ServiceWithOptional, ServiceWithOptional)

    service = await container.resolve(ServiceWithOptional)
    assert service.db is db


# sync resolution removed; resolution is async-only
@pytest.mark.asyncio
async def test_async_resolve_works():
    container = Container()
    container.singleton(SyncDep, SyncDep)
    container.singleton(SyncRoot, SyncRoot)

    root = await container.resolve(SyncRoot)
    assert isinstance(root, SyncRoot)
    assert isinstance(root.dep, SyncDep)



# following tests unchanged

def test_container_validation_cycle():
    container = Container()

    class CycleA: pass
    class CycleB: pass

    CycleA.__init__ = lambda self, b: None
    CycleA.__init__.__annotations__ = {"b": CycleB}
    CycleB.__init__ = lambda self, a: None
    CycleB.__init__.__annotations__ = {"a": CycleA}

    # Disable eager validation to test validate_graph()
    container.transient(CycleA, CycleA, validate=False)
    container.transient(CycleB, CycleB, validate=False)

    issues = container.validate()
    print(f"DEBUG issues: {issues}")
    assert any("Circular dependency" in issue for issue in issues)

def test_container_validation_scope_mismatch():
    container = Container()

    class ScopedS: pass
    class SingletonS: pass

    SingletonS.__init__ = lambda self, s: None
    SingletonS.__init__.__annotations__ = {"s": ScopedS}

    container.singleton(SingletonS, SingletonS, validate=False)
    container.scoped(ScopedS, ScopedS, validate=False)

    issues = container.validate()
    print(f"DEBUG scope issues: {issues}")
    assert any("Scope violation" in issue for issue in issues)

def test_container_validation_missing_dep():
    container = Container()

    class MissingDepService: pass
    MissingDepService.__init__ = lambda self, d: None
    MissingDepService.__init__.__annotations__ = {"d": Database}

    container.transient(MissingDepService, MissingDepService, validate=False)

    issues = container.validate()
    print(f"DEBUG missing issues: {issues}")
    # Database is not registered in THIS container instance
    assert any("Missing dependency" in issue for issue in issues)
