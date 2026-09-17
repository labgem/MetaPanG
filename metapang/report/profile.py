"""Self-contained HTML report for a profile run, exposing the .tsv outputs."""

import getpass
import html
from datetime import datetime
from pathlib import Path

from metapang import __version__ as metapang_version
from metapang.core.profile.strains import StrainProfile


def _esc(v) -> str:
    """HTML-escape a value as text."""
    return html.escape(str(v))


def _status_counts(comp) -> tuple[int, int, int]:
    """Return the (observed, reassigned, imputed) family counts of a component."""
    st = comp.family_status or {}
    return (sum(1 for v in st.values() if v == "observed"),
            sum(1 for v in st.values() if v == "reassigned"),
            sum(1 for v in st.values() if v == "imputed"))


def _strains_table(profile: StrainProfile) -> str:
    """Render the per-strain summary table for one species."""
    comps = sorted(profile.components, key=lambda c: c.ra, reverse=True)
    rows = []
    for c in comps:
        anchor = c.anchor_refs[0] if c.anchor_refs else f"comp{c.component_id}"
        extra = f" <span class='muted'>(+{len(c.anchor_refs) - 1})</span>" if len(c.anchor_refs) > 1 else ""
        n_obs, n_re, n_imp = _status_counts(c)
        ra = c.ra * 100
        rows.append(
            "<tr>"
            f"<td><span class='mono'>{_esc(anchor)}</span>{extra}</td>"
            f"<td class='num'>{c.abundance:.3f}</td>"
            f"<td class='ra'><div class='bar'><span style='width:{ra:.1f}%'></span></div>"
            f"<span class='ra-val'>{ra:.2f}%</span></td>"
            f"<td class='num'>{len(c.family_ids)}</td>"
            f"<td class='num'><span class='badge obs'>{n_obs}</span></td>"
            f"<td class='num'><span class='badge reasg'>{n_re}</span></td>"
            f"<td class='num'><span class='badge imp'>{n_imp}</span></td>"
            "</tr>"
        )
    if not rows:
        return "<p class='muted'>No strains detected above threshold.</p>"
    head = ("<tr><th>Anchor</th><th>Abundance</th><th>Relative abundance</th>"
            "<th>#genes</th><th>observed</th><th>reassigned</th><th>imputed</th></tr>")
    return f"<table class='data'><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table>"


def _selection_table(profile: StrainProfile) -> str:
    """Render the greedy selection trace table for one species."""
    trace = profile.selection.trace
    if not trace:
        return "<p class='muted'>Empty selection trace.</p>"
    rows = []
    for i, s in enumerate(trace, 1):
        cls = "ok" if s.accepted else "no"
        rows.append(
            "<tr>"
            f"<td class='num'>{i}</td>"
            f"<td><span class='mono'>{_esc(s.added_label)}</span></td>"
            f"<td class='num'>{s.residual:.3f}</td>"
            f"<td class='num'>{s.cv_error:.4f}</td>"
            f"<td><span class='pill {cls}'>{'kept' if s.accepted else 'stopped'}</span></td>"
            f"<td>{_esc(s.stop_reason or '')}</td>"
            "</tr>"
        )
    head = ("<tr><th>step</th><th>candidate</th><th>residual</th><th>cv error</th>"
            "<th>decision</th><th>stop reason</th></tr>")
    return f"<table class='data'><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table>"


def _species_section(idx: int, candidate: str, profile: StrainProfile,
                     reads_mapped: int, reads_total: int) -> str:
    """Render one species panel (stats, strains, selection, genes tables)."""
    reads = "-"
    if reads_total:
        reads = f"{reads_mapped:,} / {reads_total:,} <span class='muted'>({100 * reads_mapped / reads_total:.1f}%)</span>"
    stats = (
        f"<div class='stats'>"
        f"<div class='stat'><span class='k'>{profile.k}</span><span class='l'>strains</span></div>"
        f"<div class='stat'><span class='k'>{reads}</span><span class='l'>reads mapped</span></div>"
        f"</div>"
    )
    return (
        f"<section class='panel' id='sp{idx}' data-panel>"
        f"<h2><span class='mono'>{_esc(candidate)}</span></h2>"
        f"{stats}"
        f"<h3>Strains</h3>{_strains_table(profile)}"
        f"<h3>Selection trace</h3>{_selection_table(profile)}"
        f"</section>"
    )


def render_profile_report(sample_name: str, collection: str,
                          results: list[tuple[str, StrainProfile, int, int]]) -> str:
    """Build the full self-contained HTML report string for a profile run."""
    tab_parts = []
    for i, (cand, _p, _m, _t) in enumerate(results):
        active = " active" if i == 0 else ""
        tab_parts.append(
            f"<button class='tab{active}' onclick='showPanel({i})'>{_esc(cand)}</button>"
        )
    tabs = "".join(tab_parts)
    panels = "".join(_species_section(i, cand, prof, mapped, total)
                     for i, (cand, prof, mapped, total) in enumerate(results))
    if not results:
        panels = "<p class='muted'>No candidate species were profiled.</p>"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    meta = (
        f"<div class='meta'>"
        f"<span><b>Sample</b> {_esc(sample_name)}</span>"
        f"<span><b>Collection</b> {_esc(collection)}</span>"
        f"<span><b>Species</b> {len(results)}</span>"
        f"<span><b>Date</b> {_esc(now)}</span>"
        f"<span><b>User</b> {_esc(getpass.getuser())}</span>"
        f"<span><b>MetaPanG</b> v{_esc(metapang_version)}</span>"
        f"</div>"
    )
    return _PAGE.format(sample=_esc(sample_name), meta=meta, tabs=tabs, panels=panels, css=_CSS, js=_JS)


def write_profile_report(out_dir: Path, sample_name: str, collection: str,
                         results: list[tuple[str, StrainProfile, int, int]]) -> Path:
    """Write report.html into out_dir and return its path."""
    out = out_dir / "report.html"
    out.write_text(render_profile_report(sample_name, collection, results))
    return out


_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1c2230;--muted:#6b7280;--line:#e5e7eb;--accent:#3b82f6;
--obs:#16a34a;--reasg:#d97706;--imp:#6b7280;--bar:#dbeafe}
@media(prefers-color-scheme:dark){:root{--bg:#0f1420;--card:#161d2b;--fg:#e6e9ef;--muted:#98a2b3;
--line:#26304480;--accent:#60a5fa;--bar:#1e3a5f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:24px}
header h1{margin:0 0 4px;font-size:22px}
.meta{display:flex;flex-wrap:wrap;gap:6px 18px;color:var(--muted);font-size:13px;margin:8px 0 20px}
.meta b{color:var(--fg);font-weight:600;margin-right:4px}
.tabs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px}
.tab{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:7px 12px;border-radius:8px;
cursor:pointer;font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.panel{display:none;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:16px}
.panel.active{display:block}
h2{margin:0 0 12px;font-size:18px}
h3{margin:20px 0 8px;font-size:14px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.stats{display:flex;gap:24px;margin-bottom:14px}
.stat{display:flex;flex-direction:column}
.stat .k{font-size:22px;font-weight:700}
.stat .l{font-size:12px;color:var(--muted)}
table.data{width:100%;border-collapse:collapse;font-size:13px;margin:6px 0}
.data th,.data td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line)}
.data th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.data td.num{text-align:right;font-variant-numeric:tabular-nums}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.muted{color:var(--muted)}
.ra{white-space:nowrap}
.bar{display:inline-block;width:90px;height:8px;background:var(--bar);border-radius:4px;overflow:hidden;vertical-align:middle;margin-right:8px}
.bar span{display:block;height:100%;background:var(--accent)}
.ra-val{font-variant-numeric:tabular-nums}
.badge{display:inline-block;min-width:20px;text-align:center;padding:1px 7px;border-radius:6px;font-size:12px;color:#fff}
.badge.obs{background:var(--obs)}.badge.reasg{background:var(--reasg)}.badge.imp{background:var(--imp)}
.pill{padding:1px 8px;border-radius:6px;font-size:12px}
.pill.ok{background:#dcfce7;color:#166534}.pill.no{background:#fee2e2;color:#991b1b}
@media(prefers-color-scheme:dark){.pill.ok{background:#14532d;color:#bbf7d0}.pill.no{background:#7f1d1d;color:#fecaca}}
details{margin:10px 0;border:1px solid var(--line);border-radius:8px;padding:6px 12px}
summary{cursor:pointer;font-size:13px;font-weight:600;color:var(--muted)}
"""

_JS = """
function showPanel(i){
  document.querySelectorAll('[data-panel]').forEach((p,j)=>p.classList.toggle('active',i===j));
  document.querySelectorAll('.tab').forEach((t,j)=>t.classList.toggle('active',i===j));
}
document.addEventListener('DOMContentLoaded',function(){
  var first=document.querySelector('[data-panel]');
  if(first)first.classList.add('active');
});
"""

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MetaPanG profile - {sample}</title>
<style>{css}</style></head>
<body><div class="wrap">
<header><h1>MetaPanG profile report</h1>{meta}</header>
<div class="tabs">{tabs}</div>
{panels}
</div><script>{js}</script></body></html>
"""
