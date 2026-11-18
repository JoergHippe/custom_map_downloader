#!/usr/bin/env python3
"""Bounded opt-in execution of the official WMS scale matrix using real QGIS."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from scripts.summarize_scale_matrix import compare_against_expected, expected_hashes_by_case

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "tests" / "integration" / "config.json"


def validate_matrix(config: dict, matrix_key: str, max_pixels: int) -> list[dict]:
    """Validate complete test matrix and bound output dimensions before network I/O."""
    cases = config.get(matrix_key, [])
    if not isinstance(cases, list) or not cases or max_pixels <= 0:
        raise ValueError("Invalid or empty scale matrix / pixel limit")
    checked = []
    seen: set[str] = set()
    for case in cases:
        name = case.get("name", "")
        if not name or name in seen:
            raise ValueError("Duplicate or missing matrix case name")
        seen.add(name)
        extent = case["extent"]
        width = float(extent["east"]) - float(extent["west"])
        height = float(extent["north"]) - float(extent["south"])
        if width <= 0 or height <= 0:
            raise ValueError(f"{name}: invalid extent")
        dimensions = {}
        for label in ("small", "large"):
            scale = float(case[f"{label}_scale"])
            if scale <= 0:
                raise ValueError(f"{name}: invalid {label} scale")
            gsd = scale * 0.00028
            pixels = (max(1, round(width / gsd)), max(1, round(height / gsd)))
            if pixels[0] * pixels[1] > max_pixels:
                raise ValueError(f"{name} [{label}]: too many pixels {pixels}")
            dimensions[label] = pixels
        if dimensions["small"] == dimensions["large"]:
            raise ValueError(f"{name}: both scales produce the same dimensions")
        checked.append({"name": name, "dimensions": dimensions})
    return checked


def check_case_report(case: dict, payload: object) -> dict:
    """Fail closed on missing, malformed or incorrectly sized scale exports."""
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError(f"{case['name']}: expected exactly one result group")
    group = payload[0]
    if not isinstance(group, dict) or group.get("name") != case["name"]:
        raise ValueError(f"{case['name']}: wrong report case")
    rows = group.get("results")
    if not isinstance(rows, list) or len(rows) != 2:
        raise ValueError(f"{case['name']}: expected two scale results")
    labels = {}
    for item in rows:
        label = item.get("label")
        if label not in ("small", "large") or label in labels:
            raise ValueError(f"{case['name']}: invalid/duplicate scale label")
        if (item.get("width_px"), item.get("height_px")) != case["dimensions"][label]:
            raise ValueError(f"{case['name']} [{label}]: raster dimensions incorrect")
        digest = item.get("sha256")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest.lower())
        ):
            raise ValueError(f"{case['name']} [{label}]: invalid SHA-256")
        labels[label] = item
    if set(labels) != {"small", "large"} or labels["small"]["sha256"] == labels["large"]["sha256"]:
        raise ValueError(f"{case['name']}: scale results are incomplete or identical")
    return {"case": case["name"], "exit_code": 0, "labels": labels}


def run_matrix(matrix_key: str, report_dir: Path, timeout: int, max_pixels: int) -> int:
    """Run each scenario in its own QGIS process to isolate service failures."""
    report_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {"matrix_key": matrix_key, "result": "error", "cases": []}
    try:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        cases = validate_matrix(
            json.loads(CONFIG.read_text(encoding="utf-8")), matrix_key, max_pixels
        )
        results = {}
        for case in cases:
            name = case["name"]
            folder = report_dir / name
            folder.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env.update(
                ALLOW_INTEGRATION_NETWORK="1",
                CMD_REQUIRE_QGIS="1",
                CMD_INTEGRATION_REPORT_DIR=str(folder),
                SCENARIOS=name,
                CMD_SCALE_MATRIX_KEY=matrix_key,
            )
            cmd = [
                sys.executable,
                "-m",
                "unittest",
                "-v",
                "tests.integration.test_export_network.QgisNetworkIntegrationTest.test_scale_dependent_scenarios",
            ]
            try:
                proc = subprocess.run(
                    cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(f"{name}: timeout after {timeout}s") from exc
            (folder / "stdout.log").write_text(proc.stdout, encoding="utf-8")
            (folder / "stderr.log").write_text(proc.stderr, encoding="utf-8")
            if proc.returncode != 0:
                raise RuntimeError(f"{name}: QGIS scale process failed with {proc.returncode}")
            path = folder / "scale_matrix.json"
            if not path.exists():
                raise ValueError(f"{name}: missing scale_matrix.json")
            result = check_case_report(case, json.loads(path.read_text(encoding="utf-8")))
            results[name] = result
            summary["cases"].append({"name": name, "result": "ok"})
            for label, item in result["labels"].items():
                print(
                    f"SCALE PASS: {name} {label} {item['width_px']}x{item['height_px']}"
                    f" sha256={item['sha256']} reference={item.get('baseline_status', 'untracked')}",
                    flush=True,
                )
        rows = compare_against_expected(results, expected_hashes_by_case(matrix_key))
        if len(rows) != len(cases) * 2 or any(
            row["status"] in {"missing", "error"} for row in rows
        ):
            raise ValueError("Some required scale results are missing or invalid")
        summary["rows"] = rows
        summary["result"] = "ok"
        (report_dir / "scale_matrix_report.json").write_text(
            json.dumps({"matrix_key": matrix_key, "rows": rows}, indent=2), encoding="utf-8"
        )
        print(f"SCALE MATRIX PASS: {len(cases)} cases, {len(rows)} exports")
        return 0
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        summary["error"] = str(exc)
        print(f"SCALE MATRIX FAIL: {exc}", file=sys.stderr)
        return 1
    finally:
        (report_dir / "live_scale_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-key", default="scale_matrix")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--max-pixels", type=int, default=8_000_000)
    parser.add_argument("--report-dir", type=Path, default=ROOT / "artifacts" / "live_scale")
    args = parser.parse_args()
    return run_matrix(args.matrix_key, args.report_dir.resolve(), args.timeout, args.max_pixels)


if __name__ == "__main__":
    raise SystemExit(main())
