#!/usr/bin/env python3
"""Run one official WMS scenario with a strict result gate and a hard timeout.

This script is opt-in only: it contacts an external public map service.
A skipped/invalid source must never be interpreted as a successful live test.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "tests" / "integration" / "config.json"
DEFAULT_REPORT_DIR = REPO_ROOT / "artifacts" / "live_ogc"


def load_scenario(config: dict, name: str, max_pixels: int) -> dict:
    """Validate the chosen existing scenario before starting QGIS or the network."""
    matches = [s for s in config.get("scenarios", []) if s.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one configured scenario: {name}")
    scenario = matches[0]
    sources = {s["name"]: s for s in config.get("sources", [])}
    source = sources.get(scenario.get("source"))
    if source is None:
        raise ValueError(f"Unknown source for scenario {name}")
    provider = scenario.get("provider") or source.get("provider", "wms")
    if provider != "wms":
        raise ValueError(f"Live smoke requires a WMS provider: {name}")
    uri = scenario.get("uri") or source.get("uri", "")
    if "url=https://" not in uri:
        raise ValueError(f"Live smoke requires an HTTPS WMS URL: {name}")

    defaults = config.get("defaults", {})
    extent = scenario.get("extent") or source.get("extent") or defaults.get("extent")
    gsd = float(scenario.get("gsd", source.get("gsd", defaults.get("gsd", 0))))
    if not extent or gsd <= 0:
        raise ValueError(f"Missing extent or ground resolution: {name}")
    width = max(1, round((float(extent["east"]) - float(extent["west"])) / gsd))
    height = max(1, round((float(extent["north"]) - float(extent["south"])) / gsd))
    if width <= 0 or height <= 0 or width * height > max_pixels:
        raise ValueError(f"Requested {width} x {height} pixels exceeds limit {max_pixels}")
    if scenario.get("create_vrt", source.get("create_vrt", False)):
        raise ValueError(f"Use a direct raster scenario for live smoke: {name}")
    return {
        "name": name,
        "width_px": width,
        "height_px": height,
        "provider": provider,
        "reference_sha256": scenario.get("expected_sha256"),
    }


def check_live_report(rows: object, scenario: str) -> str:
    """Return the SHA-256 only if one real export succeeded; fail closed."""
    if not isinstance(rows, list) or len(rows) != 1:
        raise ValueError(f"{scenario}: expected one report entry, got {rows!r}")
    row = rows[0]
    if not isinstance(row, dict) or row.get("name") != scenario:
        raise ValueError(f"{scenario}: report entry does not match requested scenario")
    if row.get("result") != "ok":
        raise ValueError(f"{scenario}: report status is {row.get('result')!r}")
    digest = row.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError(f"{scenario}: missing valid SHA-256 in report")
    if not all(ch in "0123456789abcdef" for ch in digest.lower()):
        raise ValueError(f"{scenario}: invalid SHA-256 characters")
    if int(row.get("width_px", 0)) <= 0 or int(row.get("height_px", 0)) <= 0:
        raise ValueError(f"{scenario}: invalid raster dimensions in report")
    return digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-pixels", type=int, default=2_000_000)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    if args.timeout <= 0 or args.max_pixels <= 0:
        parser.error("timeout and max-pixels must be positive")

    report_dir = args.report_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {"scenario": args.scenario, "result": "error"}
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        summary.update(load_scenario(config, args.scenario, args.max_pixels))
        env = os.environ.copy()
        env.update(
            ALLOW_INTEGRATION_NETWORK="1",
            CMD_REQUIRE_QGIS="1",
            SCENARIOS=args.scenario,
            CMD_INTEGRATION_REPORT_DIR=str(report_dir),
        )
        # Launch only the non-scale WMS test. Scale and catalog baselines
        # remain a separate release gate, not part of this bounded smoke.
        command = [
            sys.executable,
            "-m",
            "unittest",
            "-v",
            "tests.integration.test_export_network.QgisNetworkIntegrationTest.test_network_scenarios",
        ]
        proc = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
        (report_dir / "stdout.log").write_text(proc.stdout, encoding="utf-8")
        (report_dir / "stderr.log").write_text(proc.stderr, encoding="utf-8")
        summary["exit_code"] = proc.returncode
        if proc.returncode != 0:
            raise RuntimeError(f"QGIS network test failed with exit code {proc.returncode}")
        report_path = report_dir / "network_scenarios.json"
        if not report_path.exists():
            raise ValueError("QGIS did not produce the expected network report")
        summary["sha256"] = check_live_report(
            json.loads(report_path.read_text(encoding="utf-8")), args.scenario
        )
        reference = summary.get("reference_sha256")
        if not reference:
            summary["baseline_status"] = "untracked"
        elif summary["sha256"] == reference:
            summary["baseline_status"] = "match"
        else:
            summary["baseline_status"] = "drift"
        summary["release_gate"] = (
            "pass" if summary["baseline_status"] == "match" else "review_required"
        )
        summary["result"] = "ok"
        print(f"LIVE WMS EXPORT PASS: {args.scenario}, sha256={summary['sha256']}")
        print(f"REFERENCE STATUS: {summary['baseline_status']}")
        if summary["release_gate"] != "pass":
            print(
                "RELEASE REVIEW REQUIRED: reference hash does not match or is absent",
                file=sys.stderr,
            )
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        summary["error"] = str(exc)
        print(f"LIVE WMS FAIL: {args.scenario}: {exc}", file=sys.stderr)
        return 1
    finally:
        (report_dir / "live_smoke_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    raise SystemExit(main())
