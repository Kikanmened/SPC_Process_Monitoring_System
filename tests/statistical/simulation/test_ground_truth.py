"""Every fault the manifest claims is actually present in the data.

Ground truth that the data does not contain is worse than no ground truth: a
detector that missed a fault which was never injected would be scored as having
failed, and one that found a fault larger than declared would be scored as
having succeeded on the wrong thing. Everything the detection scorecard will
later claim rests on the correspondence checked here.

Each fault is looked for using the signature that distinguishes its kind. The
point is not only that something changed at the onset — it is that the *right*
thing changed, in the right place, by the declared amount.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import numpy as np
import pandas as pd
import pytest

from spc_platform.domain.enums import SpatialSignature
from spc_platform.simulation import GeneratedDataset
from spc_platform.simulation.manifests import DatasetManifest, FaultRecord, scale_key
from spc_platform.simulation.models import FaultKind

if TYPE_CHECKING:
    from numpy.typing import NDArray


def wafer_means(
    frame: pd.DataFrame,
    fault: FaultRecord,
    manifest: DatasetManifest | None = None,
) -> pd.DataFrame:
    """Return one row per measured wafer for the characteristic a fault names.

    When the fault names no product, the values are centred on each product's
    own target before pooling. The same parameter sits at a different level on
    each device, so pooling the raw values would make a change in product mix
    look like a change in the process.
    """
    subset = frame[
        (frame["parameter_id"] == str(fault.parameter_id))
        & (frame["measurement_status"] == "valid")
    ].copy()
    if fault.product_id is not None:
        subset = subset[subset["product_id"] == str(fault.product_id)]
    elif manifest is not None:
        targets = {
            key.split("|")[1]: values["target"]
            for key, values in manifest.component_scales.items()
            if key.startswith(f"{fault.parameter_id}|")
        }
        subset["value"] -= subset["product_id"].map(targets)

    grouped = subset.groupby(["lot_id", "wafer_id", "timestamp", "tool_id"], as_index=False)
    return grouped.agg(value=("value", "mean")).sort_values("timestamp")


def split_at_onset(means: pd.DataFrame, fault: FaultRecord) -> tuple[pd.Series, pd.Series]:
    """Return the wafer means before and from the fault's onset."""
    before = means.loc[means["timestamp"] < fault.onset_at, "value"]
    after = means.loc[means["timestamp"] >= fault.onset_at, "value"]
    return before, after


_MAX_DESIGN_CONDITION = 5.0
"""Above this, the sampled phases are too bunched for the fit to mean anything."""


class _Sinusoid(NamedTuple):
    """A fitted cycle and how well the data pins it down."""

    amplitude: float
    standard_error: float


def _fit_sinusoid(
    values: NDArray[np.float64],
    lot_index: NDArray[np.int_],
    period: float,
) -> _Sinusoid:
    """Fit a sinusoid of ``period`` to ``values`` at the lot numbers they carry.

    A least-squares fit rather than an FFT. A characteristic is measured on a
    fraction of lots and the products take turns, so the sampling is irregular
    in the only axis the cycle is paced in; an FFT would read that irregularity
    as frequency content and put its peak somewhere else. Fitting sine and
    cosine together absorbs the phase, so the fault's onset does not have to be
    recovered first.

    The standard error comes back with the amplitude because a lot mean carries
    the tool it ran on and the lot-to-lot noise as well as the cycle, and over
    the few dozen lots a characteristic is measured on those are the same size
    as the cycle itself. An amplitude quoted without it cannot be compared with
    anything.
    """
    angle = 2.0 * np.pi * lot_index / period
    design = np.column_stack([np.cos(angle), np.sin(angle)])

    # At a period the sampling cannot resolve — twice the measurement interval,
    # say — every point lands on the same two phases, the sine column collapses,
    # and the fit answers with an enormous amplitude of no physical meaning. Such
    # a period has to be reported as unresolvable rather than as a strong cycle,
    # or a search over periods would always end up at one of them.
    if np.linalg.cond(design) > _MAX_DESIGN_CONDITION:
        return _Sinusoid(amplitude=float("nan"), standard_error=float("inf"))

    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)

    residual = values - design @ coefficients
    degrees_of_freedom = max(len(values) - design.shape[1], 1)
    variance = float(residual @ residual) / degrees_of_freedom
    return _Sinusoid(
        amplitude=float(np.hypot(*coefficients)),
        standard_error=float(np.sqrt(2.0 * variance / len(values))),
    )


@pytest.fixture(scope="module")
def manifest(dataset: GeneratedDataset) -> DatasetManifest:
    """Return the shared dataset's ground-truth manifest."""
    return dataset.manifest


def test_every_configured_fault_reaches_the_manifest(dataset: GeneratedDataset) -> None:
    """Every fault the configuration asks for is recorded as ground truth.

    A fault that fell out between the two would leave the platform scored
    against a dataset that does not contain it.
    """
    configured = {spec.fault_id for spec in dataset.manifest.config.faults}
    recorded = {fault.fault_id for fault in dataset.manifest.faults}

    assert recorded == configured


def test_every_fault_onset_falls_inside_the_generated_window(
    dataset: GeneratedDataset,
) -> None:
    """A fault whose onset sits past the last lot is recorded and not realised."""
    timestamps = dataset.frame["timestamp"]
    first, last = timestamps.min(), timestamps.max()

    for fault in dataset.manifest.faults:
        assert first <= fault.onset_at <= last, fault.fault_id


class TestStepShift:
    """A furnace maintenance event: the level moves once and stays moved."""

    def test_the_level_moves_by_the_declared_magnitude(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The level moves by the magnitude the manifest declares.

        Compared against the recorded absolute magnitude rather than against the
        configured sigma multiple, because sigma differs by product and the
        absolute figure is the one a detection score would be graded on.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.STEP_SHIFT)
        assert fault.magnitude_absolute is not None

        before, after = split_at_onset(wafer_means(dataset.frame, fault), fault)
        observed = float(after.mean()) - float(before.mean())

        scales = manifest.component_scales[
            scale_key(fault.parameter_id, fault.product_id)  # type: ignore[arg-type]
        ]
        standard_error = scales["sigma_lot"] * np.sqrt(1 / len(before) + 1 / len(after))
        assert observed == pytest.approx(
            fault.magnitude_absolute, abs=5.0 * max(standard_error, 1e-9)
        )

    def test_the_shift_does_not_reach_another_product(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The fault names one product.

        A shift that leaked to the others would make product commonality analysis point at a
        process nobody changed.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.STEP_SHIFT)
        frame = dataset.frame
        others = [
            key.split("|")[1]
            for key in manifest.component_scales
            if key.startswith(f"{fault.parameter_id}|") and not key.endswith(f"|{fault.product_id}")
        ]
        assert others, "the parameter is charted on more than one product"

        for product_id in others:
            scales = manifest.component_scales[f"{fault.parameter_id}|{product_id}"]
            subset = frame[
                (frame["parameter_id"] == str(fault.parameter_id))
                & (frame["product_id"] == product_id)
            ]
            before = subset.loc[subset["timestamp"] < fault.onset_at, "value"]
            after = subset.loc[subset["timestamp"] >= fault.onset_at, "value"]

            observed = abs(float(after.mean()) - float(before.mean()))
            standard_error = scales["sigma_lot"] * np.sqrt(1 / len(before) + 1 / len(after))
            assert observed < max(4.0 * standard_error, 0.5 * scales["sigma_total"]), product_id


class TestGradualDrift:
    """Etch chamber seasoning: the level ramps from the onset to the end."""

    def test_the_level_ramps_to_the_declared_magnitude(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The level ramps, reaching the declared magnitude by the end of the run.

        Compared head against tail of the post-onset window rather than
        before against after: a drift's average displacement is half its final
        one, so a before-and-after comparison would report the magnitude as
        half what the manifest declares and look like a generator defect.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.GRADUAL_DRIFT)
        assert fault.magnitude_absolute is not None

        means = wafer_means(dataset.frame, fault)
        after = means[means["timestamp"] >= fault.onset_at]
        head = after.head(len(after) // 5)["value"].mean()
        tail = after.tail(len(after) // 5)["value"].mean()

        # The ramp reaches its full magnitude at the last lot, so comparing the
        # first fifth against the last recovers most but not all of it.
        travelled = float(tail) - float(head)
        assert travelled == pytest.approx(fault.magnitude_absolute, rel=0.45)

    def test_the_level_is_undisturbed_before_the_onset(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """Before the declared onset the characteristic is undisturbed.

        A drift that had already started would make the declared onset wrong,
        and every time-to-detection measured against it meaningless.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.GRADUAL_DRIFT)
        means = wafer_means(dataset.frame, fault)
        before = means[means["timestamp"] < fault.onset_at]
        scales = manifest.component_scales[
            scale_key(fault.parameter_id, fault.product_id)  # type: ignore[arg-type]
        ]

        first = float(before.head(len(before) // 3)["value"].mean())
        last = float(before.tail(len(before) // 3)["value"].mean())
        assert abs(last - first) < scales["sigma_total"]


class TestCyclic:
    """An ambient temperature cycle in the track."""

    def test_the_declared_period_dominates_the_spectrum(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """Visible in the frequency domain, which is what makes it separable from a drift.

        A platform treating it as one would chase a moving target.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.CYCLIC)
        assert fault.period_lots is not None

        means = wafer_means(dataset.frame, fault)
        after = means[means["timestamp"] >= fault.onset_at]
        lots = after.groupby("lot_id", sort=True)["value"].mean()
        index = lots.index.str.removeprefix("LOT-").astype(int).to_numpy()
        centred = lots.to_numpy(dtype=float) - float(lots.mean())

        # Bounded by what the sampling can resolve at either end. Below twice
        # the gap between measurements the fit aliases onto the sampling itself
        # and reports an amplitude that says nothing about the process; above a
        # third of the observed span there are too few cycles to separate a
        # cycle from a drift.
        shortest = 2.0 * float(np.median(np.diff(index)))
        longest = (float(index.max()) - float(index.min())) / 3.0
        assert shortest < fault.period_lots < longest, "the period is resolvable at all"

        periods = np.arange(shortest, longest, 0.5)
        amplitudes = np.array([_fit_sinusoid(centred, index, p).amplitude for p in periods])
        best = float(periods[int(np.nanargmax(amplitudes))])

        assert best == pytest.approx(fault.period_lots, rel=0.1)

    def test_the_cycle_carries_the_declared_amplitude(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The cycle is as large as the manifest says it is.

        A period recovered at the wrong amplitude would let a platform pass a
        detection benchmark it should fail, and fail one it should pass.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.CYCLIC)
        assert fault.period_lots is not None
        assert fault.magnitude_absolute is not None

        means = wafer_means(dataset.frame, fault)
        after = means[means["timestamp"] >= fault.onset_at]
        lots = after.groupby("lot_id", sort=True)["value"].mean()
        index = lots.index.str.removeprefix("LOT-").astype(int).to_numpy()
        centred = lots.to_numpy(dtype=float) - float(lots.mean())

        declared = abs(fault.magnitude_absolute)
        fitted = _fit_sinusoid(centred, index, float(fault.period_lots))

        # Guard first: an estimate too vague to exclude half the declared
        # amplitude would agree with the manifest whatever the generator did.
        assert fitted.standard_error < 0.25 * declared
        assert abs(fitted.amplitude - declared) < 4.0 * fitted.standard_error


class TestVarianceIncrease:
    """A degrading gas flow controller: the spread grows, the level does not."""

    def test_the_variance_grows_by_the_declared_factor(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The factor is on the variance, not on sigma.

        A generator that applied it to sigma would put a number in the manifest that is wrong by a
        square, and every capability comparison scored against it would inherit that.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.VARIANCE_INCREASE)
        assert fault.variance_factor is not None

        scales = manifest.component_scales[
            scale_key(fault.parameter_id, fault.product_id)  # type: ignore[arg-type]
        ]
        means = wafer_means(dataset.frame, fault)
        before, after = split_at_onset(means, fault)

        # Only the process terms are widened; the gauge is untouched. The wafer
        # mean carries lot, wafer, and gauge terms, so the expected ratio has to
        # be computed rather than taken as the factor itself.
        widened = scales["sigma_wafer"] ** 2 * fault.variance_factor
        untouched = scales["sigma_lot"] ** 2
        expected = np.sqrt((widened + untouched) / (scales["sigma_wafer"] ** 2 + untouched))
        observed = float(after.std(ddof=1)) / float(before.std(ddof=1))

        assert observed == pytest.approx(float(expected), rel=0.25)

    def test_the_level_does_not_move(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The spread grows and the level does not move with it.

        The S chart should signal before the mean chart, which is only true if
        the mean genuinely stays put.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.VARIANCE_INCREASE)
        scales = manifest.component_scales[
            scale_key(fault.parameter_id, fault.product_id)  # type: ignore[arg-type]
        ]
        before, after = split_at_onset(wafer_means(dataset.frame, fault), fault)

        shift = abs(float(after.mean()) - float(before.mean()))
        standard_error = scales["sigma_lot"] * np.sqrt(1 / len(before) + 1 / len(after))
        assert shift < 4.0 * standard_error


class TestToolExcursion:
    """One scanner out of specification: invisible pooled, obvious by tool."""

    def test_the_named_tool_moves_and_the_others_do_not(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The named tool moves and the rest of the fleet stays where it was.

        This is what makes the fault a commonality problem rather than a process
        one. If the other tools moved too, a platform could find it on a pooled
        chart and never have to attribute it to equipment at all.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.TOOL_EXCURSION)
        assert fault.tool_id is not None

        means = wafer_means(dataset.frame, fault, manifest)
        after = means[means["timestamp"] >= fault.onset_at]
        before = means[means["timestamp"] < fault.onset_at]

        def shift(subset_after: pd.DataFrame, subset_before: pd.DataFrame) -> float:
            return float(subset_after["value"].mean()) - float(subset_before["value"].mean())

        named = str(fault.tool_id)
        on_tool = shift(after[after["tool_id"] == named], before[before["tool_id"] == named])
        off_tool = shift(after[after["tool_id"] != named], before[before["tool_id"] != named])

        # The fault names no product, and sigma differs by product, so the
        # comparison is against the smallest sigma the parameter carries.
        smallest = min(
            values["sigma_total"]
            for key, values in manifest.component_scales.items()
            if key.startswith(f"{fault.parameter_id}|")
        )
        assert on_tool > smallest
        assert abs(off_tool) < 0.5 * smallest

    def test_the_excursion_is_smaller_in_the_pooled_data(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The excursion is smaller in the pooled data than on the tool itself.

        This is the property that makes commonality analysis necessary rather
        than decorative: pooling dilutes the excursion by the tool's share of
        lots, and a fleet-wide chart can miss what a per-tool chart shows
        plainly.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.TOOL_EXCURSION)
        means = wafer_means(dataset.frame, fault, manifest)
        after = means[means["timestamp"] >= fault.onset_at]
        before = means[means["timestamp"] < fault.onset_at]

        named = str(fault.tool_id)
        pooled = float(after["value"].mean()) - float(before["value"].mean())
        on_tool = float(after[after["tool_id"] == named]["value"].mean()) - float(
            before[before["tool_id"] == named]["value"].mean()
        )

        assert pooled < on_tool


class TestSpatialChange:
    """Carrier head tilt: the wafer map changes, the wafer mean does not."""

    def test_the_site_profile_changes_shape(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The within-wafer profile takes on a different shape after onset.

        Measured as the correlation between the site profiles either side of the
        onset. A signature change is a change in *shape*, so it is invisible to
        anything that only tracks the wafer mean — which is the reason wafer
        maps exist alongside control charts.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.SPATIAL_CHANGE)
        assert fault.signature is SpatialSignature.ASYMMETRIC

        frame = dataset.frame
        subset = frame[
            (frame["parameter_id"] == str(fault.parameter_id))
            & (frame["product_id"] == str(fault.product_id))
            & frame["value"].notna()
        ].copy()
        subset["centred"] = subset["value"] - subset.groupby("wafer_id")["value"].transform("mean")

        before = subset[subset["timestamp"] < fault.onset_at].groupby("site_id")["centred"].mean()
        after = subset[subset["timestamp"] >= fault.onset_at].groupby("site_id")["centred"].mean()

        # A different shape, not merely a different scale: the correlation
        # between the two profiles has to break down.
        correlation = float(np.corrcoef(before.to_numpy(), after.to_numpy())[0, 1])
        assert correlation < 0.6

    def test_the_wafer_mean_stays_put(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """Only a wafer map shows this fault.

        A mean chart must remain blind to it, or the dataset would not exercise the distinction at
        all.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.SPATIAL_CHANGE)
        scales = manifest.component_scales[
            scale_key(fault.parameter_id, fault.product_id)  # type: ignore[arg-type]
        ]
        before, after = split_at_onset(wafer_means(dataset.frame, fault), fault)

        shift = abs(float(after.mean()) - float(before.mean()))
        standard_error = scales["sigma_lot"] * np.sqrt(1 / len(before) + 1 / len(after))
        assert shift < 4.0 * standard_error

    def test_the_signature_is_asymmetric_after_the_onset(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The new signature is the asymmetric one the manifest names.

        The two halves of the wafer must therefore differ from the wafer mean in
        opposite directions, which is what separates an asymmetric signature
        from a radial one.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.SPATIAL_CHANGE)
        frame = dataset.frame
        subset = frame[
            (frame["parameter_id"] == str(fault.parameter_id))
            & (frame["product_id"] == str(fault.product_id))
            & (frame["timestamp"] >= fault.onset_at)
            & frame["value"].notna()
        ].copy()
        subset["centred"] = subset["value"] - subset.groupby("wafer_id")["value"].transform("mean")

        left = subset.loc[subset["site_x"] < 0, "centred"].mean()
        right = subset.loc[subset["site_x"] > 0, "centred"].mean()

        assert float(left) * float(right) < 0.0


class TestMetrologyDrift:
    """A gauge calibration slip, which is not a process fault at all."""

    def test_the_drift_reaches_every_parameter_the_gauge_measures(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The drift follows the gauge across every parameter it measures.

        That signature is the whole point of separating gauge error from process
        error. A displacement confined to one parameter is a process problem; one
        that follows a gauge onto unrelated parameters is a calibration problem,
        and sending an engineer to the process tool for it wastes a shift.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.METROLOGY_DRIFT)
        assert fault.metrology_tool_id is not None

        frame = dataset.frame
        on_gauge = frame[frame["metrology_tool_id"] == str(fault.metrology_tool_id)]
        parameters = set(on_gauge["parameter_id"].unique())

        assert len(parameters) > 1, "a single-parameter gauge would not exercise the distinction"

        for parameter_id in parameters:
            measured = on_gauge[
                (on_gauge["parameter_id"] == parameter_id) & on_gauge["value"].notna()
            ]
            scales = next(
                values
                for key, values in manifest.component_scales.items()
                if key.startswith(f"{parameter_id}|")
            )
            before = measured.loc[measured["timestamp"] < fault.onset_at, "value"].mean()
            after = measured.loc[measured["timestamp"] >= fault.onset_at, "value"].mean()

            assert float(after) - float(before) > 0.2 * scales["sigma_total"]

    def test_the_same_parameter_on_another_gauge_is_untouched(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """The signature that separates a gauge problem from a process one.

        Reporting this as a process excursion sends engineers to the wrong tool.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.METROLOGY_DRIFT)
        frame = dataset.frame
        gauge = str(fault.metrology_tool_id)
        parameter_id = frame[frame["metrology_tool_id"] == gauge]["parameter_id"].iloc[0]

        others = frame[
            (frame["parameter_id"] == parameter_id)
            & (frame["metrology_tool_id"] != gauge)
            & frame["value"].notna()
        ]
        assert not others.empty, "the parameter is measured by more than one gauge"

        scales = next(
            values
            for key, values in manifest.component_scales.items()
            if key.startswith(f"{parameter_id}|")
        )
        before = others.loc[others["timestamp"] < fault.onset_at, "value"].mean()
        after = others.loc[others["timestamp"] >= fault.onset_at, "value"].mean()

        assert abs(float(after) - float(before)) < 0.5 * scales["sigma_total"]


class TestOutliers:
    """Sensor glitches, emitted unflagged."""

    def test_extreme_points_appear_at_roughly_the_declared_rate(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """Gross errors appear at about the rate the configuration asks for.

        Loosely, because at a rate of a couple in a thousand the count is a
        handful of events and Poisson scatter on a handful is large. The check
        is that the order of magnitude is right, which is enough to catch a
        source applied to the wrong population or applied several times over.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.OUTLIER)
        spec = next(s for s in manifest.config.faults if s.fault_id == fault.fault_id)
        assert spec.rate is not None

        frame = dataset.frame
        subset = frame[
            (frame["parameter_id"] == str(fault.parameter_id))
            & (frame["product_id"] == str(fault.product_id))
            & frame["value"].notna()
        ]
        scales = manifest.component_scales[
            scale_key(fault.parameter_id, fault.product_id)  # type: ignore[arg-type]
        ]
        # Five sigma from target: far beyond anything the clean model produces,
        # and well inside the declared eight-sigma displacement.
        extreme = (subset["value"] - scales["target"]).abs() > 5.0 * scales["sigma_total"]

        observed_rate = float(extreme.mean())
        assert observed_rate == pytest.approx(spec.rate, rel=0.6)

    def test_outliers_are_not_flagged_in_the_data(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """Deciding whether an extreme point matters is the platform's job.

        A dataset that pre-labelled them would hand the benchmark its answer.
        """
        fault = next(f for f in manifest.faults if f.kind is FaultKind.OUTLIER)
        frame = dataset.frame
        subset = frame[
            (frame["parameter_id"] == str(fault.parameter_id))
            & (frame["product_id"] == str(fault.product_id))
            & frame["value"].notna()
        ]
        scales = manifest.component_scales[
            scale_key(fault.parameter_id, fault.product_id)  # type: ignore[arg-type]
        ]
        extreme = subset[(subset["value"] - scales["target"]).abs() > 5.0 * scales["sigma_total"]]

        assert not extreme.empty
        assert set(extreme["measurement_status"].unique()) == {"valid"}


class TestMessiness:
    """The data-quality situations the pipeline must survive."""

    def test_the_manifest_accounts_for_every_row(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """Rates are configured; counts are observed.

        Reconciling the two ends of the ledger is what makes the recorded counts trustworthy: a
        rate applied to the wrong population would still look plausible on its own, and only fails
        to balance against the rows that survived.
        """
        record = manifest.messiness

        expected = (
            record.measurements_before_messiness
            + record.superseded_records  # each carries the remeasurement that replaced it
            - record.missing_measurements
        )

        frame = dataset.frame

        assert len(frame) == expected
        assert record.superseded_records == int((frame["measurement_status"] == "superseded").sum())
        superseded = frame[frame["measurement_status"] == "superseded"]
        assert record.remeasurement_events == len(
            superseded.drop_duplicates(["lot_id", "parameter_id", "wafer_id"])
        )

    def test_a_missing_measurement_is_absent_rather_than_null(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """A gap in a fab's data is a row nobody wrote, not a null somebody did.

        Emitting nulls would let a pipeline impute them, and an imputed point on a control chart is
        a fabricated signal (DATASET_GUIDE.md §5).
        """
        assert manifest.messiness.missing_measurements > 0
        assert not dataset.frame["value"].isna().any()

    def test_a_remeasured_wafer_keeps_both_records(
        self,
        dataset: GeneratedDataset,
        manifest: DatasetManifest,
    ) -> None:
        """Both records survive, the earlier one marked rather than removed.

        Deleting the first would hide the remeasurement, and deciding which
        record counts is a disposition rule the platform has to implement.
        """
        if manifest.messiness.superseded_records == 0:
            pytest.skip("this dataset realised no remeasurements")

        frame = dataset.frame
        superseded = frame[frame["measurement_status"] == "superseded"]
        wafers = set(superseded["wafer_id"].unique())
        replacements = frame[
            frame["wafer_id"].isin(wafers) & (frame["measurement_status"] == "valid")
        ]

        assert not replacements.empty

    def test_measurement_identifiers_are_unique(self, dataset: GeneratedDataset) -> None:
        """No two measurements share an identifier.

        Including across remeasurements, or a superseded record would collide
        with the one that replaced it.
        """
        identifiers = dataset.frame["measurement_id"]

        assert identifiers.is_unique
