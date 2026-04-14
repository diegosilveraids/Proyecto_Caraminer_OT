# -*- coding: utf-8 -*-
import re
import json
import ast
import sys

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

# ---------------------------------
# Fix Windows / Rocketbot encoding
# ---------------------------------
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ---------------------------------
# Retrieve and sanitize data
# ---------------------------------
try:
    report_read_raw = GetVar("report_read")
except Exception as exc:
    raise RuntimeError("BOOTSTRAP_ERROR: failed to read Rocketbot variable 'report_read'") from exc

try:
    if isinstance(report_read_raw, str):
        report_read_raw = report_read_raw.encode("utf-8", "ignore").decode("utf-8")

    report_read = ast.literal_eval(report_read_raw)
except Exception:
    try:
        report_read_raw = RE_NON_ASCII.sub(" ", GetVar("report_read"))
        report_read = ast.literal_eval(report_read_raw)
    except Exception as exc:
        raise RuntimeError("PARSE_ERROR: failed to parse 'report_read' content") from exc

# ---------------------------------
# Function definitions
# ---------------------------------
def extract(txt, patron, re_spaces=RE_SPACES):
    m = re.search(patron, txt, re.I | re.S)
    return re_spaces.sub(" ", m.group(1)).strip() if m else None

def extract_schedule(txt, re_schedule=RE_SCHEDULE):
    txt = (
        txt
        .replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\u00a0", " ")
    )

    schedule = []

    for begin, end in re_schedule.findall(txt):
        schedule.append({
            "begin": begin.strip(),
            "end": end.strip()
        })

    return schedule

def validate_task(task):
    errors = []

    if not task.get("area"):
        errors.append("Missing area")

    if not task.get("n_task"):
        errors.append("Missing n_task")

    if not task.get("gamas"):
        errors.append("Missing gamas")

    if not task.get("begin_date"):
        errors.append("Missing begin_date")

    if not task.get("end_date"):
        errors.append("Missing end_date")

    schedules = task.get("schedules", [])

    if not schedules:
        errors.append("Missing schedules")
    else:
        if schedules[0]["begin"] > schedules[-1]["end"]:
            errors.append("Inconsistent schedule")

    if task.get("begin_date") and task.get("end_date"):
        if task["begin_date"] > task["end_date"]:
            errors.append("begin_date > end_date")

    if errors:
        return "ERROR", " | ".join(errors)

    return "CORRECT", ""

try:
    ensure_structure(isinstance(report_read, list), "STRUCTURE_ERROR: parsed report must be a list")
    ensure_structure(len(report_read) > 0, "STRUCTURE_ERROR: parsed report is empty")

    # ---------------------------------
    # Extract metadata from first page
    # ---------------------------------
    page_0 = next((p["text"] for p in report_read if p.get("page") == 1), "")

    metadata = {
        "report_name": extract(page_0, RX_REPORT_NAME),
        "state": extract(page_0, RX_REPORT_STATE),
        "date": extract(page_0, RX_REPORT_DATE),
        "week": extract(page_0, RX_REPORT_WEEK)
    }

    # ---------------------------------
    # Report full text (excluding first
    # page and repeated pattern)
    # ---------------------------------
    text = "\n".join(p["text"] for p in report_read if p.get("page") != 1)
    ensure_structure(text.strip() != "", "STRUCTURE_ERROR: report has no body text after page 1")

    text = re.sub(
        RX_REPEATED_HEADER,
        '',
        text,
        flags=re.I | re.S
    )

    # ---------------------------------
    # Titles per day
    # ---------------------------------
    titles = list(RE_TITLE_BY_DAY.finditer(text))
    ensure_structure(len(titles) > 0, "STRUCTURE_ERROR: no day-title sections were found")

    tasks_dictionary = {}
    total_candidate_task_blocks = 0
    valid_tasks_count = 0
    invalid_tasks_count = 0

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

        # ---------------------------------
        # Tasks
        # ---------------------------------
        tasks_raw = RE_TASK_SPLIT.split(block)
        tasks = []

        for t in tasks_raw:
            if not RE_TASK_HAS_ID.search(t):
                continue

            total_candidate_task_blocks += 1

            # ---------------------------------
            # Details per task
            # ---------------------------------
            task = {
                "area": extract(t, RX_FIELD_AREA),
                "n_task": extract(t, RX_FIELD_TASK_NUMBER),
                "occupation_zone": extract(t, RX_FIELD_OCCUPATION_ZONE),
                "description": extract(t, RX_FIELD_DESCRIPTION),
                "work_system": extract(t, RX_FIELD_WORK_SYSTEM),
                "pk": extract(t, RX_FIELD_PK),
                "begin_date": extract(t, RX_FIELD_BEGIN_DATE),
                "end_date": extract(t, RX_FIELD_END_DATE),
                "schedules": extract_schedule(t),
                "week_days": extract(t, RX_FIELD_WEEK_DAYS),
                "responsible": extract(t, RX_FIELD_RESPONSIBLE),
                "machinery": extract(t, RX_FIELD_MACHINERY),
                "assets": extract(t, RX_FIELD_ASSETS),
                "considerations": extract(t, RX_FIELD_CONSIDERATIONS),
                "procedure": extract(t, RX_FIELD_PROCEDURE),
                "gamas": extract(t, RX_FIELD_GAMAS)
            }

            task["assets"] = [a.strip() for a in (task["assets"] or "").split("/") if a.strip()]
            task["gamas"] = [g.strip() for g in (task["gamas"] or "").split("/") if g.strip()]

            state, error_description = validate_task(task)
            task["state"] = state
            task["error_description"] = error_description

            if state == "CORRECT":
                valid_tasks_count += 1
            else:
                invalid_tasks_count += 1

            tasks.append(task)

        tasks_dictionary.setdefault(day, {}).setdefault(subtitle, []).extend(tasks)

    ensure_structure(
        total_candidate_task_blocks > 0,
        "STRUCTURE_ERROR: no task blocks matched expected '\u00C1rea / N\u00B0 Tarea' markers"
    )

    # ---------------------------------
    # Task and OT counting
    # ---------------------------------
    unique_tasks = set()
    unique_work_orders = 0

    for day in tasks_dictionary.values():
        for system in day.values():
            for task in system:
                if task.get("n_task"):
                    unique_tasks.add(task["n_task"])

                n_assets = len(task["assets"]) or 1
                n_gamas = len(task["gamas"]) or 1

                unique_work_orders += n_assets * n_gamas

    # ---------------------------------
    # Final json
    # ---------------------------------
    work_order_dictionary = {
        "metadata": {
            **metadata,
            "tasks_count": len(unique_tasks),
            "work_orders_count": unique_work_orders,
            "valid_tasks_count": valid_tasks_count,
            "invalid_tasks_count": invalid_tasks_count
        },
        "tasks": tasks_dictionary
    }

    SetVar("work_order_dictionary", json.dumps(work_order_dictionary, ensure_ascii=False))
except ReportStructureError as exc:
    raise RuntimeError(f"STRUCTURE_PHASE_ERROR: {exc}") from exc
except Exception as exc:
    raise RuntimeError(f"RUNTIME_PHASE_ERROR: {exc}") from exc