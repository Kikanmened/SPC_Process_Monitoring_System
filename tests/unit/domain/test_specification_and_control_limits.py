"""The Spec / Control limit separation — the project's defining type decision.

FR-C06, ADR-0003, Phase 7 exit criterion: it is impossible to construct a
ControlLimit from a SpecificationLimit, or the reverse.
"""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError
from tests.factories.domain import a_control_limit, a_specification_limit, aware

from spc_platform.domain import ControlLimit, SpecificationLimit


@pytest.mark.unit
def test_specification_limit_rejects_lsl_not_less_than_usl() -> None:
    with pytest.raises((ValidationError, Exception)) as exc_info:
        a_specification_limit(lsl=10.5, usl=9.5, target=None)
    assert "lsl" in str(exc_info.value).lower() or "strictly less" in str(exc_info.value)


@pytest.mark.unit
def test_specification_limit_rejects_target_outside_limits() -> None:
    with pytest.raises((ValidationError, Exception)):
        a_specification_limit(lsl=9.5, usl=10.5, target=10.6)


@pytest.mark.unit
def test_specification_limit_allows_single_sided_usl_only() -> None:
    limit = a_specification_limit(lsl=None, usl=50.0, target=None)
    assert limit.lsl is None
    assert limit.usl == 50.0


@pytest.mark.unit
def test_specification_limit_requires_at_least_one_side() -> None:
    with pytest.raises((ValidationError, Exception)):
        a_specification_limit(lsl=None, usl=None, target=None)


@pytest.mark.unit
def test_control_limit_requires_lcl_below_centre_below_ucl() -> None:
    with pytest.raises((ValidationError, Exception)):
        a_control_limit(lcl=10.5, centre_line=10.0, ucl=10.3)


@pytest.mark.unit
def test_control_limit_rejects_non_positive_sigma_estimate() -> None:
    with pytest.raises(ValidationError):
        a_control_limit(sigma_estimate=0.0)


@pytest.mark.unit
def test_no_conversion_methods_exist_between_limit_types() -> None:
    """Structural: the conversion path that would make FR-C06 unenforceable."""
    assert not hasattr(SpecificationLimit, "to_control_limit")
    assert not hasattr(SpecificationLimit, "as_control_limit")
    assert not hasattr(ControlLimit, "from_specification")
    assert not hasattr(ControlLimit, "from_specification_limit")
    assert not hasattr(ControlLimit, "to_specification_limit")


@pytest.mark.unit
def test_control_limit_constructor_does_not_accept_specification() -> None:
    """Type-level seam: no parameter can take a SpecificationLimit."""
    parameters = inspect.signature(ControlLimit).parameters
    assert "specification" not in parameters
    assert "specification_limit" not in parameters
    assert "usl" not in parameters
    assert "lsl" not in parameters
    assert "target" not in parameters


@pytest.mark.unit
def test_specification_limit_constructor_does_not_accept_control_fields() -> None:
    parameters = inspect.signature(SpecificationLimit).parameters
    assert "baseline_id" not in parameters
    assert "centre_line" not in parameters
    assert "lcl" not in parameters
    assert "ucl" not in parameters
    assert "sigma_estimator" not in parameters


@pytest.mark.unit
def test_limit_types_are_not_subclasses_of_each_other() -> None:
    assert not issubclass(ControlLimit, SpecificationLimit)
    assert not issubclass(SpecificationLimit, ControlLimit)


@pytest.mark.unit
def test_control_limit_cannot_be_validated_from_specification_payload() -> None:
    """Passing a specification-shaped dict into ControlLimit must fail."""
    spec = a_specification_limit()
    with pytest.raises(ValidationError):
        ControlLimit.model_validate(spec.model_dump())


@pytest.mark.unit
def test_specification_limit_cannot_be_validated_from_control_payload() -> None:
    control = a_control_limit()
    with pytest.raises(ValidationError):
        SpecificationLimit.model_validate(control.model_dump())


@pytest.mark.unit
def test_specification_limit_rejects_naive_effective_from() -> None:
    with pytest.raises((ValidationError, Exception)):
        a_specification_limit(effective_from=aware().replace(tzinfo=None))
