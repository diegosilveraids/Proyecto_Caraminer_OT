# -*- coding: utf-8 -*-
import re
import json
import ast
import pandas as pd

# Obtener texto leído desde Rocketbot
pdf_read = GetVar("pdf_read")

# Transformar el pdf leido a un diccionario.
pdf_read = ast.literal_eval(pdf_read)

# NOTE: primera pagina
pagina_0 = next((p["text"] for p in pdf_read if p.get("page") == 1), "")

def extraer_metadata(txt):

    def extraer(patron):
        m = re.search(patron, txt, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    metadata = {
        "nombre_acta": extraer(r'(FO\s*O-PLA-[0-9A-Z\-]+)'),
        "estado": extraer(r'\b(APROBAD[OA])\b'),
        "fecha": extraer(r'\n\s*([0-9]{2}/[0-9]{2}/[0-9]{4})\s*\n'),
        "semana": extraer(r'SEMANA\s*([0-9]{1,2})')
    }

    return metadata

metadata = extraer_metadata(pagina_0)
# NOTE: fin de primera pagina

def validar_tarea_json(tarea):
    errores = []

    if not tarea.get("area"):
        errores.append("Falta campo area")

    if not tarea.get("n_tarea"):
        errores.append("Falta campo n_tarea")

    if not tarea.get("gamas"):
        errores.append("Falta campo gamas")
    
    if not tarea.get("fecha_inicio"):
        errores.append("Falta campo fecha de inicio")

    if not tarea.get("fecha_fin"):
        errores.append("Falta campo fecha de fin")

    horarios = tarea.get("horarios", [])

    if not horarios:
        errores.append("Falta horarios")
    else:
        inicio = horarios[0].get("inicio")
        fin = horarios[-1].get("fin")

        if inicio and fin and inicio > fin:
            errores.append("Error de formato horario_inicio > horario_fin")

    if tarea.get("fecha_inicio") and tarea.get("fecha_fin"):
        if tarea["fecha_inicio"] > tarea["fecha_fin"]:
            errores.append("Error de formato fecha_inicio > fecha_fin")

    if errores:
        return "ERROR", " | ".join(errores)

    return "CORRECTO", ""

# unir el texto de todas las paginas leídas en un solo string gigante sin la primera página
texto = "\n".join(p["text"] for p in pdf_read if p.get("page") != 1)

# eliminar encabezado repetido
texto = re.sub(
    r'SISTEMA\s+INTEGRADO\s+DE\s+GESTIÓN.*?Hoja\s+\d+\s+de\s+\d+',
    '',
    texto,
    flags=re.IGNORECASE | re.DOTALL
)

# detectar títulos por día
regex_titulo = re.compile(
    r'^\s*(LUNES|MARTES|MIERCOLES|MIÉRCOLES|JUEVES|VIERNES|SABADO|SÁBADO|DOMINGO)\b.*?(?=\n\s*Área:)',
    re.IGNORECASE | re.DOTALL | re.MULTILINE
)

titulos = list(regex_titulo.finditer(texto))
resultado = {}

for i, match in enumerate(titulos):

    titulo = match.group().strip()

    regex_dia_titulo = re.compile(
        r'^\s*(LUNES|MARTES|MIERCOLES|MIÉRCOLES|JUEVES|VIERNES|SABADO|SÁBADO|DOMINGO)\b\s*(.*)',
        re.IGNORECASE | re.DOTALL
    )

    m = regex_dia_titulo.match(titulo)

    if not m:
        dia = "DESCONOCIDO"
        subtitulo = titulo
    else:
        dia = m.group(1).upper()
        subtitulo = re.sub(r'\s+', ' ', m.group(2)).strip()
        if not subtitulo:
            subtitulo = "SIN CATEGORÍA"

    start = match.end()
    end = titulos[i + 1].start() if i + 1 < len(titulos) else len(texto)
    bloque = texto[start:end]

    trabajos_raw = re.split(
        r'(?=^\s*Área:\s*.*?N°\s*Tarea:)',
        bloque,
        flags=re.MULTILINE
    )

    trabajos = []

    def extraer(txt, patron):
        m = re.search(patron, txt, re.DOTALL | re.IGNORECASE)
        return re.sub(r'\s+', ' ', m.group(1)).strip() if m else None

    def extraer_horarios(txt):
        # Normalizar ligaduras Unicode reales del PDF
        txt = (
            txt
            .replace("ﬁ", "fi")
            .replace("ﬂ", "fl")
            .replace("\xa0", " ")
        )

        horarios = []

        # Patrón EXACTO para el formato real del PDF
        patron = re.compile(
            r'Hora\s*inicio:\s*([0-9]{1,2}:[0-9]{2})\s*'
            r'Hora\s*final:\s*([0-9]{1,2}:[0-9]{2})',
            re.IGNORECASE
        )

        matches = patron.findall(txt)

        for ini, fin in matches:
            horarios.append({
                "inicio": ini.strip(),
                "fin": fin.strip()
            })

        return horarios

    for t in trabajos_raw:

        if not re.search(r'N°\s*Tarea:', t):
            continue

        # NOTE: new version (includes gamas and assets)
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
            "activos": extraer(t, r'Activos:\s*(.*?)\s*Consideraciones'),
            "consideraciones": extraer(t, r'Consideraciones:\s*(.*?)\s*Procedimiento'),
            "procedimiento": extraer(t, r'Procedimiento:\s*(.*?)\s*Gamas'),
            "gamas": extraer(t, r'Gamas:\s*(.*?)(?:\n|$)')
        }
        # NUEVO
        if trabajo["activos"]:
            trabajo["activos"] = [a.strip() for a in trabajo["activos"].split("/") if a.strip()]
        else:
            trabajo["activos"] = []
        
        if trabajo["gamas"]:
            trabajo["gamas"] = [g.strip() for g in trabajo["gamas"].split("/") if g.strip()]
        else:
            trabajo["gamas"] = []
        
        estado, descripcion_error = validar_tarea_json(trabajo)

        trabajo["estado"] = estado
        trabajo["descripcion_error"] = descripcion_error

        trabajos.append(trabajo)

    if dia not in resultado:
        resultado[dia] = {}

    if subtitulo not in resultado[dia]:
        resultado[dia][subtitulo] = []

    resultado[dia][subtitulo].extend(trabajos)


# NUEVO
tareas_unicas = set()
tareas_expandida = 0

for dia, sistemas in resultado.items():
    for sistema, tareas in sistemas.items():
        for tarea in tareas:

            n = tarea.get("n_tarea")
            if n:
                tareas_unicas.add(n)

            activos = tarea.get("activos", [])
            gamas = tarea.get("gamas", [])

            n_activos = len(activos) if activos else 1
            n_gamas = len(gamas) if gamas else 1

            tareas_expandida += n_activos * n_gamas

cantidad_tareas_unicas = len(tareas_unicas)
cantidad_tareas_expandida = tareas_expandida

resultado_final = {
    "metadata": {
        **metadata,
        "cantidad_tareas_unicas": cantidad_tareas_unicas,
        "cantidad_tareas_expandida": cantidad_tareas_expandida
    },
    "work_orders": resultado
}

# SetVar("res", json.dumps(resultado, ensure_ascii=False))

SetVar("res", json.dumps(resultado_final, ensure_ascii=False))
# Generar Excel
filas = []

for dia, sistemas in resultado.items():
    for sistema, tareas in sistemas.items():
        for tarea in tareas:

            horarios = tarea.get("horarios", [])
            horario_inicio = horarios[0]["inicio"] if horarios else None
            horario_fin = horarios[-1]["fin"] if horarios else None

            activos = tarea.get("activos", [])
            gamas = tarea.get("gamas", [])

            if not activos:
                activos = [None]

            if not gamas:
                gamas = [None]

            for activo in activos:
                for gama in gamas:
                    filas.append({
                        "dia": dia,
                        "sistema_trabajo_grupo": sistema,
                        "area": tarea.get("area"),
                        "n_tarea": tarea.get("n_tarea"),
                        "descripcion": tarea.get("descripcion"),
                        "zona_ocupacion": tarea.get("zona_ocupacion"),
                        "pk": tarea.get("pk"),
                        "fecha_inicio": tarea.get("fecha_inicio"),
                        "fecha_fin": tarea.get("fecha_fin"),
                        "dias_semana": tarea.get("dias_semana"),
                        "responsable": tarea.get("responsable"),
                        "maquinaria": tarea.get("maquinaria"),
                        "consideraciones": tarea.get("consideraciones"),
                        "procedimiento": tarea.get("procedimiento"),

                        "horario_inicio": horario_inicio,
                        "horario_fin": horario_fin,

                        "activo": activo,
                        "gama": gama,

                        "semana": metadata["semana"],
                        "fecha_acta": metadata["fecha"],
                        "estado_acta": metadata["estado"],
                    })

df = pd.DataFrame(filas)

df.to_excel(
    "C:/Users/Juan Pacheco/Downloads/FO O-PLA-00-GEN-03 v031 Acta Semanal de Programación.xlsx",
    index=False
)