# -*- coding: utf-8 -*-
import re
import unicodedata

RX_SPACES = r"\s+"
RX_NON_ASCII = r"[^\x00-\x7F]+"

RX_REPORT_NAME = r"(FO\s*O-PLA-[0-9A-Z\-]+)"
RX_REPORT_STATE = r"\b(APROBAD[OA])\b"
RX_REPORT_DATE = r"\n\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\s*\n"
RX_REPORT_WEEK = r"SEMANA\s*([0-9]{1,2})"

RX_REPEATED_HEADER = r"SISTEMA\s+INTEGRADO\s+DE\s+GESTIÓN.*?Hoja\s+\d+\s+de\s+\d+"
RX_TITLE_BY_DAY = r"^\s*(LUNES|MARTES|MIERCOLES|MIÉRCOLES|JUEVES|VIERNES|SABADO|SÁBADO|DOMINGO)\b.*?(?=\n\s*Área:)"
RX_DAY_AND_SUBTITLE = r"^\s*(LUNES|MARTES|MIERCOLES|MIÉRCOLES|JUEVES|VIERNES|SABADO|SÁBADO|DOMINGO)\b\s*(.*)"

RX_TASK_SPLIT = r"(?=^\s*Área:\s*.*?N°\s*Tarea:)"
RX_TASK_HAS_ID = r"N°\s*Tarea:"

RX_FIELD_AREA = r"Área:\s*(.*?)\s*N°\s*Tarea"
RX_FIELD_TASK_NUMBER = r"N°\s*Tarea:\s*([0-9/]+)"
RX_FIELD_OCCUPATION_ZONE = r"Zona\s*de\s*Ocupación:\s*(.*?)\s*Descripción"
RX_FIELD_DESCRIPTION = r"Descripción:\s*(.*?)\s*Sistema\s*de\s*Trabajo"
RX_FIELD_WORK_SYSTEM = r"Sistema\s*de\s*Trabajo:\s*(.*?)\s*PK:"
RX_FIELD_PK = r"PK:\s*(.*?)\s*Fecha\s*de\s*Inicio"
RX_FIELD_BEGIN_DATE = r"Fecha\s*de\s*Inicio:\s*([0-9\-]+)"
RX_FIELD_END_DATE = r"Fecha\s*de\s*Fin:\s*([0-9\-]+)"
RX_FIELD_WEEK_DAYS = r"Días\s*de\s*la\s*semana:\s*([A-Z, ]+)"
RX_FIELD_RESPONSIBLE = r"Responsable\s*de\s*la\s*tarea\s*:\s*(.*?)\s*Maquinaria:"
RX_FIELD_MACHINERY = r"Maquinaria:\s*(.*?)\s*Activos"
RX_FIELD_ASSETS = r"Activos:\s*(.*?)\s*Consideraciones"
RX_FIELD_CONSIDERATIONS = r"Consideraciones:\s*(.*?)\s*Procedimiento"
RX_FIELD_PROCEDURE = r"Procedimiento:\s*(.*?)\s*Gamas"
RX_FIELD_GAMAS = r"Gamas:\s*(.*?)(?:\n|$)"

RX_SCHEDULE = (
    r"Hora\s*inicio:\s*([0-9]{1,2}:[0-9]{2})\s*"
    r"Hora\s*final:\s*([0-9]{1,2}:[0-9]{2})"
)

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


def extract(txt, patron, re_spaces=RE_SPACES):
    match = re.search(patron, txt, re.I | re.S)
    return re_spaces.sub(" ", match.group(1)).strip() if match else None


def normalize_text(txt):
    if not txt:
        return ""

    normalized = unicodedata.normalize("NFD", txt)
    without_accents = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return without_accents.casefold().strip()


def extract_schedule(txt, re_schedule=RE_SCHEDULE):
    txt = txt.replace("\ufb01", "fi").replace("\ufb02", "fl").replace("\u00a0", " ")
    matches = re_schedule.findall(txt)

    if matches:
        begin, end = matches[0]
        return {"begin": begin.strip(), "end": end.strip()}

    return {}
