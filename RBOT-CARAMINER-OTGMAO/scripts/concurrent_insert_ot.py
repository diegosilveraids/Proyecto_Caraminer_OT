# -*- coding: utf-8 -*-
import json

import requests
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

# --------------
# CONFIG
# --------------

BASE_URL = "https://carltest.caraminer.com/cmms/api"
TOKEN = "5bc69c549e057888aebeaed320ff5c27e605f70c59a549e3da860717a3a31ba1"

HEADERS = {
    "X-CS-Access-Token": TOKEN,
    "Content-Type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json"
}

# Reusable HTTP session
session = requests.Session()
session.headers.update(HEADERS)

# --------------
# CORE HTTP
# --------------

def get_entity(entity_type: str, filters: dict, limit: int = 1) -> list:
    url = f"{BASE_URL}/entities/v1/{entity_type}"

    params = filters.copy()
    params["page[limit]"] = limit

    response = session.get(url=url, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(
            f"Error GET {entity_type}: {response.status_code} - {response.text}"
        )

    return response.json().get("data", [])


@lru_cache(maxsize=None)
def get_id_by_code(entity_type: str, code: str) -> str:
    data = get_entity(
        entity_type,
        {f"filter[{entity_type}][code]": code}
    )

    if not data:
        raise Exception(f"No se encontró {entity_type} con code={code}")

    return data[0]["id"]


@lru_cache(maxsize=None)
def get_gama_data(gama_code: str) -> dict:
    data = get_entity(
        "pwo",
        {"filter[pwo][code]": gama_code}
    )

    if not data:
        raise Exception(f"No se encontró la gama con code={gama_code}")

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
def get_relationship(entity_type: str, entity_id: str, relationship: str) -> dict | None:
    url = f"{BASE_URL}/entities/v1/{entity_type}/{entity_id}/relationships/{relationship}"

    response = session.get(url=url, timeout=30)

    if response.status_code != 200:
        raise Exception(
            f"Error GET relationship {entity_type}.{relationship}: "
            f"{response.status_code} - {response.text}"
        )

    return response.json().get("data")


@lru_cache(maxsize=None)
def get_action_type_id_from_gama(gama_code: str) -> str:
    # 1. obtener gama
    gama_data = get_gama_data(gama_code)
    gama_id = gama_data["id"]

    # 2. obtener relationship actionType
    rel = get_relationship("pwo", gama_id, "actionType")

    if not rel:
        raise Exception(f"La gama '{gama_code}' no tiene actionType asociado")

    return rel["id"]


@lru_cache(maxsize=None)
def get_gama_processes(gama_id: str) -> list:
    url = f"{BASE_URL}/entities/v1/pwo/{gama_id}/processes"
    response = session.get(url=url, timeout=30)

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
            "attributes": item.get("attributes", {})
        }
        for item in data
    ]

def get_process_id_from_pwo_process(tipo: str, proceso_id: str) -> str:
    url = f"{BASE_URL}/entities/v1/{tipo}/{proceso_id}/relationships/process"
    response = session.get(url=url, timeout=30)

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
    ordering: int | None = None,
    comment: str | None = None,
    mandatory: bool | None = None
) -> dict:
    payload = {
        "data": {
            "type": exp_type,
            "relationships": {
                "WO": {
                    "data": {"type": "wo", "id": wo_id}
                },
                "process": {
                    "data": {"type": "process", "id": process_id}
                }
            }
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

    url = f"{BASE_URL}/entities/v1/{exp_type}"
    response = session.post(url, json=payload, timeout=30)

    if response.status_code not in (200, 201):
        raise Exception(
            f"Error creando {exp_type} para WO {wo_id}: "
            f"{response.status_code} - {response.text}"
        )

    return response.json()

# --------------
# HELPERS
# --------------

@lru_cache(maxsize=None)
def build_datetime(date_str: str, time_str: str) -> str:
    tz = timezone(timedelta(hours=-3))

    date_time = datetime.strptime(
        f"{date_str} {time_str}",
        "%d-%m-%Y %H:%M"
    )

    date_time = date_time.replace(tzinfo=tz, microsecond=0)
    return date_time.isoformat()

@lru_cache(maxsize=None)
def parse_pk(pk: str) -> float:
    """
    Convierte PK de formato '000+923' a float 0.923
    """

    if pk is None:
        raise ValueError("PK es None")

    pk = pk.strip()

    if "+" not in pk:
        raise ValueError(f"Formato inválido de PK: {pk}")

    km, metros = pk.split("+", 1)

    if not km.isdigit() or not metros.isdigit():
        raise ValueError(f"PK inválido: {pk}")

    # asegurar 3 dígitos en metros
    metros = metros.zfill(3)

    return float(f"{int(km)}.{metros}")

def tiene_activo(order: dict) -> bool:
    activo = order.get("activo")
    return activo is not None and str(activo).strip() != ""

# --------------
# WO CREATION
# --------------

def create_wo(order: dict):
    gama_data = get_gama_data(order["gama"])
    gama_id = gama_data["id"]

    action_type_id = get_action_type_id_from_gama(order["gama"])

    area_code = order["area"].strip()[0].upper()
    cost_center_id = get_id_by_code("costcenter", area_code)
    site_id = get_id_by_code("site", area_code)

    inicio_str = build_datetime(order["fecha_inicio"], order["hora_inicio"])
    fin_str = build_datetime(order["fecha_fin"], order["hora_fin"])

    gama_processes = get_gama_processes(gama_id)

    type_map = {
        "pwoprocess": "expwoprocess",
        "pwochoiceprocess": "expwochoiceprocess"
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
        exp_process_templates.append({
            "exp_type": exp_type,
            "process_id": process_id,
            "ordering": proc_attrs.get("ordering"),
            "comment": proc_attrs.get("comment"),
            "mandatory": proc_attrs.get("mandatory")
        })


    attributes = {
        "xtraTxt11": order["week"],
        "xtraTxt09": order["nro_tarea"],
        "description": gama_data["description"],
        "WOBegin": inicio_str,
        "WOEnd": fin_str,
        
        # Todos estos son opcionales?
        # "workPriority": gama_data["workPriority"],
        # "currencyCode": gama_data["currencyCode"],
        # "toSchedule": gama_data["toSchedule"],
        # "fixedDt": gama_data["fixedDate"],
        # "workRecept": gama_data["workRecept"],
        # "eqptStop": gama_data["eqptStop"]
    }

    relationships = {
        "PWO": {
            "data": {"type": "pwo", "id": gama_id}
        },
        "actionType": {
            "data": {"type": "actiontype", "id": action_type_id}
        },
        "costCenter": {
            "data": {"type": "costcenter", "id": cost_center_id}
        },
        "site": {
            "data": {"type": "site", "id": site_id}
        }
    }

    if tiene_activo(order):
        material_id = get_id_by_code("material", order["activo"])
        relationships["material"] = {
            "data": {"type": "material", "id": material_id}
        }
    else:
        attributes["directKPBegin"] = parse_pk(order["pk_inicial"])
        attributes["directKPEnd"] = parse_pk(order["pk_final"])

    payload = {
        "data": {
            "type": "wo",
            "attributes": attributes,
            "relationships": relationships
        }
    }

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    url = f"{BASE_URL}/entities/v1/wo"

    response = session.post(url, json=payload, timeout=30)

    print("WO insert -> status:", response.status_code)
    try:
        print("WO insert -> body:", response.json())
    except ValueError:
        print("WO insert -> body (raw):", response.text)

    if response.status_code not in (200, 201):
        raise Exception(
            f"Error creando WO: {response.status_code} - {response.text}"
        )

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
            mandatory=template["mandatory"]
        )

    return wo_response

# ----------------------------
# CONCURRENT EXECUTION
# ----------------------------

def create_many_wos(orders: list, max_workers: int = 5):
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(create_wo, order) for order in orders]

        for future in as_completed(futures):
            results.append(future.result())

    return results


# --------------
# EXAMPLE DATA
# --------------

# work_order_example = {
#     "week": "W08", #xtraTxt11
#     "nro_tarea": "613/02", # xtraTxt09
#     "area": "Señalización", # site
#     "gama": "S_F_CORRECTIVO", # PWO
#     "activo": "LC003", # material

#     # PKs parseados
#     "pk_inicial": "000+923", # directKPBegin
#     "pk_final": "009+306", # directKPEnd

#     # fechas
#     "fecha_inicio": "16-02-2026", # WOBeginDate
#     "fecha_fin": "16-02-2026", # WOEndDate

#     # primer schedule
#     "hora_inicio": "05:00", # WOBeginTime
#     "hora_fin": "08:00", # WOEndTime
# }

work_order_example = {
    "week": "W08", #xtraTxt11
    "nro_tarea": "625/02", # xtraTxt09
    "area": "Infraestructura", # site
    "gama": "I_F_8_CON_VEG_PREV", # PWO
    "activo": None, # material

    # PKs parseados
    "pk_inicial": "000+500", # directKPBegin
    "pk_final": "059+487", # directKPEnd

    # fechas
    "fecha_inicio": "16-02-2026", # WOBeginDate
    "fecha_fin": "16-02-2026", # WOEndDate

    # primer schedule
    "hora_inicio": "05:00", # WOBeginTime
    "hora_fin": "23:30", # WOEndTime
}

if __name__ == "__main__":

    # Multiple OT simulation
    orders = [work_order_example for _ in range(1)]
    start_time = time.perf_counter()
    create_many_wos(orders, max_workers=5)
    end_time = time.perf_counter()
    print(f"WO batch completed in {end_time - start_time:.2f} seconds")