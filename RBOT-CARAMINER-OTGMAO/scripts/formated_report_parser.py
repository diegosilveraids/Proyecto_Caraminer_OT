# -*- coding: utf-8 -*-
import re
import json
import ast
import sys
import os
import unicodedata

# ---------------------------------
# Regex constants
# ---------------------------------
RX_SPACES = r"\s+"
RX_NON_ASCII = r"[^\x00-\x7F]+"

RX_REPORT_NAME = r'(FO\s*O-PLA-[0-9A-Z\-]+)'
RX_REPORT_STATE = r'\b(APROBAD[OA])\b'
RX_REPORT_DATE = r'\n\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\s*\n'
RX_REPORT_WEEK = r'SEMANA\s*([0-9]{1,2})'

RX_REPEATED_HEADER = r'SISTEMA\s+INTEGRADO\s+DE\s+GESTI\u00D3N.*?Hoja\s+\d+\s+de\s+\d+'
RX_TITLE_BY_DAY = r'^\s*(LUNES|MARTES|MIERCOLES|MI\u00C9RCOLES|JUEVES|VIERNES|SABADO|S\u00C1BADO|DOMINGO)\b.*?(?=\n\s*\u00C1rea:)'
RX_DAY_AND_SUBTITLE = r'^\s*(LUNES|MARTES|MIERCOLES|MI\u00C9RCOLES|JUEVES|VIERNES|SABADO|S\u00C1BADO|DOMINGO)\b\s*(.*)'

RX_TASK_SPLIT = r'(?=^\s*\u00C1rea:\s*.*?N\u00B0\s*Tarea:)'
RX_TASK_HAS_ID = r'N\u00B0\s*Tarea:'

RX_FIELD_AREA = r'\u00C1rea:\s*(.*?)\s*N\u00B0\s*Tarea'
RX_FIELD_TASK_NUMBER = r'N\u00B0\s*Tarea:\s*([0-9/]+)'
RX_FIELD_OCCUPATION_ZONE = r'Zona\s*de\s*Ocupaci\u00F3n:\s*(.*?)\s*Descripci\u00F3n'
RX_FIELD_DESCRIPTION = r'Descripci\u00F3n:\s*(.*?)\s*Sistema\s*de\s*Trabajo'
RX_FIELD_WORK_SYSTEM = r'Sistema\s*de\s*Trabajo:\s*(.*?)\s*PK:'
RX_FIELD_PK = r'PK:\s*(.*?)\s*Fecha\s*de\s*Inicio'
RX_FIELD_BEGIN_DATE = r'Fecha\s*de\s*Inicio:\s*([0-9\-]+)'
RX_FIELD_END_DATE = r'Fecha\s*de\s*Fin:\s*([0-9\-]+)'
RX_FIELD_WEEK_DAYS = r'D\u00EDas\s*de\s*la\s*semana:\s*([A-Z, ]+)'
RX_FIELD_RESPONSIBLE = r'Responsable\s*de\s*la\s*tarea\s*:\s*(.*?)\s*Maquinaria:'
RX_FIELD_MACHINERY = r'Maquinaria:\s*(.*?)\s*Activos'
RX_FIELD_ASSETS = r'Activos:\s*(.*?)\s*Consideraciones'
RX_FIELD_CONSIDERATIONS = r'Consideraciones:\s*(.*?)\s*Procedimiento'
RX_FIELD_PROCEDURE = r'Procedimiento:\s*(.*?)\s*Gamas'
RX_FIELD_GAMAS = r'Gamas:\s*(.*?)(?:\n|$)'

RX_SCHEDULE = (
    r'Hora\s*inicio:\s*([0-9]{1,2}:[0-9]{2})\s*'
    r'Hora\s*final:\s*([0-9]{1,2}:[0-9]{2})'
)

# ---------------------------------
# Precompiled regex patterns
# ---------------------------------
RE_SPACES = re.compile(RX_SPACES)
RE_NON_ASCII = re.compile(RX_NON_ASCII)
RE_SCHEDULE = re.compile(RX_SCHEDULE, re.I)
RE_TITLE_BY_DAY = re.compile(RX_TITLE_BY_DAY, re.I | re.S | re.M)
RE_DAY_AND_SUBTITLE = re.compile(RX_DAY_AND_SUBTITLE, re.I | re.S)
RE_TASK_SPLIT = re.compile(RX_TASK_SPLIT, re.M)
RE_TASK_HAS_ID = re.compile(RX_TASK_HAS_ID)


class ReportStructureError(Exception):
    pass


def ensure_structure(condition, message):
    if not condition:
        raise ReportStructureError(message)


def configure_output_encoding():
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass




def _get_cli_arg(index):
    """Safely retrieve argv at index, return None if missing/invalid."""
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
    """Load and parse report_read dumped into a file path from argv[2]."""
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
    """Get PROJECT_PATH from argv[1], fallback to GetVar or script-relative path."""
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


def extract(txt, patron, re_spaces=RE_SPACES):
    m = re.search(patron, txt, re.I | re.S)
    return re_spaces.sub(" ", m.group(1)).strip() if m else None


def normalize_text(txt):
    if not txt:
        return ""

    normalized = unicodedata.normalize("NFD", txt)
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_accents.casefold().strip()


def extract_schedule(txt, re_schedule=RE_SCHEDULE):
    txt = (
        txt
        .replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\u00a0", " ")
    )

    matches = re_schedule.findall(txt)

    if matches:
        begin, end = matches[0]
        return {
            "begin": begin.strip(),
            "end": end.strip()
        }

    return {}


def parse_pk(txt):
    if not txt:
        return {
            "initial_pk": "",
            "final_pk": ""
        }

    matches = re.findall(r'\d{3}\+\d{3}', txt)

    return {
        "initial_pk": matches[0] if len(matches) > 0 else "",
        "final_pk": matches[1] if len(matches) > 1 else ""
    }


def parse_assets(raw_assets):
    re_asset_code = re.compile(r"\b[A-Za-z]{1,4}\s*\d{1,4}\b")

    if raw_assets is None:
        return [], None

    raw = raw_assets.strip()
    if not raw:
        return [], None

    # Keep original asset token format; validate only division quality.
    if raw.startswith("/") or raw.endswith("/") or re.search(r"/\s*/", raw):
        return [], "Invalid assets division"

    assets = [a.strip() for a in raw.split("/")]
    if any(not asset for asset in assets):
        return [], "Invalid assets division"

    # If one token contains multiple asset-like codes, separators are likely wrong.
    if any(len(re_asset_code.findall(asset)) > 1 for asset in assets):
        return [], "Invalid assets division"

    return assets, None


def parse_gamas(raw_gamas):
    if raw_gamas is None:
        return [], None

    raw = raw_gamas.strip()
    if not raw:
        return [], None

    # Keep original gama token format; validate only division quality.
    if raw.startswith("/") or raw.endswith("/") or re.search(r"/\s*/", raw):
        return [], "Invalid gamas division"

    gamas = [g.strip() for g in raw.split("/")]
    if any(not gama for gama in gamas):
        return [], "Invalid gamas division"

    return gamas, None


def validate_task(task, assets_error=None, gamas_error=None):
    import datetime as _dt
    import unicodedata as _ud

    def _normalize_area(value):
        if not value:
            return ""
        normalized = _ud.normalize("NFD", value)
        without_accents = "".join(ch for ch in normalized if _ud.category(ch) != "Mn")
        return without_accents.casefold().strip()

    allowed_areas = {"senalizacion", "area", "infraestructura", "vias"}

    errors = []

    if not task.get("area"):
        errors.append("Missing area")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

    if _normalize_area(task.get("area")) not in allowed_areas:
        errors.append("Invalid area")
        return "ERROR-FORMAT", " | ".join(errors)

    if not task.get("n_task"):
        errors.append("Missing n_task")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

    if assets_error:
        errors.append(assets_error)
        return "ERROR-FORMAT", " | ".join(errors)

    if gamas_error:
        errors.append(gamas_error)
        return "ERROR-FORMAT", " | ".join(errors)

    if not task.get("gamas"):
        errors.append("Missing gamas")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

    # Validate PK format only for tasks without assets.
    if not task.get("assets"):
        pk = task.get("pk") or {}
        pk_initial = (pk.get("initial_pk") or "").strip()
        pk_final = (pk.get("final_pk") or "").strip()

        if not re.fullmatch(r"\d{3}\+\d{3}", pk_initial):
            errors.append("Invalid pk format (expected DDD+DDD)")
            return "ERROR-FORMAT", " | ".join(errors)

        if pk_final and not re.fullmatch(r"\d{3}\+\d{3}", pk_final):
            errors.append("Invalid pk format (expected DDD+DDD)")
            return "ERROR-FORMAT", " | ".join(errors)

    if not task.get("begin_date"):
        errors.append("Missing begin_date")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

    if not task.get("end_date"):
        errors.append("Missing end_date")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

    try:
        begin_date_obj = _dt.datetime.strptime(task["begin_date"], "%d-%m-%Y")
    except ValueError:
        errors.append("Invalid begin_date format (expected dd-mm-yyyy)")
        return "ERROR-FORMAT", " | ".join(errors)

    try:
        end_date_obj = _dt.datetime.strptime(task["end_date"], "%d-%m-%Y")
    except ValueError:
        errors.append("Invalid end_date format (expected dd-mm-yyyy)")
        return "ERROR-FORMAT", " | ".join(errors)

    schedule = task.get("schedule", {})

    if not schedule:
        errors.append("Missing schedule")
    else:
        if schedule.get("begin", "") > schedule.get("end", ""):
            errors.append("Inconsistent schedule")
            return "ERROR-FORMAT", " | ".join(errors)

    if begin_date_obj > end_date_obj:
        errors.append("begin_date > end_date")
        return "ERROR-FORMAT", " | ".join(errors)

    if errors:
        return "ERROR-FORMAT", " | ".join(errors)

    return "READ-SUCCESS", ""


def expand_task_by_asset_gamma(task):
    """
    Expands a task into multiple tasks - one for each combination of asset and gamma.
    Each expanded task has only one asset and one gamma.
    Schedule is used from the original task (no longer a list).
    """
    assets = task.get("assets", [])
    gamas = task.get("gamas", [])

    # Ensure at least one item for cartesian product
    if not assets:
        assets = [None]
    if not gamas:
        gamas = [None]

    expanded_tasks = []

    for asset in assets:
        for gamma in gamas:
            new_task = dict(task)
            new_task["asset"] = asset
            new_task["gamma"] = gamma
            del new_task["assets"]
            del new_task["gamas"]
            expanded_tasks.append(new_task)

    return expanded_tasks


def extract_report_metadata(report_read):
    page_0 = next((p["text"] for p in report_read if p.get("page") == 1), "")

    report_name = extract(page_0, RX_REPORT_NAME)
    state = extract(page_0, RX_REPORT_STATE)
    date = extract(page_0, RX_REPORT_DATE)
    year = date[-4:] if date else None
    week = "W" + extract(page_0, RX_REPORT_WEEK)

    metadata = {
        "report_name": report_name,
        "state": state,
        "date": date,
        "year": year,
        "week": week
    }

    return metadata, report_name


def build_report_body_text(report_read):
    text = "\n".join(p["text"] for p in report_read if p.get("page") != 1)
    ensure_structure(text.strip() != "", "STRUCTURE_ERROR: report has no body text after page 1")

    text = re.sub(
        RX_REPEATED_HEADER,
        '',
        text,
        flags=re.I | re.S
    )

    return text


def parse_task_block(task_block_text):
    task = {
        "area": extract(task_block_text, RX_FIELD_AREA),
        "n_task": extract(task_block_text, RX_FIELD_TASK_NUMBER),
        "occupation_zone": extract(task_block_text, RX_FIELD_OCCUPATION_ZONE),
        "description": extract(task_block_text, RX_FIELD_DESCRIPTION),
        "work_system": extract(task_block_text, RX_FIELD_WORK_SYSTEM),
        "pk": parse_pk(extract(task_block_text, RX_FIELD_PK)),
        "begin_date": extract(task_block_text, RX_FIELD_BEGIN_DATE),
        "end_date": extract(task_block_text, RX_FIELD_END_DATE),
        "schedule": extract_schedule(task_block_text),
        "week_days": extract(task_block_text, RX_FIELD_WEEK_DAYS),
        "responsible": extract(task_block_text, RX_FIELD_RESPONSIBLE),
        "machinery": extract(task_block_text, RX_FIELD_MACHINERY),
        "assets": extract(task_block_text, RX_FIELD_ASSETS),
        "considerations": extract(task_block_text, RX_FIELD_CONSIDERATIONS),
        "procedure": extract(task_block_text, RX_FIELD_PROCEDURE),
        "gamas": extract(task_block_text, RX_FIELD_GAMAS),
        "state": None,
        "error_description": None
    }

    parsed_assets, assets_error = parse_assets(task["assets"])
    parsed_gamas, gamas_error = parse_gamas(task["gamas"])
    task["assets"] = parsed_assets
    task["gamas"] = parsed_gamas

    state, error_description = validate_task(task, assets_error, gamas_error)
    task["state"] = state
    task["error_description"] = error_description

    return task


def build_work_orders_dictionary(text):
    titles = list(RE_TITLE_BY_DAY.finditer(text))
    ensure_structure(len(titles) > 0, "STRUCTURE_ERROR: no day-title sections were found")

    wo_dictionary = {}
    total_candidate_task_blocks = 0

    for i, match in enumerate(titles):
        title = match.group().strip()

        m = RE_DAY_AND_SUBTITLE.match(title)
        if not m:
            day = "UNKNOWN"
            subtitle = title
        else:
            day = m.group(1).upper()
            subtitle = RE_SPACES.sub(" ", m.group(2)).strip() or "NO CATEGORY"

        start = match.end()
        end = titles[i + 1].start() if i + 1 < len(titles) else len(text)
        block = text[start:end]

        tasks_raw = RE_TASK_SPLIT.split(block)
        tasks = []

        for raw_task in tasks_raw:
            if not RE_TASK_HAS_ID.search(raw_task):
                continue

            total_candidate_task_blocks += 1

            parsed_task = parse_task_block(raw_task)
            expanded_tasks = expand_task_by_asset_gamma(parsed_task)
            tasks.extend(expanded_tasks)

        wo_dictionary.setdefault(day, {}).setdefault(subtitle, []).extend(tasks)

    ensure_structure(
        total_candidate_task_blocks > 0,
        "STRUCTURE_ERROR: no task blocks matched expected '\u00C1rea / N\u00B0 Tarea' markers"
    )

    return wo_dictionary


def calculate_counts(wo_dictionary):
    unique_tasks = set()
    unique_work_orders = 0
    valid_wo_count = 0
    invalid_wo_count = 0

    for day in wo_dictionary.values():
        for system in day.values():
            for task in system:
                if task.get("n_task"):
                    unique_tasks.add(task["n_task"])

                if task.get("state") == "READ-SUCCESS":
                    valid_wo_count += 1
                else:
                    invalid_wo_count += 1

                unique_work_orders += 1

    return {
        "tasks_count": len(unique_tasks),
        "work_orders_count": unique_work_orders,
        "valid_wo_count": valid_wo_count,
        "invalid_wo_count": invalid_wo_count
    }


def build_output_dictionary(metadata, counts, wo_dictionary):
    return {
        "metadata": {
            **metadata,
            **counts
        },
        "work_orders": wo_dictionary
    }


def write_output_file(work_order_dictionary, report_name):
    project_path = get_project_path()
    safe_report_name = re.sub(r'[<>:"/\\|?*]', "_", report_name or "report")
    parsed_dir = os.path.join(project_path, "parsed")
    output_file_path = os.path.join(parsed_dir, f"{safe_report_name}.json")

    os.makedirs(parsed_dir, exist_ok=True)
    with open(output_file_path, "w", encoding="utf-8") as output_file:
        json.dump(work_order_dictionary, output_file, ensure_ascii=False, indent=4)


def export_work_order_dictionary(work_order_dictionary):
    return json.dumps(work_order_dictionary, ensure_ascii=False)


def main():
    configure_output_encoding()

    report_read = load_report_read()
    ensure_structure(isinstance(report_read, list), "STRUCTURE_ERROR: parsed report must be a list")
    ensure_structure(len(report_read) > 0, "STRUCTURE_ERROR: parsed report is empty")

    metadata, report_name = extract_report_metadata(report_read)
    text = build_report_body_text(report_read)
    wo_dictionary = build_work_orders_dictionary(text)

    counts = calculate_counts(wo_dictionary)
    work_order_dictionary = build_output_dictionary(metadata, counts, wo_dictionary)

    write_output_file(work_order_dictionary, report_name)
    return export_work_order_dictionary(work_order_dictionary)


def run():
    try:
        return main()
    except ReportStructureError as exc:
        raise RuntimeError(f"STRUCTURE_PHASE_ERROR: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"RUNTIME_PHASE_ERROR: {exc}") from exc


if __name__ == "__main__":
    print(run())