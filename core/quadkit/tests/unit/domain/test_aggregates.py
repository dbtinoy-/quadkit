"""Tests for AggregateRoots."""
from __future__ import annotations
from dataclasses import dataclass, field
import pytest
from quadkit.domain.models.aggregate import AggregateRoot, VersionedAggregate, EventSourcedAggregate
from quadkit.contracts.domain.events import DomainEvent

@dataclass(frozen=True)
class PriceChanged(DomainEvent):
    new_price: int = 0

@dataclass
class Product(AggregateRoot):
    price: int = 0

    def change_price(self, new_val: int):
        self.price = new_val
        self._record_event(PriceChanged(new_price=new_val))

def test_aggregate_root_events():
    product = Product(price=10)
    product.change_price(20)
    
    events = list(product.collect_events())
    assert len(events) == 1
    assert isinstance(events[0], PriceChanged)
    assert events[0].new_price == 20
    
    # Second collect should be empty
    assert len(list(product.collect_events())) == 0

def test_versioned_aggregate():
    @dataclass
    class VProduct(VersionedAggregate):
        price: int = 0
        
    v = VProduct(price=10)
    assert v.version == 0
    v._increment_version()
    assert v.version == 1

def test_event_sourced_aggregate():
    @dataclass
    class ESProduct(EventSourcedAggregate):
        price: int = 0
        
        def on_price_changed(self, event: PriceChanged):
            self.price = event.new_price
            
    es = ESProduct(price=10)
    es.apply(PriceChanged(new_price=30))
    
    assert es.price == 30
    assert es.version == 1
    
    events = list(es.collect_events())
    assert len(events) == 1
    assert events[0].sequence_number == 1
    assert events[0].aggregate_id == es.id
    assert events[0].aggregate_type == "ESProduct"
