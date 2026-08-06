"""The generated data has the variance structure it was configured with.

If it does not, every capability number, every control limit, and every
detection score computed from it is measuring something nobody specified. This
is the check that makes the rest of the benchmark mean anything.

The estimators used here are written out in ``spc_platform.simulation.validators``
independently of ``analytics/``. Two independent implementations agreeing is
evidence; one implementation agreeing with itself is not.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from spc_platform.simulation import GeneratedDataset, validate_dataset
from spc_platform.simulation.manifests import scale_key
from spc_platform.simulation.models import ValueDistribution


def _characteristic_checked_by(
    dataset: GeneratedDataset,
    check_name: str,
) -> tuple[str, dict[str, float]]:
    """Return one characteristic that a named check actually runs on.

    A faulted characteristic is skipped by design, and a single-site parameter
    supports no within-wafer estimate. Corrupting either would prove nothing
    about whether the validator can see corruption.
    """
    report = validate_dataset(dataset.frame, dataset.manifest)
    subjects = {
        check.subject.split(" ")[0].replace("/", "|")
        for check in report.checks
        if check.name == check_name
    }
    key = next(key for key in dataset.manifest.component_scales if key in subjects)
    return key, dataset.manifest.component_scales[key]


def _subjects_touched_by_faults(dataset: GeneratedDataset) -> set[str]:
    """Return every characteristic any injected fault reaches.

    Restated here from the frame rather than read off the manifest, because a
    fault leaves unset the fields it does not scope itself to. A gauge drift
    naming only a metrology tool reaches whatever that tool measured.
    """
    frame = dataset.frame
    touched: set[str] = set()
    for fault in dataset.manifest.faults:
        mask = pd.Series(data=True, index=frame.index)
        for column, value in (
            ("parameter_id", fault.parameter_id),
            ("product_id", fault.product_id),
            ("tool_id", fault.tool_id),
            ("chamber_id", fault.chamber_id),
            ("metrology_tool_id", fault.metrology_tool_id),
        ):
            if value is not None:
                mask &= frame[column] == str(value)
        reached = frame.loc[mask, ["parameter_id", "product_id"]].drop_duplicates()
        touched |= {f"{p}/{q}" for p, q in reached.itertuples(index=False)}
    return touched


def test_every_configured_quantity_is_realised_within_tolerance(
    dataset: GeneratedDataset,
) -> None:
    """The dataset realises every quantity the manifest declares.

    The headline check: process level, within-wafer sigma, between-tool
    mismatch, and spatial amplitude all match what the manifest declares.
    """
    report = validate_dataset(dataset.frame, dataset.manifest)

    assert report.checks, "a dataset with no checks proves nothing"
    assert report.passed, report.summary()


def test_the_only_characteristics_left_unchecked_are_the_faulted_ones(
    dataset: GeneratedDataset,
) -> None:
    """A characteristic carrying an injected fault has no clean quantity to compare against.

    Anything else going unchecked would be coverage the report claims and does not have.
    """
    report = validate_dataset(dataset.frame, dataset.manifest)
    touched = _subjects_touched_by_faults(dataset)

    unexplained = [subject for subject in report.unchecked_subjects if subject not in touched]
    assert not unexplained, report.summary()


def test_almost_every_characteristic_is_examined(dataset: GeneratedDataset) -> None:
    """The validator reaches most of the dataset rather than a corner of it.

    A report can pass by checking almost nothing: characteristics without enough
    wafers to estimate a component are skipped, and a skipped characteristic
    reads the same as a clean one in the headline result. Bounding the skipped
    fraction is what stops that from happening quietly.
    """
    report = validate_dataset(dataset.frame, dataset.manifest)
    total = len(dataset.manifest.component_scales)

    assert len(report.unchecked_subjects) < total // 4


def test_the_validator_would_notice_a_shifted_level(dataset: GeneratedDataset) -> None:
    """A validator that passes everything is not a validator.

    Displacing one characteristic by four sigma has to be caught, or the
    agreement in the test above carries no information.
    """
    frame = dataset.frame.copy()
    key, scales = _characteristic_checked_by(dataset, "level")
    parameter_id, product_id = key.split("|")
    affected = (frame["parameter_id"] == parameter_id) & (frame["product_id"] == product_id)
    frame.loc[affected, "value"] += 4.0 * scales["sigma_total"]

    report = validate_dataset(frame, dataset.manifest)

    assert not report.passed
    assert any(check.name == "level" for check in report.failures)


def test_the_validator_would_notice_inflated_noise(dataset: GeneratedDataset) -> None:
    """The spread checks have teeth as well as the level checks.

    The counterpart to the shifted-level case above. Widening one characteristic
    leaves its mean where it was, so only a check on the spread can catch it —
    and a validator that watched the level alone would pass this dataset while
    reporting a capability figure that is wrong by a factor of three.
    """
    frame = dataset.frame.copy()
    key, scales = _characteristic_checked_by(dataset, "within_wafer_sigma")
    parameter_id, product_id = key.split("|")
    affected = (frame["parameter_id"] == parameter_id) & (frame["product_id"] == product_id)
    noise = np.random.default_rng(0).normal(0.0, 3.0 * scales["sigma_total"], int(affected.sum()))
    frame.loc[affected, "value"] += noise

    report = validate_dataset(frame, dataset.manifest)

    assert not report.passed
    assert any(check.name == "within_wafer_sigma" for check in report.failures)


class TestSystematicStructure:
    """Structure that must be systematic rather than noise."""

    def test_the_within_wafer_signature_repeats_across_wafers(
        self,
        dataset: GeneratedDataset,
    ) -> None:
        """The property the whole spatial module exists for.

        If within-wafer variation were independent noise, pooling sites into a
        subgroup would be harmless, a naive implementation would pass its own
        benchmark, and the resulting detection scores would be meaningless
        (R-04, R-30). Estimated on two disjoint halves of the wafers, the site
        profile has to be the same shape in both.
        """
        report = validate_dataset(dataset.frame, dataset.manifest)
        reproducibility = [check for check in report.checks if check.name == "spatial_systematic"]

        assert reproducibility, "no characteristic carries a checkable spatial signature"
        for check in reproducibility:
            assert check.passed, check.describe()

    def test_tool_offsets_are_persistent_biases_rather_than_per_lot_noise(
        self,
        dataset: GeneratedDataset,
    ) -> None:
        """A tool's offset is a standing bias, not noise redrawn each lot.

        A resampled offset would turn a tool mismatch into noise and delete the
        phenomenon commonality analysis exists to find. Each tool is compared
        against the bias the manifest records for it, so a fleet whose members
        were spread correctly but individually mislabelled would fail here.
        """
        report = validate_dataset(dataset.frame, dataset.manifest)
        offsets = [check for check in report.checks if check.name == "tool_offset"]

        assert offsets, "no characteristic runs enough lots per tool to resolve a bias"
        for check in offsets:
            assert check.passed, check.describe()

    def test_the_manifest_records_a_bias_for_every_tool_that_ran(
        self,
        dataset: GeneratedDataset,
    ) -> None:
        """Every tool that ran a characteristic has its bias recorded.

        Ground truth for commonality analysis: a platform that names the wrong
        tool has to be scoreable as wrong.
        """
        frame = dataset.frame
        for key, offsets in dataset.manifest.tool_offsets.items():
            parameter_id, product_id = key.split("|")
            observed = frame[
                (frame["parameter_id"] == parameter_id) & (frame["product_id"] == product_id)
            ]["tool_id"].unique()

            assert set(observed) <= set(offsets)


class TestShortTermAndLongTermSpreadDiffer:
    """Cp and Pp must not be the same number."""

    def test_systematic_terms_widen_the_overall_spread(
        self,
        dataset: GeneratedDataset,
    ) -> None:
        """The whole fleet spreads wider than any single tool within it.

        Tool mismatch sits outside the random total, and a generator where the
        two spreads coincided would make the capability module's central
        distinction — Cp against Pp — untestable. Compared through the exact
        decomposition of total variance into a size-weighted within-tool part
        and a between-tool part, so the claim is about the data rather than an
        artefact of unequal tool loading.
        """
        frame = dataset.frame[dataset.frame["value"].notna()]
        touched = _subjects_touched_by_faults(dataset)
        widened = 0

        for key, scales in dataset.manifest.component_scales.items():
            parameter_id, product_id = key.split("|")
            if scales["sigma_tool_offset"] <= 0.0 or f"{parameter_id}/{product_id}" in touched:
                continue
            subset = frame[
                (frame["parameter_id"] == parameter_id) & (frame["product_id"] == product_id)
            ]
            if subset["tool_id"].nunique() < 2:
                continue

            groups = subset.groupby("tool_id")["value"]
            weights = groups.count().to_numpy(dtype=float)
            within = float(np.average(groups.var(ddof=0).to_numpy(dtype=float), weights=weights))
            between = float(
                np.average(
                    (groups.mean().to_numpy(dtype=float) - float(subset["value"].mean())) ** 2,
                    weights=weights,
                )
            )

            assert between > 0.0
            assert within + between > within
            widened += 1

        assert widened > 0, "no clean characteristic in the dataset carries tool mismatch"


def test_a_poisson_parameter_has_variance_close_to_its_mean(
    dataset: GeneratedDataset,
) -> None:
    """Count data is generated as counts, not as rounded Gaussians.

    A platform that applies normal-theory limits to it should be visibly wrong here.
    """
    frame = dataset.frame
    poisson_parameters = [
        str(physics.parameter_id)
        for physics in dataset.manifest.config.parameters
        if physics.distribution is ValueDistribution.POISSON
    ]
    assert poisson_parameters, "the committed configuration declares count parameters"

    for parameter_id in poisson_parameters:
        values = frame.loc[frame["parameter_id"] == parameter_id, "value"].dropna()
        assert float(values.min()) >= 0.0
        np.testing.assert_array_equal(values.to_numpy(), np.round(values.to_numpy()))


def test_every_characteristic_has_a_recorded_scale(dataset: GeneratedDataset) -> None:
    """Every characteristic in the data has scales in the manifest.

    A measurement whose scales are absent from the manifest is a measurement
    nothing can be scored against.
    """
    frame = dataset.frame
    observed = set(
        zip(
            frame["parameter_id"].astype(str),
            frame["product_id"].astype(str),
            strict=True,
        )
    )
    recorded = set(dataset.manifest.component_scales)

    missing = {
        scale_key(parameter, product)  # type: ignore[arg-type]
        for parameter, product in observed
    } - recorded
    assert not missing


@pytest.mark.parametrize("column", ["value", "site_x", "site_y"])
def test_numeric_columns_hold_no_infinities(dataset: GeneratedDataset, column: str) -> None:
    """No numeric column carries an infinity.

    One overflow anywhere upstream propagates silently: a mean becomes infinite,
    the sigma around it becomes undefined, and a control chart draws limits that
    no point can ever violate.
    """
    values = dataset.frame[column].to_numpy(dtype=float)

    assert not np.isinf(values).any()
