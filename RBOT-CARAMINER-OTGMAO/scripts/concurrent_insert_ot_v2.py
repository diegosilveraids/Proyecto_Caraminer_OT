# -*- coding: utf-8 -*-
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import requests

API_BASE_URL = ""
BATCH_SIZE = 25
MAX_WORKERS = 5
REQUEST_TIMEOUT = 30

session = requests.Session()


def init_session(token: str, base_url: str) -> None:
    global API_BASE_URL

    API_BASE_URL = base_url.rstrip("/")
    headers = {
        "X-CS-Access-Token": token,
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/vnd.api+json",
    }
    session.headers.clear()
    session.headers.update(headers)


def get_entity(entity_type: str, filters: dict, limit: int = 1) -> list:
    url = f"{API_BASE_URL}/entities/v1/{entity_type}"
    params = filters.copy()
    params["page[limit]"] = limit

    response = session.get(url=url, params=params, timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        raise Exception(f"Error GET {entity_type}: {response.status_code} - {response.text}")

    return response.json().get("data", [])


@lru_cache(maxsize=None)
def get_id_by_code(entity_type: str, code: str) -> str:
    data = get_entity(entity_type, {f"filter[{entity_type}][code]": code})
    if not data:
        raise Exception(f"No se encontro {entity_type} con code={code}")
    return data[0]["id"]


@lru_cache(maxsize=None)
def get_gama_data(gama_code: str) -> dict:
    data = get_entity("pwo", {"filter[pwo][code]": gama_code})
    if not data:
        raise Exception(f"No se encontro la gama con code={gama_code}")

    entity = data[0]
    attributes = entity.get("attributes", {})

    return {
        "id": entity.get("id"),
        "toSchedule": attributes.get("toSchedule"),
        "workPriority": attributes.get("workPriority"),
        "description": attributes.get("description"),
        "workRecept": attributes.get("workRecept"),
        "currencyCode": attributes.get("currencyCode"),
        "fixedDate": attributes.get("fixedDate"),
        "eqptStop": attributes.get("eqptStop"),
    }


@lru_cache(maxsize=None)
def get_relationship(entity_type: str, entity_id: str, relationship: str):
    url = f"{API_BASE_URL}/entities/v1/{entity_type}/{entity_id}/relationships/{relationship}"
    response = session.get(url=url, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        raise Exception(
            f"Error GET relationship {entity_type}.{relationship}: "
            f"{response.status_code} - {response.text}"
        )

    return response.json().get("data")


@lru_cache(maxsize=None)
def get_action_type_id_from_gama(gama_code: str) -> str:
    gama_data = get_gama_data(gama_code)
    gama_id = gama_data["id"]

    rel = get_relationship("pwo", gama_id, "actionType")
    if not rel:
        raise Exception(f"La gama '{gama_code}' no tiene actionType asociado")

    return rel["id"]


@lru_cache(maxsize=None)
def get_gama_processes(gama_id: str) -> list:
    url = f"{API_BASE_URL}/entities/v1/pwo/{gama_id}/processes"
    response = session.get(url=url, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        raise Exception(
            f"Error GET pwo processes para gama '{gama_id}': "
            f"{response.status_code} - {response.text}"
        )

    data = response.json().get("data", [])
    return [
        {
            "id": item.get("id"),
            "type": item.get("type"),
            "attributes": item.get("attributes", {}),
        }
        for item in data
    ]


def get_process_id_from_pwo_process(tipo: str, proceso_id: str):
    url = f"{API_BASE_URL}/entities/v1/{tipo}/{proceso_id}/relationships/process"
    response = session.get(url=url, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        raise Exception(
            f"Error GET process desde {tipo} '{proceso_id}': "
            f"{response.status_code} - {response.text}"
        )

    data = response.json().get("data")
    if not data:
        return None

    return data.get("id")


def create_exp_process_for_wo(
    wo_id: str,
    exp_type: str,
    process_id: str,
    ordering=None,
    comment=None,
    mandatory=None,
) -> dict:
    payload = {
        "data": {
            "type": exp_type,
            "relationships": {
                "WO": {"data": {"type": "wo", "id": wo_id}},
                "process": {"data": {"type": "process", "id": process_id}},
            },
        }
    }

    attributes = {}
    if ordering is not None:
        attributes["ordering"] = ordering
    if comment is not None:
        attributes["comment"] = comment
    if mandatory is not None:
        attributes["mandatory"] = mandatory
    if attributes:
        payload["data"]["attributes"] = attributes

    url = f"{API_BASE_URL}/entities/v1/{exp_type}"
    response = session.post(url, json=payload, timeout=REQUEST_TIMEOUT)

    if response.status_code not in (200, 201):
        raise Exception(
            f"Error creando {exp_type} para WO {wo_id}: "
            f"{response.status_code} - {response.text}"
        )

    return response.json()


@lru_cache(maxsize=None)
def build_datetime(date_str: str, time_str: str) -> str:
    tz = timezone(timedelta(hours=-3))
    date_time = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
    date_time = date_time.replace(tzinfo=tz, microsecond=0)
    return date_time.isoformat()


@lru_cache(maxsize=None)
def parse_pk(pk: str) -> float:
    if pk is None:
        raise ValueError("PK es None")

    raw = str(pk).strip()
    if "+" not in raw:
        raise ValueError(f"Formato invalido de PK: {raw}")

    km, meters = raw.split("+", 1)
    if not km.isdigit() or not meters.isdigit():
        raise ValueError(f"PK invalido: {raw}")

    meters = meters.zfill(3)
    return float(f"{int(km)}.{meters}")


def has_asset(order: dict) -> bool:
    value = order.get("activo")
    return value is not None and str(value).strip() != ""


def create_wo(order: dict) -> dict:
    gama_data = get_gama_data(order["gama"])
    gama_id = gama_data["id"]
    action_type_id = get_action_type_id_from_gama(order["gama"])

    area_code = order["area"].strip()[0].upper()
    cost_center_id = get_id_by_code("costcenter", area_code)
    site_id = get_id_by_code("site", area_code)

    begin_iso = build_datetime(order["fecha_inicio"], order["hora_inicio"])
    end_iso = build_datetime(order["fecha_fin"], order["hora_fin"])

    gama_processes = get_gama_processes(gama_id)
    type_map = {
        "pwoprocess": "expwoprocess",
        "pwochoiceprocess": "expwochoiceprocess",
    }

    exp_process_templates = []
    for proc in gama_processes:
        exp_type = type_map.get(proc["type"])
        if not exp_type:
            continue

        process_id = get_process_id_from_pwo_process(proc["type"], proc["id"])
        if not process_id:
            continue

        proc_attrs = proc.get("attributes", {})
        exp_process_templates.append(
            {
                "exp_type": exp_type,
                "process_id": process_id,
                "ordering": proc_attrs.get("ordering"),
                "comment": proc_attrs.get("comment"),
                "mandatory": proc_attrs.get("mandatory"),
            }
        )

    attributes = {
        "xtraTxt11": order["week"],
        "xtraTxt09": order["nro_tarea"],
        "description": gama_data.get("description"),
        "WOBegin": begin_iso,
        "WOEnd": end_iso,
    }

    relationships = {
        "PWO": {"data": {"type": "pwo", "id": gama_id}},
        "actionType": {"data": {"type": "actiontype", "id": action_type_id}},
        "costCenter": {"data": {"type": "costcenter", "id": cost_center_id}},
        "site": {"data": {"type": "site", "id": site_id}},
    }

    if has_asset(order):
        material_id = get_id_by_code("material", str(order["activo"]).strip())
        relationships["material"] = {"data": {"type": "material", "id": material_id}}
    else:
        attributes["directKPBegin"] = parse_pk(order["pk_inicial"])
        attributes["directKPEnd"] = parse_pk(order["pk_final"])

    payload = {
        "data": {
            "type": "wo",
            "attributes": attributes,
            "relationships": relationships,
        }
    }

    response = session.post(
        f"{API_BASE_URL}/entities/v1/wo", json=payload, timeout=REQUEST_TIMEOUT
    )
    if response.status_code not in (200, 201):
        raise Exception(f"Error creando WO: {response.status_code} - {response.text}")

    wo_response = response.json()
    wo_id = wo_response.get("data", {}).get("id")
    if not wo_id:
        raise Exception("WO creada sin id en la respuesta")

    for template in exp_process_templates:
        create_exp_process_for_wo(
            wo_id=wo_id,
            exp_type=template["exp_type"],
            process_id=template["process_id"],
            ordering=template["ordering"],
            comment=template["comment"],
            mandatory=template["mandatory"],
        )

    return wo_response


def _normalize_order(week: str, raw: dict) -> dict:
    return {
        "week": week,
        "nro_tarea": raw.get("n_task"),
        "area": raw.get("area"),
        "gama": raw.get("gamma"),
        "activo": raw.get("asset"),
        "pk_inicial": (raw.get("pk") or {}).get("initial_pk"),
        "pk_final": (raw.get("pk") or {}).get("final_pk"),
        "fecha_inicio": raw.get("begin_date"),
        "fecha_fin": raw.get("end_date"),
        "hora_inicio": (raw.get("schedule") or {}).get("begin"),
        "hora_fin": (raw.get("schedule") or {}).get("end"),
    }


def extract_jobs(parsed: dict) -> list:
    week = (parsed.get("metadata") or {}).get("week")
    if not week:
        raise ValueError("El parsed report no contiene metadata.week")

    jobs = []
    grouped_orders = parsed.get("work_orders") or {}

    for _, systems in grouped_orders.items():
        if not isinstance(systems, dict):
            continue

        for _, orders in systems.items():
            if not isinstance(orders, list):
                continue

            for order in orders:
                if (order or {}).get("state") != "READ-SUCCESS":
                    continue
                jobs.append(_normalize_order(week=week, raw=order))

    return jobs


def chunked(values: list, size: int):
    for idx in range(0, len(values), size):
        yield values[idx : idx + size]


def process_single_job(index: int, job: dict) -> dict:
    task = str(job.get("nro_tarea"))
    try:
        wo_response = create_wo(job)
        wo_id = wo_response.get("data", {}).get("id")
        return {"index": index, "task": task, "ok": True, "wo_id": wo_id, "error": ""}
    except Exception as exc:
        return {"index": index, "task": task, "ok": False, "wo_id": None, "error": str(exc)}


def process_in_batches(jobs: list, batch_size: int, max_workers: int) -> list:
    total = len(jobs)
    results = []

    for batch_num, batch in enumerate(chunked(jobs, batch_size), start=1):
        batch_start = ((batch_num - 1) * batch_size) + 1
        batch_end = min(batch_num * batch_size, total)
        print(f"[BATCH {batch_num}] Procesando jobs {batch_start}-{batch_end} de {total}")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(process_single_job, batch_start + idx - 1, job): job
                for idx, job in enumerate(batch, start=1)
            }

            for future in as_completed(future_map):
                result = future.result()
                results.append(result)
                if result["ok"]:
                    print(f"  OK   tarea={result['task']} wo_id={result['wo_id']}")
                else:
                    print(f"  FAIL tarea={result['task']} error={result['error']}")

    return results


def print_summary(results: list, elapsed_seconds: float) -> None:
    total = len(results)
    success = sum(1 for item in results if item["ok"])
    failed = total - success

    print("\n=== RESUMEN ===")
    print(f"Total jobs: {total}")
    print(f"Success:    {success}")
    print(f"Failed:     {failed}")
    print(f"Elapsed:    {elapsed_seconds:.2f}s")

    if failed:
        print("\nErrores detectados:")
        for item in (x for x in results if not x["ok"]):
            print(f"- idx={item['index']} tarea={item['task']} error={item['error']}")


def main() -> int:
    # if len(sys.argv) != 3:
    #     print(
    #         "Uso: python concurrent_insert_ot_v2.py "
    #         "<parsed_report_path> <api_token> <base_url>"
    #     )
    #     return 2

    parsed_report_path = Path(sys.argv[1])
    api_token = sys.argv[2]
    base_url = sys.argv[3]

    print(f"Parsed report path: {parsed_report_path}")

    if not parsed_report_path.exists():
        print(f"No existe el archivo parsed: {parsed_report_path}")
        return 2

    if not api_token.strip():
        print("API token vacio")
        return 2

    if not base_url.strip():
        print("Base URL vacia")
        return 2

    try:
        parsed_payload = json.loads(parsed_report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"No se pudo leer/parsear el JSON: {exc}")
        return 2

    jobs = extract_jobs(parsed_payload)
    print(f"Jobs filtrados (state=READ-SUCCESS): {len(jobs)}")

    if not jobs:
        print("No hay jobs para procesar.")
        return 0

    init_session(token=api_token, base_url=base_url)

    start = time.perf_counter()
    results = process_in_batches(jobs=jobs, batch_size=BATCH_SIZE, max_workers=MAX_WORKERS)
    elapsed = time.perf_counter() - start

    print_summary(results=results, elapsed_seconds=elapsed)

    # Exit code 0: ejecucion completa del lote aunque existan fallas por item.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
