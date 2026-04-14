# -*- coding: utf-8 -*-
import re
import json
import ast
import sys

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
#----------------------------------
try:
    report_read_raw = GetVar("report_read")
    if isinstance(report_read_raw, str):
        report_read_raw = report_read_raw.encode("utf-8", "ignore").decode("utf-8")

    report_read = ast.literal_eval(report_read_raw)

except Exception:
    report_read_raw = re.sub(r"[^\x00-\x7F]+", " ", GetVar("report_read"))
    report_read = ast.literal_eval(report_read_raw)

# ---------------------------------
# Function definitions
# ---------------------------------
def extract(txt, patron):
    m = re.search(patron, txt, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None

def extract_schedule(txt):

    # Clean text
    txt = (
        txt
        .replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\u00a0", " ")
    )

    schedule = []

    # Time pattern
    pattern = re.compile(
        r'Hora\s*inicio:\s*([0-9]{1,2}:[0-9]{2})\s*'
        r'Hora\s*final:\s*([0-9]{1,2}:[0-9]{2})',
        re.I
    )

    for begin, end in pattern.findall(txt):
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

    horarios = task.get("schedules", [])

    if not horarios:
        errors.append("Missing schedules")

    else:
        if horarios[0]["begin"] > horarios[-1]["end"]:
            errors.append("Inconsistent schedule")

    if task.get("begin_date") and task.get("end_date"):
        if task["begin_date"] > task["end_date"]:
            errors.append("begin_date > end_date")

    if errors:
        return "ERROR", " | ".join(errors)

    return "CORRECT", ""

# ---------------------------------
# Extract metadata from first page
# ---------------------------------

page_0 = next((p["text"] for p in report_read if p.get("page") == 1), "")

metadata = {
    "report_name": extract(page_0, r'(FO\s*O-PLA-[0-9A-Z\-]+)'),
    "state": extract(page_0, r'\b(APROBAD[OA])\b'),
    "date": extract(page_0, r'\n\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\s*\n'),
    "week": extract(page_0, r'SEMANA\s*([0-9]{1,2})')
}
# ---------------------------------
# Report full text (excluding first
# page and repeated pattern)
# ---------------------------------

text = "\n".join(p["text"] for p in report_read if p.get("page") != 1)

text = re.sub(
    r'SISTEMA\s+INTEGRADO\s+DE\s+GESTI\u00D3N.*?Hoja\s+\d+\s+de\s+\d+',
    '',
    text,
    flags=re.I | re.S
)

# ---------------------------------
# Titles per day
# ---------------------------------
regex_title = re.compile(
    r'^\s*(LUNES|MARTES|MIERCOLES|MI\u00C9RCOLES|JUEVES|VIERNES|SABADO|S\u00C1BADO|DOMINGO)\b.*?(?=\n\s*\u00C1rea:)',
    re.I | re.S | re.M
)

titles = list(regex_title.finditer(text))

tasks_dictionary = {}

for i, match in enumerate(titles):

    title = match.group().strip()

    m = re.match(
        r'^\s*(LUNES|MARTES|MIERCOLES|MI\u00C9RCOLES|JUEVES|VIERNES|SABADO|S\u00C1BADO|DOMINGO)\b\s*(.*)',
        title,
        re.I | re.S
    )

    if not m:
        day = "UNKOWN"
        subtitle = title
    else:
        day = m.group(1).upper()
        subtitle = re.sub(r'\s+', ' ', m.group(2)).strip() or "NO CATEGORY"

    start = match.end()
    end = titles[i + 1].start() if i + 1 < len(titles) else len(text)

    block = text[start:end]

    # ---------------------------------
    # Tasks
    # ---------------------------------
    tasks_raw = re.split(
        r'(?=^\s*\u00C1rea:\s*.*?N\u00B0\s*Tarea:)',
        block,
        flags=re.M
    )

    tasks = []

    for t in tasks_raw:

        if not re.search(r'N\u00B0\s*Tarea:', t):
            continue

        # ---------------------------------
        # Details per task
        # ---------------------------------
        task = {

            "area": extract(t, r'\u00C1rea:\s*(.*?)\s*N\u00B0\s*Tarea'),
            "n_task": extract(t, r'N\u00B0\s*Tarea:\s*([0-9/]+)'),
            "occupation_zone": extract(t, r'Zona\s*de\s*Ocupaci\u00F3n:\s*(.*?)\s*Descripci\u00F3n'),
            "description": extract(t, r'Descripci\u00F3n:\s*(.*?)\s*Sistema\s*de\s*Trabajo'),
            "work_system": extract(t, r'Sistema\s*de\s*Trabajo:\s*(.*?)\s*PK:'),
            "pk": extract(t, r'PK:\s*(.*?)\s*Fecha\s*de\s*Inicio'),
            "begin_date": extract(t, r'Fecha\s*de\s*Inicio:\s*([0-9\-]+)'),
            "end_date": extract(t, r'Fecha\s*de\s*Fin:\s*([0-9\-]+)'),
            "schedules": extract_schedule(t),
            "week_days": extract(t, r'D\u00EDas\s*de\s*la\s*semana:\s*([A-Z, ]+)'),
            "responsible": extract(t, r'Responsable\s*de\s*la\s*tarea\s*:\s*(.*?)\s*Maquinaria:'),
            "machinery": extract(t, r'Maquinaria:\s*(.*?)\s*Activos'),
            "assets": extract(t, r'Activos:\s*(.*?)\s*Consideraciones'),
            "considerations": extract(t, r'Consideraciones:\s*(.*?)\s*Procedimiento'),
            "procedure": extract(t, r'Procedimiento:\s*(.*?)\s*Gamas'),
            "gamas": extract(t, r'Gamas:\s*(.*?)(?:\n|$)')
        }

        task["assets"] = [a.strip() for a in (task["assets"] or "").split("/") if a.strip()]
        task["gamas"] = [g.strip() for g in (task["gamas"] or "").split("/") if g.strip()]

        # Validate a task
        state, error_description = validate_task(task)

        task["state"] = state
        task["error_description"] = error_description

        tasks.append(task)

    tasks_dictionary.setdefault(day, {}).setdefault(subtitle, []).extend(tasks)

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
        "work_orders_count": unique_work_orders
    },
    "tasks": tasks_dictionary
}

SetVar("work_order_dictionary", json.dumps(work_order_dictionary, ensure_ascii=False))