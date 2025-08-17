#!/usr/bin/env python3

import os
import sys
from datetime import date
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import pandas as pd

# Ensure project root is on sys.path to import tools
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
	sys.path.insert(0, PROJECT_ROOT)

from tools.jira_sprint_processor import run_processor, parse_sprint_window

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret")

DATA_DIR = os.path.abspath(os.path.join(".", "data", "jira_sprint_processor"))
SNAP_DIR = os.path.join(DATA_DIR, "snapshots_csv")
REPORT_DIR = os.path.join(DATA_DIR, "reports")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

os.makedirs(SNAP_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


def latest_report_paths(stamp: Optional[str] = None) -> dict:
	if not stamp:
		stamp = date.today().isoformat()
	paths = {
		"snapshot": os.path.join(REPORT_DIR, f"snapshot_{stamp}.csv"),
		"events": os.path.join(REPORT_DIR, f"daily_events_{stamp}.csv"),
		"worklogs": os.path.join(REPORT_DIR, f"worklogs_{stamp}.csv"),
		"worklogs_daily": os.path.join(REPORT_DIR, f"worklogs_daily_{stamp}.csv"),
		"burndown_png": os.path.join(REPORT_DIR, f"burndown_{stamp}.png"),
		"burndown_csv": os.path.join(REPORT_DIR, f"burndown_{stamp}.csv"),
	}
	return paths


def exists(path: str) -> bool:
	return os.path.exists(path)


@app.route("/")
def index():
	stamp = date.today().isoformat()
	paths = latest_report_paths(stamp)
	context = {
		"stamp": stamp,
		"has_reports": any(exists(p) for p in paths.values()),
	}
	return render_template("index.html", **context)


@app.route("/upload", methods=["POST"])
def upload():
	f = request.files.get("csv")
	if not f or not f.filename.lower().endswith(".csv"):
		flash("Kérlek válassz egy CSV fájlt.")
		return redirect(url_for("index"))
	stamp = date.today().isoformat()
	upload_path = os.path.join(UPLOAD_DIR, f"upload_{stamp}.csv")
	f.save(upload_path)
	# Try to parse sprint window for display
	sprint_text = None
	sprint_start = None
	sprint_end = None
	try:
		df = pd.read_csv(upload_path)
		sprint_start, sprint_end, sprint_text = parse_sprint_window(df, default_year=date.today().year)
	except Exception:
		pass
	# Run processor
	run_processor(upload_path, DATA_DIR, date.today(), None, None)
	paths = latest_report_paths(stamp)
	return render_template("index.html", stamp=stamp, has_reports=True, sprint_text=sprint_text, sprint_start=sprint_start, sprint_end=sprint_end, paths=paths)


@app.route("/files/<path:subpath>")
def files(subpath: str):
	return send_from_directory(DATA_DIR, subpath, as_attachment=False)


@app.template_filter("relpath")
def relpath_filter(full_path: str) -> str:
	# Return path relative to DATA_DIR for the /files route
	try:
		return os.path.relpath(full_path, DATA_DIR)
	except Exception:
		return full_path


if __name__ == "__main__":
	port = int(os.environ.get("PORT", "5000"))
	app.run(host="0.0.0.0", port=port, debug=True)