# -*- coding: cp1252 -*-
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
    pdf_read_raw = GetVar("pdf_read")
    if isinstance(pdf_read_raw, str):
        print("A" * 50)
        pdf_read_raw = pdf_read_raw.encode("utf-8", "ignore").decode("utf-8")

    pdf_read = ast.literal_eval(pdf_read_raw)

except Exception:
    pdf_read_raw = re.sub(r"[^\x00-\x7F]+", " ", GetVar("pdf_read"))
    pdf_read = ast.literal_eval(pdf_read_raw)

# ---------------------------------
# Function definitions
# ---------------------------------

def extraer(txt, patron):
    m = re.search(patron, txt, re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def extraer_horarios(txt):

    # Clean text
    txt = (
        txt
        .replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\u00a0", " ")
    )

    horarios = []

    # Time pattern
    patron = re.compile(
        r'Hora\s*inicio:\s*([0-9]{1,2}:[0-9]{2})\s*'
        r'Hora\s*final:\s*([0-9]{1,2}:[0-9]{2})',
        re.I
    )

    for ini, fin in patron.findall(txt):
        horarios.append({
            "inicio": ini.strip(),
            "fin": fin.strip()
        })

    return horarios


def validar_tarea_json(tarea):
    errores = []
    if not tarea.get("area"):
        errores.append("Falta area")

    if not tarea.get("n_tarea"):
        errores.append("Falta n_tarea")

    if not tarea.get("gamas"):
        errores.append("Falta gamas")

    if not tarea.get("fecha_inicio"):
        errores.append("Falta fecha_inicio")

    if not tarea.get("fecha_fin"):
        errores.append("Falta fecha_fin")

    horarios = tarea.get("horarios", [])

    if not horarios:
        errores.append("Falta horarios")

    else:
        if horarios[0]["inicio"] > horarios[-1]["fin"]:
            errores.append("Horario inconsistente")

    if tarea.get("fecha_inicio") and tarea.get("fecha_fin"):
        if tarea["fecha_inicio"] > tarea["fecha_fin"]:
            errores.append("fecha_inicio > fecha_fin")

    if errores:
        return "ERROR", " | ".join(errores)

    return "CORRECTO", ""

# ---------------------------------
# Extract metadata from first page
# ---------------------------------

pagina_0 = next((p["text"] for p in pdf_read if p.get("page") == 1), "")

metadata = {
    "nombre_acta": extraer(pagina_0, r'(FO\s*O-PLA-[0-9A-Z\-]+)'),
    "estado": extraer(pagina_0, r'\b(APROBAD[OA])\b'),
    "fecha": extraer(pagina_0, r'\n\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\s*\n'),
    "semana": extraer(pagina_0, r'SEMANA\s*([0-9]{1,2})')
}
# ---------------------------------
# Report full text (excluding first
# page and repeated pattern)
# ---------------------------------

texto = "\n".join(p["text"] for p in pdf_read if p.get("page") != 1)

texto = re.sub(
    r'SISTEMA\s+INTEGRADO\s+DE\s+GESTIÓN.*?Hoja\s+\d+\s+de\s+\d+',
    '',
    texto,
    flags=re.I | re.S
)

# ---------------------------------
# Titles per day
# ---------------------------------
regex_titulo = re.compile(
    r'^\s*(LUNES|MARTES|MIERCOLES|MIÉRCOLES|JUEVES|VIERNES|SABADO|SÁBADO|DOMINGO)\b.*?(?=\n\s*Área:)',
    re.I | re.S | re.M
)

titulos = list(regex_titulo.finditer(texto))

resultado = {}

for i, match in enumerate(titulos):

    titulo = match.group().strip()

    m = re.match(
        r'^\s*(LUNES|MARTES|MIERCOLES|MIÉRCOLES|JUEVES|VIERNES|SABADO|SÁBADO|DOMINGO)\b\s*(.*)',
        titulo,
        re.I | re.S
    )

    if not m:
        dia = "DESCONOCIDO"
        subtitulo = titulo
    else:
        dia = m.group(1).upper()
        subtitulo = re.sub(r'\s+', ' ', m.group(2)).strip() or "SIN CATEGORIA"

    start = match.end()
    end = titulos[i + 1].start() if i + 1 < len(titulos) else len(texto)

    bloque = texto[start:end]

    # ---------------------------------
    # Tasks
    # ---------------------------------
    trabajos_raw = re.split(
        r'(?=^\s*Área:\s*.*?N°\s*Tarea:)',
        bloque,
        flags=re.M
    )

    trabajos = []

    for t in trabajos_raw:

        if not re.search(r'N°\s*Tarea:', t):
            continue

        # ---------------------------------
        # Details per task
        # ---------------------------------
        trabajo = {

            "area": extraer(t, r'Área:\s*(.*?)\s*N°\s*Tarea'),
            "n_tarea": extraer(t, r'N°\s*Tarea:\s*([0-9/]+)'),
            "zona_ocupacion": extraer(t, r'Zona\s*de\s*Ocupación:\s*(.*?)\s*Descripción'),
            "descripcion": extraer(t, r'Descripción:\s*(.*?)\s*Sistema\s*de\s*Trabajo'),
            "sistema_trabajo": extraer(t, r'Sistema\s*de\s*Trabajo:\s*(.*?)\s*PK:'),
            "pk": extraer(t, r'PK:\s*(.*?)\s*Fecha\s*de\s*Inicio'),
            "fecha_inicio": extraer(t, r'Fecha\s*de\s*Inicio:\s*([0-9\-]+)'),
            "fecha_fin": extraer(t, r'Fecha\s*de\s*Fin:\s*([0-9\-]+)'),
            "horarios": extraer_horarios(t),
            "dias_semana": extraer(t, r'Días\s*de\s*la\s*semana:\s*([A-Z, ]+)'),
            "responsable": extraer(t, r'Responsable\s*de\s*la\s*tarea\s*:\s*(.*?)\s*Maquinaria:'),
            "maquinaria": extraer(t, r'Maquinaria:\s*(.*?)\s*Activos'),
            "assets": extraer(t, r'Activos:\s*(.*?)\s*Consideraciones'),
            "consideraciones": extraer(t, r'Consideraciones:\s*(.*?)\s*Procedimiento'),
            "procedimiento": extraer(t, r'Procedimiento:\s*(.*?)\s*Gamas'),
            "gamas": extraer(t, r'Gamas:\s*(.*?)(?:\n|$)')
        }

        trabajo["assets"] = [a.strip() for a in (trabajo["assets"] or "").split("/") if a.strip()]
        trabajo["gamas"] = [g.strip() for g in (trabajo["gamas"] or "").split("/") if g.strip()]

        # Validate a task
        estado, desc = validar_tarea_json(trabajo)

        trabajo["estado"] = estado
        trabajo["descripcion_error"] = desc

        trabajos.append(trabajo)

    resultado.setdefault(dia, {}).setdefault(subtitulo, []).extend(trabajos)

# ---------------------------------
# Task and OT counting
# ---------------------------------
unique_tasks = set()
unique_work_orders = 0

for sistemas in resultado.values():
    for tareas in sistemas.values():
        for tarea in tareas:

            if tarea.get("n_tarea"):
                unique_tasks.add(tarea["n_tarea"])

            n_assets = len(tarea["assets"]) or 1
            n_gamas = len(tarea["gamas"]) or 1

            unique_work_orders += n_assets * n_gamas

# ---------------------------------
# Final json
# ---------------------------------
work_order_diccionary = {
    "metadata": {
        **metadata,
        "tasks_count": len(unique_tasks),
        "work_orders_count": unique_work_orders
    },
    "tasks": resultado
}

SetVar("res", json.dumps(work_order_diccionary, ensure_ascii=False))
