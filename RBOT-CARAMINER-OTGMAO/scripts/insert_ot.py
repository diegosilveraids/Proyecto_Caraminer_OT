# -*- coding: utf-8 -*-
import requests
import time
from datetime import datetime, timedelta, timezone

BASE_URL = "https://carltest.caraminer.com/cmms/api"
TOKEN = "4e4a543e0c6cf75c1e771c3ebf08b5b2ff4bf5616e1c145e840019343e2ec884"

HEADERS = {
    "X-CS-Access-Token": TOKEN,
    "Content-Type": "application/vnd.api+json",
    "Accept": "application/vnd.api+json"
}

def get_entity(entity_type: str, filters: dict, limit: int = 1) -> list:
    url = f"{BASE_URL}/entities/v1/{entity_type}"

    params = filters.copy()
    params["page[limit]"] = limit

    response = requests.get(url=url, headers=HEADERS, params=params, timeout=30)

    if response.status_code != 200:
        raise Exception(
            f"Error GET {entity_type}: {response.status_code} - {response.text}"
        )
    
    return response.json().get("data", [])

def get_id_by_code(entity_type: str, code: str) -> str:
    data = get_entity(
        entity_type, 
        {f"filter[{entity_type}][code]": code}
    )

    if not data:
        raise Exception(f"No se encontró {entity_type} con code={code}")
    
    return data[0]["id"]

def get_gama_data(gama_code: str) -> dict:
    """
    Returns a diccionary with the required fields of a gama 
    (pwo) searched by code.
    """

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
        "modifyDate": attributes.get("modifyDate"),
        "statusChangedDate": attributes.get("statusChangedDate"),
        "toSchedule": attributes.get("toSchedule"),
        "workPriority": attributes.get("workPriority"),
        "statusCode": attributes.get("statusCode"),
        "description": attributes.get("description"),
        "workRecept": attributes.get("workRecept"),
        "currencyCode": attributes.get("currencyCode"),
        "fixedDate": attributes.get("fixedDate"),
        "eqptStop": attributes.get("eqptStop"),
    }

def build_datetime(date_str: str, time_str: str) -> str:
    """
    Converts 'DD-MM-YYYY' + 'HH:SS' to ISO 8601 -03:00 without microseconds.
    """
    tz = timezone(timedelta(hours=-3))

    date_time = datetime.strptime(
        f"{date_str} {time_str}",
        "%d-%m-%Y %H:%M"
    )

    date_time = date_time.replace(tzinfo=tz, microsecond=0)

    return date_time.isoformat()

def create_wo(order: dict):
    wo_types ={
        "PREV": "PREVENTIVO",
        # "CORP": "CORR-PROGRAMADO"
        "_ZAD": "CORR-PROGRAMADO" # TODO: eliminar esto.
    }
    suffix = order["gama"][-4:]
    if suffix not in wo_types:
        raise ValueError(f"No se puede determinar el tipo de la gama: {order['gama']}")
    
    gama_type = wo_types[suffix]
    gama_data = get_gama_data(order["gama"])
    gama_id = gama_data["id"]
    material_id = get_id_by_code("material", order["activo"])
    action_type_id = get_id_by_code("actiontype", gama_type)
    cost_center_id = get_id_by_code("costcenter", order["area"][0].upper())

    inicio_str = build_datetime(order["fecha_inicio"], order["hora_inicio"])
    fin_str = build_datetime(order["fecha_fin"], order["hora_fin"])

    # TODO: posibles datos faltantes -> site, company, responsible, planner, department, origin
    payload = {
        "data": {
            "type": "wo",
            "attributes": {
                "xtraTxt11": order["week"], # SEMANA
                "xtraTxt09": order["nro_tarea"], # NRO TAREA
                "description": gama_data["description"], # TÍTULO
                "descriptionSearch": gama_data["description"], # TITULO TODO: revisar si hay que enviar o no
                "WOBegin": inicio_str, # FECHA DE INICIO
                "WOEnd": fin_str, # FECHA DE FINALIZACIÓN
                "workPriority": gama_data["workPriority"], # PRIORIDAD
                "currencyCode": gama_data["currencyCode"], # MONEDA
                "toSchedule": gama_data["toSchedule"], # TODO: Revisar si hay que enviar o no
                "fixedDt": gama_data["fixedDate"], # TODO: Revisar si hay que enviar o no
                "workRecept": gama_data["workRecept"],
                "eqptStop": gama_data["eqptStop"]

                # Campos adicionales
                # "area": orden["area"],
                # "zona_ocupacion": orden["zona_ocupacion"],
                # "sistema_trabajo": orden["sistema_trabajo"],
                # "xtraTxt03": orden["pk"]["inicial"],
                # "xtraTxt04": orden["pk"]["final"],
                # "responsable": orden["responsable"],
                # "consideraciones": orden["consideraciones"],
                # "maquinaria": orden["maquinaria"],
                # "procedimiento": orden["procedimiento"]
            },
            "relationships": {
                "material": {
                    "data": {
                        "type": "material",
                        "id": material_id
                    }
                },
                "PWO": {
                    "data": {
                        "type": "pwo",
                        "id": gama_id
                    }
                },
                "actionType": {
                    "data": {
                        "type": "actiontype",
                        "id": action_type_id
                    }
                },
                "costCenter": {
                    "data": {
                        "type": "costcenter",
                        "id": cost_center_id
                    }
                }
            }
        }
    }

    url = f"{BASE_URL}/entities/v1/wo"

    response = requests.post(url, headers=HEADERS, json=payload, timeout=30)

    if response.status_code not in (200, 201):
        raise Exception(
            f"Error creando WO: {response.status_code} - {response.text}"
        )

    return response.json()


# ---------------
# Data
# ---------------

work_order_prev = {
    "week": "W34",
    "nro_tarea": "444/10",
    "area": "Vías",
    "gama": "I_F_8_CON_VEG_PREV",
    "activo": "LC012",
    "fecha_inicio": "20-10-2025",
    "fecha_fin": "20-10-2025",
    "hora_inicio": "06:30",
    "hora_fin": "10:00",
    
    # Campos aún no asignados 
    "zona_ocupacion": "PELIGRO",
    "sistema_trabajo": "EVB",
    "pk": {
        "inicial": "008+300",
        "final": "0012+000",
    },
    "responsable": "Encargado de trabajo",
    "consideraciones": "Pans: LC027; ...",
    "dia_semana": "L",
    "maquinaria": "",
    "procedimiento": "PR O-VIA-CO-PAN-001",
    # "descripcion": "Control de Vegetación desde script PREVENTIVA con CC V y fecha",
}

work_order_corr = {
    "week": "W56",
    "nro_tarea": "123/45",
    "area": "Infraestructura",
    "gama": "I_F_10_LIMP_CORP_ZAD",
    "activo": "LC012",
    "fecha_inicio": "20-10-2025",
    "fecha_fin": "20-10-2025",
    "hora_inicio": "06:30",
    "hora_fin": "10:00",
    
    # Campos aún no asignados 
    "zona_ocupacion": "PELIGRO",
    "sistema_trabajo": "EVB",
    "pk": {
        "inicial": "008+300",
        "final": "0012+000",
    },
    "responsable": "Encargado de trabajo",
    "consideraciones": "Pans: LC027; ...",
    "dia_semana": "L",
    "maquinaria": "",
    "procedimiento": "PR O-VIA-CO-PAN-001",
    # "descripcion": "Control de Vegetación desde script PREVENTIVA con CC V y fecha",
}


if __name__ == "__main__":
    start_time = time.perf_counter()
    resultado = create_wo(work_order_corr)
    end_time = time.perf_counter()

    elapsed_time = end_time - start_time
    print(f"WO created successfuly in {elapsed_time}")
    # print(resultado)