# -*- coding: utf-8 -*-
import datetime as dt
import re

from rp_helpers.rp_patterns import (
    RE_DAY_AND_SUBTITLE,
    RE_SPACES,
    RE_TASK_HAS_ID,
    RE_TASK_SPLIT,
    RE_TITLE_BY_DAY,
    RX_FIELD_AREA,
    RX_FIELD_ASSETS,
    RX_FIELD_BEGIN_DATE,
    RX_FIELD_CONSIDERATIONS,
    RX_FIELD_DESCRIPTION,
    RX_FIELD_END_DATE,
    RX_FIELD_GAMAS,
    RX_FIELD_MACHINERY,
    RX_FIELD_OCCUPATION_ZONE,
    RX_FIELD_PK,
    RX_FIELD_PROCEDURE,
    RX_FIELD_RESPONSIBLE,
    RX_FIELD_TASK_NUMBER,
    RX_FIELD_WEEK_DAYS,
    RX_FIELD_WORK_SYSTEM,
    RX_REPEATED_HEADER,
    RX_REPORT_DATE,
    RX_REPORT_NAME,
    RX_REPORT_STATE,
    RX_REPORT_WEEK,
    ensure_structure,
    extract,
    extract_schedule,
    normalize_text,
)


# def extract_pk_from_task_block(task_block_text):
#     """
#     Extract PK values directly from task block by searching for the numeric pattern.
#     This is more robust than relying on regex boundaries which fail with malformed PDFs.
#     """
#     if not task_block_text:
#         return {"initial_pk": "", "final_pk": ""}

#     matches = re.findall(r"\d{3}\+\d{3}", task_block_text)
#     return {
#         "initial_pk": matches[0] if len(matches) > 0 else "",
#         "final_pk": matches[1] if len(matches) > 1 else "",
#     }


def parse_pk(txt):
    if not txt:
        return {"initial_pk": "", "final_pk": ""}

    matches = re.findall(r"\d{3}\+\d{3}", txt)
    return {
        "initial_pk": matches[0] if len(matches) > 0 else "",
        "final_pk": matches[1] if len(matches) > 1 else "",
    }


def parse_assets(raw_assets):
    re_asset_code = re.compile(r"\b[A-Za-z]{1,4}\s*\d{1,4}\b")

    if raw_assets is None:
        return [], None

    raw = raw_assets.strip()
    if not raw:
        return [], None

    if raw.startswith("/") or raw.endswith("/") or re.search(r"/\s*/", raw):
        return [], "Invalid assets division"

    assets = [asset.strip() for asset in raw.split("/")]
    if any(not asset for asset in assets):
        return [], "Invalid assets division"

    if any(len(re_asset_code.findall(asset)) > 1 for asset in assets):
        return [], "Invalid assets division"

    return assets, None


def parse_gamas(raw_gamas):
    if raw_gamas is None:
        return [], None

    raw = raw_gamas.strip()
    if not raw:
        return [], None

    if raw.startswith("/") or raw.endswith("/") or re.search(r"/\s*/", raw):
        return [], "Invalid gamas division"

    gamas = [gama.strip() for gama in raw.split("/")]
    if any(not gama for gama in gamas):
        return [], "Invalid gamas division"

    return gamas, None


def validate_task(task, assets_error=None, gamas_error=None):
    allowed_areas = {"senalizacion", "area", "infraestructura", "vias"}
    errors = []

    if not task.get("area"):
        errors.append("Missing area")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

    if normalize_text(task.get("area")) not in allowed_areas:
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

    if not task.get("assets"):
        pk = task.get("pk") or {}
        pk_initial = (pk.get("initial_pk") or "").strip()
        pk_final = (pk.get("final_pk") or "").strip()

        if not pk_initial:
            errors.append("Missing initial_pk")
            return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

        if not pk_final:
            errors.append("Missing final_pk")
            return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

        if not re.fullmatch(r"\d{3}\+\d{3}", pk_initial):
            errors.append("Invalid pk format (expected DDD+DDD)")
            return "ERROR-FORMAT", " | ".join(errors)

        if not re.fullmatch(r"\d{3}\+\d{3}", pk_final):
            errors.append("Invalid pk format (expected DDD+DDD)")
            return "ERROR-FORMAT", " | ".join(errors)

    if not task.get("begin_date"):
        errors.append("Missing begin_date")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

    if not task.get("end_date"):
        errors.append("Missing end_date")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)

    try:
        begin_date_obj = dt.datetime.strptime(task["begin_date"], "%d-%m-%Y")
    except ValueError:
        errors.append("Invalid begin_date format (expected dd-mm-yyyy)")
        return "ERROR-FORMAT", " | ".join(errors)

    try:
        end_date_obj = dt.datetime.strptime(task["end_date"], "%d-%m-%Y")
    except ValueError:
        errors.append("Invalid end_date format (expected dd-mm-yyyy)")
        return "ERROR-FORMAT", " | ".join(errors)

    schedule = task.get("schedule", {})
    if not schedule:
        errors.append("Missing schedule")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)
    if not schedule.get("begin"):
        errors.append("Missing schedule.begin")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)
    if not schedule.get("end"):
        errors.append("Missing schedule.end")
        return "ERROR-MISS-REQUIRED-FIELD", " | ".join(errors)
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
    assets = task.get("assets", []) or [None]
    gamas = task.get("gamas", []) or [None]

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
    page_0 = next((page["text"] for page in report_read if page.get("page") == 1), "")

    report_name = extract(page_0, RX_REPORT_NAME)
    state = extract(page_0, RX_REPORT_STATE)
    date = extract(page_0, RX_REPORT_DATE)
    year = date[-4:] if date else None
    week_number = extract(page_0, RX_REPORT_WEEK)
    week = f"W{week_number}" if week_number else None

    metadata = {
        "report_name": report_name,
        "state": state,
        "date": date,
        "year": year,
        "week": week,
    }
    return metadata, report_name


def validate_metadata_required_fields(metadata):
    if not metadata.get("week"):
        raise RuntimeError("ERROR-MISS-REQUIRED-FIELD: Missing metadata.week")


def build_report_body_text(report_read):
    text = "\n".join(page["text"] for page in report_read if page.get("page") != 1)
    ensure_structure(text.strip() != "", "STRUCTURE_ERROR: report has no body text after page 1")

    return re.sub(RX_REPEATED_HEADER, "", text, flags=re.I | re.S)


def parse_task_block(task_block_text):
    task = {
        "area": extract(task_block_text, RX_FIELD_AREA),
        "n_task": extract(task_block_text, RX_FIELD_TASK_NUMBER),
        "occupation_zone": extract(task_block_text, RX_FIELD_OCCUPATION_ZONE),
        "description": extract(task_block_text, RX_FIELD_DESCRIPTION),
        "work_system": extract(task_block_text, RX_FIELD_WORK_SYSTEM),
        "pk": parse_pk(task_block_text),
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
        "error_description": None,
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
        title_match = RE_DAY_AND_SUBTITLE.match(title)

        if not title_match:
            day = "UNKNOWN"
            subtitle = title
        else:
            day = title_match.group(1).upper()
            subtitle = RE_SPACES.sub(" ", title_match.group(2)).strip() or "NO CATEGORY"

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
            tasks.extend(expand_task_by_asset_gamma(parsed_task))

        wo_dictionary.setdefault(day, {}).setdefault(subtitle, []).extend(tasks)

    ensure_structure(
        total_candidate_task_blocks > 0,
        "STRUCTURE_ERROR: no task blocks matched expected 'Área / N° Tarea' markers",
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
        "invalid_wo_count": invalid_wo_count,
    }


def build_output_dictionary(metadata, counts, wo_dictionary):
    return {"metadata": {**metadata, **counts}, "work_orders": wo_dictionary}
