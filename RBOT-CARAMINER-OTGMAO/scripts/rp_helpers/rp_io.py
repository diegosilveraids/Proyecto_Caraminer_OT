# -*- coding: utf-8 -*-
import ast
import json
import os
import re
import sys

from rp_helpers.rp_patterns import RE_NON_ASCII


def configure_output_encoding():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _get_cli_arg(index):
    try:
        return sys.argv[index]
    except IndexError:
        return None


def _parse_report_read_text(report_read_raw):
    report_read_raw = report_read_raw.encode("utf-8", "ignore").decode("utf-8")

    try:
        report_read = ast.literal_eval(report_read_raw)
    except Exception:
        try:
            report_read = json.loads(report_read_raw)
        except Exception:
            try:
                report_read_raw = RE_NON_ASCII.sub(" ", report_read_raw)
                report_read = ast.literal_eval(report_read_raw)
            except Exception as exc:
                raise RuntimeError(f"PARSE_ERROR: failed to parse report_read: {exc}") from exc

    if not isinstance(report_read, list):
        raise RuntimeError("PARSE_ERROR: report_read must be a list")

    return report_read


def load_report_read():
    report_path = _get_cli_arg(2)

    if report_path is None:
        raise RuntimeError("BOOTSTRAP_ERROR: missing report_path from argv[2]")

    if not isinstance(report_path, str):
        report_path = str(report_path)

    report_path = report_path.strip()
    if not report_path:
        raise RuntimeError("BOOTSTRAP_ERROR: empty report_path from argv[2]")

    if not os.path.isfile(report_path):
        raise RuntimeError(f"BOOTSTRAP_ERROR: report_path does not exist or is not a file: {report_path}")

    with open(report_path, "r", encoding="utf-8") as report_file:
        report_read_raw = report_file.read().strip()

    if not report_read_raw:
        raise RuntimeError("PARSE_ERROR: report_read file is empty")

    return _parse_report_read_text(report_read_raw)


def get_project_path():
    project_path = _get_cli_arg(1)

    if isinstance(project_path, str):
        project_path = project_path.strip()
        if project_path:
            return os.fspath(project_path)

    get_var = globals().get("GetVar")
    if callable(get_var):
        try:
            project_path = get_var("PROJECT_PATH")
            if isinstance(project_path, str):
                project_path = project_path.strip()
                if project_path:
                    return os.fspath(project_path)
        except Exception:
            pass

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write_output_file(work_order_dictionary, report_name):
    project_path = get_project_path()
    safe_report_name = re.sub(r"[<>:\"/\\|?*]", "_", report_name or "report")
    parsed_dir = os.path.join(project_path, "parsed")
    output_file_path = os.path.join(parsed_dir, f"{safe_report_name}.json")

    os.makedirs(parsed_dir, exist_ok=True)
    with open(output_file_path, "w", encoding="utf-8") as output_file:
        json.dump(work_order_dictionary, output_file, ensure_ascii=False, indent=4)

    return output_file_path.replace("\\", "/")

