from __future__ import annotations

from datetime import datetime, timezone

from app.schemas import BriefResponse


def build_weekly_brief(risks: list[dict], spikes: int) -> BriefResponse:
    """Render the brief from a compute_risks() result and a signal-spike count."""
    stockouts = [r for r in risks if r["risk_type"] == "stockout"]
    overstocks = [r for r in risks if r["risk_type"] == "overstock"]

    top_so = stockouts[:5]
    top_os = overstocks[:3]

    bullets: list[str] = []
    for r in top_so:
        bullets.append(
            f"Stockout risk: {r['sku_id']} @ {r['warehouse_id']} — "
            f"~{r['expected_demand_in_lead_time']:.0f} units needed in {r['lead_time_days']}d lead window "
            f"vs {r['available_units']:.0f} available."
        )
    for r in top_os:
        bullets.append(
            f"Overstock: {r['sku_id']} @ {r['warehouse_id']} — "
            f"~{r['weeks_of_cover']:.1f} weeks of cover with softening demand."
        )
    if not bullets:
        bullets.append("No critical inventory exceptions detected in the current snapshot.")

    summary = (
        f"This week the control tower flags {len(stockouts)} stockout-skewed positions and "
        f"{len(overstocks)} overstock-skewed positions across monitored warehouses. "
        f"External signal spikes (WoW): {spikes} SKUs with elevated social/search intensity."
    )

    return BriefResponse(
        title="Weekly buyer brief",
        summary=summary,
        bullets=bullets[:12],
        stockout_count=len(stockouts),
        overstock_count=len(overstocks),
        signal_spikes=spikes,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
