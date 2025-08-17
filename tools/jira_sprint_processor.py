#!/usr/bin/env python3

import os
import re
import sys
import argparse
from datetime import datetime, date, timedelta
from typing import Optional, Tuple

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# -----------------------------
# Defaults
# -----------------------------
DEFAULT_DATA_DIR = os.path.join(".", "data", "jira_sprint_processor")
SNAP_SUBDIR = "snapshots_csv"
REPORT_SUBDIR = "reports"


# -----------------------------
# Helpers
# -----------------------------

def anycol(df: pd.DataFrame, candidates):
	for c in candidates:
		if c in df.columns:
			return c
	lower = {c.lower(): c for c in df.columns}
	for c in candidates:
		if c.lower() in lower:
			return lower[c.lower()]
	return None


def parse_sprint_window(df: pd.DataFrame, default_year: int) -> Tuple[Optional[date], Optional[date], Optional[str]]:
	"""
	Parse dates from sprint-like text pattern " - MMDD > MMDD" found in any 'Sprint' column.
	Returns (start_date, end_date, sprint_text) or (None, None, None).
	"""
	sprint_cols = [c for c in df.columns if "sprint" in c.lower()]
	pattern = re.compile(r"-\s*(\d{2})(\d{2})\s*>\s*(\d{2})(\d{2})")
	for col in sprint_cols:
		for val in df[col].dropna().astype(str).head(200):
			m = pattern.search(val)
			if m:
				mm1, dd1, mm2, dd2 = m.groups()
				s_month, s_day = int(mm1), int(dd1)
				e_month, e_day = int(mm2), int(dd2)
				s_year = default_year
				e_year = default_year if e_month >= s_month else default_year + 1
				try:
					return date(s_year, s_month, s_day), date(e_year, e_month, e_day), val
				except Exception:
					continue
	return None, None, None


def normalize(df: pd.DataFrame) -> pd.DataFrame:
	cols = {
		"key": anycol(df, ["Issue key", "Key"]),
		"summary": anycol(df, ["Summary", "Title"]),
		"status": anycol(df, ["Status"]),
		"assignee": anycol(df, ["Assignee", "Assignee name", "Assignee email"]),
		"story_points": anycol(df, ["Story Points", "Σ Story Points", "Story points"]),
		"created": anycol(df, ["Created"]),
		"updated": anycol(df, ["Updated"]),
		"sprint": anycol(df, ["Sprint", "Sprint 1", "Sprints"]),
		"time_spent": anycol(df, ["Σ Time Spent", "Time Spent", "Time spent"]),
		"remaining_estimate": anycol(df, ["Remaining Estimate", "Σ Remaining Estimate"]),
	}
	core = pd.DataFrame({k: df[v] if v in df.columns else pd.NA for k, v in cols.items()})
	for dc in ["created", "updated"]:
		if dc in core.columns:
			core[dc] = pd.to_datetime(core[dc], errors="coerce")
	for nc in ["story_points", "time_spent", "remaining_estimate"]:
		if nc in core.columns:
			core[nc] = pd.to_numeric(core[nc], errors="coerce")
	return core


def latest_snapshot_path(snapshot_dir: str) -> Optional[str]:
	snaps = [f for f in os.listdir(snapshot_dir) if f.startswith("snapshot_") and f.endswith(".csv")] if os.path.isdir(snapshot_dir) else []
	if not snaps:
		return None
	snaps.sort()
	return os.path.join(snapshot_dir, snaps[-1])


def prev_snapshot_path(snapshot_dir: str, exclude: Optional[str]) -> Optional[str]:
	snaps = [f for f in os.listdir(snapshot_dir) if f.startswith("snapshot_") and f.endswith(".csv")] if os.path.isdir(snapshot_dir) else []
	if not snaps:
		return None
	snaps.sort()
	if exclude:
		snaps = [s for s in snaps if not s.endswith(f"{exclude}.csv")]
	return os.path.join(snapshot_dir, snaps[-1]) if snaps else None


def save_snapshot(snapshot_dir: str, df_core: pd.DataFrame, sprint_name: str, sprint_start: Optional[date], sprint_end: Optional[date], today: date) -> Tuple[str, str]:
	stamp = today.isoformat()
	os.makedirs(snapshot_dir, exist_ok=True)
	path = os.path.join(snapshot_dir, f"snapshot_{stamp}.csv")
	meta_path = os.path.join(snapshot_dir, f"snapshot_{stamp}.meta.txt")
	with open(meta_path, "w", encoding="utf-8") as f:
		f.write(f"sprint_name: {sprint_name}\n")
		f.write(f"sprint_start: {sprint_start}\n")
		f.write(f"sprint_end: {sprint_end}\n")
		f.write(f"generated_on: {stamp}\n")
	df_core.to_csv(path, index=False)
	return path, meta_path


def compute_deltas(prev: pd.DataFrame, curr: pd.DataFrame, today_iso: str) -> pd.DataFrame:
	merge = prev.merge(curr, on="key", suffixes=("_prev", "_curr"), how="outer", indicator=True)
	events = []
	def add_event(k, field, old, new, details=None):
		events.append({
			"date": today_iso,
			"issue": k,
			"field": field,
			"old": old,
			"new": new,
			"details": details or ""
		})
	for _, r in merge.iterrows():
		k = r.get("key")
		if r["_merge"] == "left_only":
			add_event(k, "issue_removed", r.get("summary_prev"), "", "Issue not present today")
			continue
		if r["_merge"] == "right_only":
			add_event(k, "issue_added", "", r.get("summary_curr"), "New issue appears today")
			continue
		for field, caster in [("status", str), ("assignee", str)]:
			old = r.get(f"{field}_prev")
			new = r.get(f"{field}_curr")
			if pd.notna(old):
				old = caster(old)
			if pd.notna(new):
				new = caster(new)
			if (pd.isna(old) and pd.notna(new)) or (pd.notna(old) and pd.isna(new)) or (pd.notna(old) and pd.notna(new) and old != new):
				add_event(k, field, old, new)
		for field in ["story_points", "time_spent", "remaining_estimate"]:
			old = r.get(f"{field}_prev")
			new = r.get(f"{field}_curr")
			if (pd.isna(old) and pd.notna(new)) or (pd.notna(old) and pd.isna(new)) or (pd.notna(old) and pd.notna(new) and float(old) != float(new)):
				add_event(k, field, old, new)
	return pd.DataFrame(events)


def parse_worklogs(full_df: pd.DataFrame, sprint_start: Optional[date], sprint_end: Optional[date]) -> pd.DataFrame:
	wl_date_cols = [c for c in full_df.columns if "worklog" in c.lower() and "date" in c.lower()]
	wl_spent_cols = [c for c in full_df.columns if "worklog" in c.lower() and ("time spent" in c.lower() or "timespent" in c.lower())]
	wl_author_cols = [c for c in full_df.columns if "worklog" in c.lower() and "author" in c.lower()]
	rows = []
	issue_col = anycol(full_df, ["Issue key", "Key"])
	for _, row in full_df.iterrows():
		key = row.get(issue_col, None)
		for dcol in wl_date_cols:
			if pd.isna(row.get(dcol)):
				continue
			try:
				d = pd.to_datetime(row.get(dcol)).date()
			except Exception:
				continue
			if sprint_start and sprint_end and (d < sprint_start or d > sprint_end):
				continue
			seconds = None
			for spcol in wl_spent_cols:
				val = row.get(spcol)
				if pd.isna(val):
					continue
				try:
					seconds = float(val)
				except Exception:
					# Try parse like "3h 30m"
					txt = str(val)
					hours = sum(float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*h", txt))
					minutes = sum(float(n) for n in re.findall(r"(\d+(?:\.\d+)?)\s*m", txt))
					seconds = hours * 3600 + minutes * 60
				break
			author = None
			for acol in wl_author_cols:
				if pd.notna(row.get(acol)):
					author = row.get(acol)
					break
			if seconds is not None:
				rows.append({"date": d, "issue": key, "author": author, "seconds": seconds})
	if rows:
		wldf = pd.DataFrame(rows)
		wldf["hours"] = wldf["seconds"] / 3600.0
		return wldf
	return pd.DataFrame(columns=["date", "issue", "author", "seconds", "hours"])


def collect_burndown_series(snapshot_dir: str, sprint_start: Optional[date], sprint_end: Optional[date]) -> pd.DataFrame:
	snaps = sorted([f for f in os.listdir(snapshot_dir) if f.startswith("snapshot_") and f.endswith(".csv")]) if os.path.isdir(snapshot_dir) else []
	if not snaps:
		return pd.DataFrame(columns=["date", "remaining_sp"])
	rows = []
	for f in snaps:
		snap_date = f[len("snapshot_") : -len(".csv")]
		path = os.path.join(snapshot_dir, f)
		df = pd.read_csv(path)
		status_col = anycol(df, ["status"])
		sp_col = anycol(df, ["story_points"])
		if status_col is None or sp_col is None:
			continue
		# treat these as done
		done_like = df[status_col].astype(str).str.lower().isin(["done", "closed", "verifiable", "verified", "accepted", "released"])
		remaining = df.loc[~done_like, sp_col].fillna(0).sum()
		rows.append({"date": snap_date, "remaining_sp": remaining})
	bdf = pd.DataFrame(rows)
	if not bdf.empty:
		bdf["date"] = pd.to_datetime(bdf["date"]).dt.date
		if sprint_start and sprint_end:
			bdf = bdf[(bdf["date"] >= sprint_start) & (bdf["date"] <= sprint_end)]
		bdf = bdf.sort_values("date")
	return bdf


def plot_burndown(bdf: pd.DataFrame, sprint_start: Optional[date], sprint_end: Optional[date], out_png: str) -> Optional[str]:
	if bdf.empty or sprint_start is None or sprint_end is None:
		return None
	first_day = bdf["date"].min()
	days = (sprint_end - sprint_start).days + 1
	ideal_start = bdf.loc[bdf["date"] == first_day, "remaining_sp"].iloc[0]
	ideal = pd.DataFrame({
		"date": [sprint_start + timedelta(days=i) for i in range(days)],
		"ideal": np.linspace(ideal_start, 0, days)
	})
	merged = ideal.merge(bdf, on="date", how="left")
	plt.figure(figsize=(8, 4.5))
	plt.plot(merged["date"], merged["ideal"], label="Ideal")
	plt.plot(merged["date"], merged["remaining_sp"], marker="o", label="Remaining")
	plt.xticks(rotation=45, ha="right")
	plt.title("Sprint Burndown")
	plt.xlabel("Date")
	plt.ylabel("Story Points")
	plt.legend()
	plt.tight_layout()
	plt.savefig(out_png, dpi=200)
	plt.close()
	return out_png


# -----------------------------
# CLI
# -----------------------------

def run_processor(raw_csv: str, data_dir: str, today: date, sprint_start_arg: Optional[str], sprint_end_arg: Optional[str]) -> None:
	if not os.path.isabs(data_dir):
		data_dir = os.path.abspath(data_dir)
	snap_dir = os.path.join(data_dir, SNAP_SUBDIR)
	report_dir = os.path.join(data_dir, REPORT_SUBDIR)
	os.makedirs(snap_dir, exist_ok=True)
	os.makedirs(report_dir, exist_ok=True)

	full_df = pd.read_csv(raw_csv)
	core = normalize(full_df)
	# Determine sprint window
	if sprint_start_arg and sprint_end_arg:
		sprint_start = datetime.fromisoformat(sprint_start_arg).date()
		sprint_end = datetime.fromisoformat(sprint_end_arg).date()
		sprint_text = None
	else:
		default_year = today.year
		sprint_start, sprint_end, sprint_text = parse_sprint_window(full_df, default_year)

	# Save current snapshot
	snap_path, meta_path = save_snapshot(snap_dir, core, sprint_text or "", sprint_start, sprint_end, today)

	# Previous snapshot (exclude today)
	prev_path = prev_snapshot_path(snap_dir, exclude=today.isoformat())
	prev_df = pd.read_csv(prev_path) if prev_path else None
	events_df = pd.DataFrame(columns=["date", "issue", "field", "old", "new", "details"])
	if prev_df is not None:
		prev_norm = normalize(prev_df)
		events_df = compute_deltas(prev_norm, core, today.isoformat())

	# Worklogs
	worklogs_df = parse_worklogs(full_df, sprint_start, sprint_end)

	# Save reports
	stamp = today.isoformat()
	core_csv = os.path.join(report_dir, f"snapshot_{stamp}.csv")
	events_csv = os.path.join(report_dir, f"daily_events_{stamp}.csv")
	worklogs_csv = os.path.join(report_dir, f"worklogs_{stamp}.csv")
	core.to_csv(core_csv, index=False)
	events_df.to_csv(events_csv, index=False)
	worklogs_df.to_csv(worklogs_csv, index=False)
	# Daily worklog summary within sprint window
	worklogs_daily_csv = os.path.join(report_dir, f"worklogs_daily_{stamp}.csv")
	if not worklogs_df.empty:
		wls = worklogs_df.copy()
		wls["date"] = pd.to_datetime(wls["date"]).dt.date
		daily = wls.groupby("date", as_index=False).agg(total_seconds=("seconds", "sum"), total_hours=("hours", "sum"), entries=("issue", "count"))
		daily = daily.sort_values("date")
		daily.to_csv(worklogs_daily_csv, index=False)
	else:
		pd.DataFrame(columns=["date", "total_seconds", "total_hours", "entries"]).to_csv(worklogs_daily_csv, index=False)

	# Burndown
	bdf = collect_burndown_series(snap_dir, sprint_start, sprint_end)
	burndown_png = os.path.join(report_dir, f"burndown_{stamp}.png")
	burndown_plot = plot_burndown(bdf, sprint_start, sprint_end, burndown_png)
	# Save burndown dataset
	burndown_csv = os.path.join(report_dir, f"burndown_{stamp}.csv")
	if not bdf.empty:
		bdf.to_csv(burndown_csv, index=False)
	else:
		pd.DataFrame(columns=["date", "remaining_sp"]).to_csv(burndown_csv, index=False)

	print("Sprint text:", sprint_text)
	print("Sprint start:", sprint_start, "Sprint end:", sprint_end)
	print("Saved snapshot:", snap_path)
	print("Reports:")
	print(" - Snapshot CSV:", core_csv)
	print(" - Events CSV:", events_csv)
	print(" - Worklogs CSV:", worklogs_csv)
	print(" - Worklogs daily CSV:", worklogs_daily_csv)
	if burndown_plot:
		print(" - Burndown chart:", burndown_plot)
	else:
		print(" - Burndown chart: not generated (insufficient data)")
	print(" - Burndown dataset:", burndown_csv)


def parse_args(argv: list[str]) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Sprint-feldolgozó JIRA CSV exporthoz (snapshotok, diff, worklog, burndown).")
	parser.add_argument("--csv", required=True, help="Abszolút (vagy relatív) útvonal a JIRA CSV fájlhoz")
	parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR, help=f"Adatkönyvtár (alapértelmezés: {DEFAULT_DATA_DIR})")
	parser.add_argument("--today", default=date.today().isoformat(), help="Dátum felülbírálása YYYY-MM-DD formátumban")
	parser.add_argument("--sprint-start", dest="sprint_start", default=None, help="Sprint kezdete YYYY-MM-DD")
	parser.add_argument("--sprint-end", dest="sprint_end", default=None, help="Sprint vége YYYY-MM-DD")
	return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
	args = parse_args(argv or sys.argv[1:])
	try:
		today = datetime.fromisoformat(args.today).date()
	except Exception:
		print("Hibás --today dátum formátum, várható: YYYY-MM-DD", file=sys.stderr)
		return 2
	if not os.path.exists(args.csv):
		print(f"CSV nem található: {args.csv}", file=sys.stderr)
		return 2
	run_processor(args.csv, args.data_dir, today, args.sprint_start, args.sprint_end)
	return 0


if __name__ == "__main__":
	sys.exit(main())