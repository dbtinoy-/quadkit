"""Tests for strict DomainModel requirements."""
from __future__ import annotations
from dataclasses import dataclass, field
import pytest
from uuid import uuid4
import datetime

from quadkit.domain.models.base import DomainModel


def test_domain_model_requires_dataclass():
    # This class is NOT a dataclass
    class NonDataclassModel(DomainModel):
        name: str

    with pytest.raises(TypeError, match="must be a dataclass"):
        NonDataclassModel(name="test")


def test_domain_model_with_dataclass_works():
    @dataclass
    class ValidModel(DomainModel):
        name: str
        
    m = ValidModel(name="valid")
    assert m.name == "valid"
    assert m.model_dump() == {"name": "valid"}


def test_domain_model_inheritance_works():
    @dataclass
    class Parent(DomainModel):
        p_val: int
        
    @dataclass
    class Child(Parent):
        c_val: int
        
    c = Child(p_val=1, c_val=2)
    assert c.p_val == 1
    assert c.c_val == 2
    assert c.model_dump() == {"p_val": 1, "c_val": 2}


def test_strict_mixed_inheritance():
    # If DomainModel is first, it should enforce dataclass
    class MixedModel(DomainModel, object):
        pass
        
    with pytest.raises(TypeError, match="must be a dataclass"):
        MixedModel()


def test_domain_model_with_default_values():
    @dataclass
    class ModelWithDefaults(DomainModel):
        name: str = "default"
        count: int = 0
        
    m = ModelWithDefaults()
    assert m.name == "default"
    assert m.count == 0
    
    m2 = ModelWithDefaults(name="custom")
    assert m2.name == "custom"


def test_domain_model_with_factory():
    @dataclass
    class ModelWithFactory(DomainModel):
        id: str = field(default_factory=lambda: str(uuid4()))
        created: datetime.datetime = field(default_factory=datetime.datetime.now)
        
    m = ModelWithFactory()
    assert m.id is not None
    assert m.created is not None
    
    m2 = ModelWithFactory()
    # Different IDs because factory creates new ones
    assert m.id != m2.id


def test_domain_model_model_dump():
    @dataclass
    class Person(DomainModel):
        name: str
        age: int
        
    p = Person(name="John", age=30)
    dump = p.model_dump()
    assert dump == {"name": "John", "age": 30}


def test_domain_model_model_dump_exclude():
    @dataclass
    class Person(DomainModel):
        name: str
        age: int
        
    p = Person(name="John", age=30)
    dump = p.model_dump(exclude={"age"})
    assert dump == {"name": "John"}


def test_domain_model_model_dump_include():
    @dataclass
    class Person(DomainModel):
        name: str
        age: int
        
    p = Person(name="John", age=30)
    dump = p.model_dump(include={"name"})
    assert dump == {"name": "John"}


def test_domain_model_model_dump_json():
    @dataclass
    class Person(DomainModel):
        name: str
        age: int
        
    p = Person(name="John", age=30)
    dump = p.model_dump(mode="json")
    assert dump == {"name": "John", "age": 30}


def test_domain_model_model_validate():
    @dataclass
    class Person(DomainModel):
        name: str
        age: int
        
    p = Person.model_validate({"name": "John", "age": 30})
    assert p.name == "John"
    assert p.age == 30


def test_domain_model_copy():
    @dataclass
    class Person(DomainModel):
        name: str
        age: int
        
    p1 = Person(name="John", age=30)
    p2 = p1.model_copy()
    
    assert p2.name == "John"
    assert p2.age == 30
    assert p1 is not p2


def test_domain_model_copy_update():
    @dataclass
    class Person(DomainModel):
        name: str
        age: int
        
    p1 = Person(name="John", age=30)
    p2 = p1.model_copy(update={"age": 31})
    
    assert p2.name == "John"
    assert p2.age == 31
    assert p1.age == 30


def test_domain_model_post_init():
    @dataclass
    class ModelWithInit(DomainModel):
        name: str
        upper_name: str = ""
        
        def __post_init__(self) -> None:
            self.upper_name = self.name.upper()
            
    m = ModelWithInit(name="test")
    assert m.upper_name == "TEST"


def test_domain_model_extra_fields():
    @dataclass
    class ModelWithExtra(DomainModel):
        name: str = "default"
        
    m = ModelWithExtra(name="custom")
    m.extra_field = "extra"
    
    extra = m.model_extra
    assert extra is not None
    assert "extra_field" in extra