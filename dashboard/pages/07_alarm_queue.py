"""Alarm and disposition queue with acknowledgement (FR-A01 - FR-A03)."""

from __future__ import annotations

from datetime import datetime

import streamlit as st
from dashboard.components.refusal_panel import refusal_markdown
from dashboard.layouts.page import page_header
from dashboard.state.session import default_actor, ensure_bundle

from spc_platform.application.use_cases import (
    acknowledge_violation,
    build_alarm_queue,
    evaluate_lot,
    record_disposition,
)
from spc_platform.common.errors import SPCPlatformError
from spc_platform.domain.enums import DispositionAction
from spc_platform.domain.ids import LotId, OcapId, ParameterId

page_header(
    "Alarm queue",
    "Open violations by severity and age. OCAP field shown when linked.",
)

bundle = ensure_bundle(st.session_state)  # type: ignore[arg-type]
actor = default_actor()

with st.expander("Evaluate a lot to raise violations"):
    if st.button("Evaluate LOT-DEMO / OXIDE_THK"):
        try:
            result = evaluate_lot(
                bundle.services,
                actor=actor,
                parameter_id=ParameterId("OXIDE_THK"),
                lot_id=LotId("LOT-DEMO"),
                window_start=datetime.fromisoformat("2025-07-01T00:00:00+00:00"),
                window_end=datetime.fromisoformat("2025-07-14T00:00:00+00:00"),
            )
            st.success(
                f"Evaluated {result.points_evaluated} points; "
                f"{len(result.violations)} violation(s)."
            )
        except SPCPlatformError as exc:
            st.markdown(refusal_markdown("Evaluation refused", str(exc)))

queue = build_alarm_queue(bundle.services, actor=actor)
st.metric("Open alarms", queue.n_open)

if not queue.items:
    st.info("No open violations.")
else:
    for item in queue.items:
        ocap = item.ocap_id or "(no OCAP linked)"
        st.write(
            f"**{item.severity.value.upper()}** `{item.violation_id}` · "
            f"{item.parameter_id} · rule={item.rule_id} · "
            f"value={item.statistic_value:.4g} · OCAP={ocap} · "
            f"{item.timestamp.isoformat()}"
        )
        cols = st.columns(2)
        with cols[0]:
            if st.button(f"Acknowledge {item.violation_id}", key=f"ack-{item.violation_id}"):
                try:
                    acknowledge_violation(
                        bundle.services,
                        actor=actor,
                        violation_id=item.violation_id,
                        reason="acknowledged from dashboard",
                    )
                    st.rerun()
                except SPCPlatformError as exc:
                    st.markdown(refusal_markdown("Acknowledge failed", str(exc)))
        with cols[1]:
            action = st.selectbox(
                "Disposition",
                options=[a.value for a in DispositionAction],
                key=f"disp-action-{item.violation_id}",
            )
            reason = st.text_input(
                "Disposition reason",
                key=f"disp-reason-{item.violation_id}",
                value="hold pending review",
            )
            if st.button(
                f"Record disposition {item.violation_id}", key=f"disp-{item.violation_id}"
            ):
                try:
                    record_disposition(
                        bundle.services,
                        actor=actor,
                        lot_id=LotId("LOT-DEMO"),
                        action=DispositionAction(action),
                        reason=reason,
                        ocap_id=None if item.ocap_id is None else OcapId(item.ocap_id),
                    )
                    st.success("Disposition recorded.")
                except SPCPlatformError as exc:
                    st.markdown(refusal_markdown("Disposition failed", str(exc)))
