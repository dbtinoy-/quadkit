"""Security documentation values remain dependency-free immutable declarations."""

from dataclasses import FrozenInstanceError

import pytest

from quadkit.contracts.web.security_metadata import (
    HttpBearerDocumentation,
    HttpErrorMessageDocumentation,
)


def test_bearer_default_is_backward_compatible_without_rejection_inference():
    assert HttpBearerDocumentation("bearerAuth") == HttpBearerDocumentation()
    assert HttpBearerDocumentation().rejections == ()


def test_nested_rejection_declarations_are_immutable_primitive_values():
    rejection = HttpErrorMessageDocumentation(403, "forbidden")
    metadata = HttpBearerDocumentation(rejections=(rejection,))
    with pytest.raises(FrozenInstanceError):
        metadata.rejections = ()
    with pytest.raises(FrozenInstanceError):
        rejection.status_code = 401
    assert isinstance(hash(metadata), int)
