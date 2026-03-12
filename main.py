import html
import re
import pandas as pd
import streamlit as st

# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================
st.set_page_config(page_title="Horario UTEC", layout="wide")

ARCHIVO_EXCEL = "Consulta_Horario_20261.xlsx"

COLUMNAS_NECESARIAS = [
    "Curso",
    "Sección",
    "Sesión Grupo",
    "Modalidad",
    "Horario",
    "Frecuencia",
    "Ubicación",
    "Vacantes",
    "Matriculados",
    "Docente",
]

# =========================================================
# ESTILOS
# =========================================================
st.markdown(
    """
    <style>
    .bloque-titulo {
        font-size: 1.55rem;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }

    div[data-testid="stButton"] > button {
        width: 100%;
        border-radius: 10px;
        background-color: #22c7d6;
        color: white;
        border: 1px solid #1bb3c1;
        font-weight: 600;
    }

    div[data-testid="stButton"] > button:hover {
        background-color: #19b4c2;
        color: white;
        border: 1px solid #169eaa;
    }

    .schedule-wrap {
        width: 100%;
        overflow-x: auto;
        padding-top: 6px;
    }

    .schedule-board {
        position: relative;
        background: white;
        border: 1px solid #d9d9d9;
    }

    .schedule-cell,
    .schedule-header,
    .schedule-time {
        position: absolute;
        box-sizing: border-box;
        border-right: 1px solid #d9d9d9;
        border-bottom: 1px solid #d9d9d9;
        background: white;
    }

    .schedule-header {
        background: #fafafa;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1;
    }

    .schedule-time {
        background: #fafafa;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1;
        font-size: 13px;
    }

    .schedule-block {
        position: absolute;
        border-radius: 10px;
        padding: 6px 8px;
        color: #1f1f1f;
        font-size: 11px;
        line-height: 1.15;
        overflow: hidden;
        border: 1px solid rgba(0,0,0,0.10);
        box-shadow: 0 1px 3px rgba(0,0,0,0.10);
        z-index: 5;
    }

    .schedule-block-title {
        font-weight: 700;
        margin-bottom: 3px;
        font-size: 11px;
    }

    .schedule-block-sub {
        font-size: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# FUNCIONES AUXILIARES
# =========================================================
def limpiar_texto(valor) -> str:
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def formatear_seccion(valor) -> str:
    txt = limpiar_texto(valor)
    if txt == "":
        return ""
    try:
        num = float(txt)
        if num.is_integer():
            return str(int(num))
        return txt
    except ValueError:
        return txt


def ordenar_seccion(valor):
    try:
        return (0, float(valor))
    except ValueError:
        return (1, str(valor))


def es_laboratorio(texto: str) -> bool:
    t = limpiar_texto(texto).upper()
    return "LABORATORIO" in t or "LAB" in t


def quitar_acentos(txt: str) -> str:
    reemplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
    }
    for k, v in reemplazos.items():
        txt = txt.replace(k, v)
    return txt


def formatear_horario_visible(horario_raw: str) -> str:
    texto = limpiar_texto(horario_raw)

    reemplazos = {
        "Lun.": "Lunes",
        "Mar.": "Martes",
        "Mie.": "Miércoles",
        "Mié.": "Miércoles",
        "Jue.": "Jueves",
        "Vie.": "Viernes",
        "Sab.": "Sábado",
        "Sáb.": "Sábado",
        "Lun": "Lunes",
        "Mar": "Martes",
        "Mie": "Miércoles",
        "Mié": "Miércoles",
        "Jue": "Jueves",
        "Vie": "Viernes",
        "Sab": "Sábado",
        "Sáb": "Sábado",
    }

    for prefijo, nombre in reemplazos.items():
        if texto.startswith(prefijo):
            resto = texto[len(prefijo):].strip()
            return f"{nombre} {resto}".strip()

    return texto


def normalizar_dia(dia_raw: str) -> str:
    d = quitar_acentos(limpiar_texto(dia_raw)).replace(".", "").lower()

    if d.startswith("lun"):
        return "Lunes"
    if d.startswith("mar"):
        return "Martes"
    if d.startswith("mie"):
        return "Miércoles"
    if d.startswith("jue"):
        return "Jueves"
    if d.startswith("vie"):
        return "Viernes"
    if d.startswith("sab"):
        return "Sábado"

    if d.startswith("lunes"):
        return "Lunes"
    if d.startswith("martes"):
        return "Martes"
    if d.startswith("miercoles"):
        return "Miércoles"
    if d.startswith("jueves"):
        return "Jueves"
    if d.startswith("viernes"):
        return "Viernes"
    if d.startswith("sabado"):
        return "Sábado"

    return ""


def parsear_horario(horario_raw: str):
    """
    Soporta formatos como:
    - Lun. 14:00 - 16:00
    - Mar.09:00 - 10:00
    - Martes 19:00 - 20:00
    - Vie 14:00-16:00
    - Miércoles 09:30 - 11:00
    """
    texto = limpiar_texto(horario_raw)
    if texto == "":
        return None

    texto = texto.replace("–", "-").replace("—", "-")
    texto = re.sub(r"\s+", " ", texto).strip()

    patron = r"^([A-Za-zÁÉÍÓÚáéíóú]+)\.?\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$"
    m = re.match(patron, texto)
    if not m:
        return None

    dia_raw = m.group(1)
    h_ini = int(m.group(2))
    min_ini = int(m.group(3))
    h_fin = int(m.group(4))
    min_fin = int(m.group(5))

    dia = normalizar_dia(dia_raw)
    if dia == "":
        return None

    inicio = h_ini + (min_ini / 60.0)
    fin = h_fin + (min_fin / 60.0)

    if fin <= inicio:
        return None

    return {
        "dia": dia,
        "inicio": inicio,
        "fin": fin,
        "texto_visible": formatear_horario_visible(texto),
    }


@st.cache_data
def cargar_datos(archivo_excel: str) -> pd.DataFrame:
    df = pd.read_excel(
        archivo_excel,
        dtype=str,
        keep_default_na=False,
        engine="openpyxl",
    )

    df.columns = [str(c).strip() for c in df.columns]

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    faltantes = [c for c in COLUMNAS_NECESARIAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas en el Excel: {faltantes}")

    df["Sección_fmt"] = df["Sección"].apply(formatear_seccion)
    return df


def agrupar_teorias(df_teorias: pd.DataFrame):
    salida = []

    if df_teorias.empty:
        return salida

    grupos = df_teorias.groupby(["Docente", "Sesión Grupo"], sort=False, dropna=False)

    for (_, _), grupo in grupos:
        grupo = grupo.copy()

        bloques = []
        vistos = set()

        for _, row in grupo.iterrows():
            modalidad = limpiar_texto(row["Modalidad"])
            horario_raw = limpiar_texto(row["Horario"])
            horario_visible = formatear_horario_visible(horario_raw)
            ubicacion = limpiar_texto(row["Ubicación"])

            firma = (modalidad, horario_raw, ubicacion)
            if firma not in vistos:
                vistos.add(firma)
                bloques.append(
                    {
                        "modalidad": modalidad,
                        "horario_raw": horario_raw,
                        "horario_visible": horario_visible,
                        "ubicacion": ubicacion,
                    }
                )

        primer = grupo.iloc[0]

        salida.append(
            {
                "docente": limpiar_texto(primer["Docente"]),
                "sesion": limpiar_texto(primer["Sesión Grupo"]),
                "vacantes": limpiar_texto(primer["Vacantes"]),
                "frecuencia": limpiar_texto(primer["Frecuencia"]),
                "bloques": bloques,
            }
        )

    return salida


def color_para_curso(curso: str) -> str:
    paleta = [
        "#BFE3C0", "#C8D9F0", "#F6D5A8", "#E7C6FF", "#FFD6D6",
        "#CDEAC0", "#F9C6A3", "#BDE0FE", "#D9ED92", "#FFC8DD",
        "#D8F3DC", "#F1C0E8", "#FAE1DD", "#C3E0E5", "#E2ECE9"
    ]
    idx = sum(ord(c) for c in curso) % len(paleta)
    return paleta[idx]


def existe_item(item_id: str) -> bool:
    return any(x["id"] == item_id for x in st.session_state["matriculas"])


def bloques_se_superponen(a, b):
    if a["dia"] != b["dia"]:
        return False
    return a["inicio"] < b["fin"] and b["inicio"] < a["fin"]


def matricular_item(item: dict):
    actuales = st.session_state["matriculas"]

    # Reemplaza teoría previa del mismo curso o lab previo del mismo curso
    filtrados = [
        x for x in actuales
        if not (x["curso"] == item["curso"] and x["categoria"] == item["categoria"])
    ]

    filtrados.append(item)
    st.session_state["matriculas"] = filtrados

    # Mensaje informativo por cruce, pero NO bloquea
    bloques_nuevos = armar_bloques_render([item])
    bloques_todos = armar_bloques_render(filtrados)

    cursos_con_cruce = set()
    for bn in bloques_nuevos:
        for bt in bloques_todos:
            if bt["item_id"] == bn["item_id"]:
                continue
            if bloques_se_superponen(bn, bt):
                cursos_con_cruce.add(bt["curso"])

    if cursos_con_cruce:
        lista = ", ".join(sorted(cursos_con_cruce))
        st.session_state["mensaje"] = f"Se matriculó, pero tiene cruce con: {lista}."
        st.session_state["tipo_mensaje"] = "warning"
    else:
        st.session_state["mensaje"] = f"Se matriculó: {item['curso']} - {item['sesion']}"
        st.session_state["tipo_mensaje"] = "success"


def quitar_item(item_id: str):
    st.session_state["matriculas"] = [
        x for x in st.session_state["matriculas"] if x["id"] != item_id
    ]
    st.session_state["mensaje"] = "Se quitó el curso/grupo del horario."
    st.session_state["tipo_mensaje"] = "warning"


def limpiar_horario():
    st.session_state["matriculas"] = []
    st.session_state["mensaje"] = "Horario limpiado."
    st.session_state["tipo_mensaje"] = "warning"


def seleccionar_curso(curso: str):
    st.session_state["curso_seleccionado"] = curso


def armar_bloques_render(matriculas):
    bloques = []

    for item in matriculas:
        for i, bloque in enumerate(item["bloques"]):
            info = parsear_horario(bloque["horario_raw"])
            if info is None:
                continue

            bloques.append(
                {
                    "item_id": item["id"],
                    "curso": item["curso"],
                    "seccion": item["seccion"],
                    "sesion": item["sesion"],
                    "frecuencia": item["frecuencia"],
                    "categoria": item["categoria"],
                    "docente": item["docente"],
                    "ubicacion": bloque["ubicacion"],
                    "modalidad": bloque["modalidad"],
                    "horario_visible": bloque["horario_visible"],
                    "dia": info["dia"],
                    "inicio": info["inicio"],
                    "fin": info["fin"],
                    "subindex": i,
                }
            )

    return bloques


def calcular_lanes_y_conflictos(bloques):
    """
    Asigna carriles por día para que bloques con cruce
    se dibujen en paralelo y en rojo.
    """
    por_dia = {}
    for idx, b in enumerate(bloques):
        por_dia.setdefault(b["dia"], []).append(idx)

    for dia, indices in por_dia.items():
        # Grafo de traslape
        adj = {i: set() for i in indices}
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                a = bloques[indices[i]]
                b = bloques[indices[j]]
                if bloques_se_superponen(a, b):
                    adj[indices[i]].add(indices[j])
                    adj[indices[j]].add(indices[i])

        visitados = set()
        componentes = []

        for nodo in indices:
            if nodo in visitados:
                continue
            stack = [nodo]
            comp = []
            visitados.add(nodo)

            while stack:
                x = stack.pop()
                comp.append(x)
                for y in adj[x]:
                    if y not in visitados:
                        visitados.add(y)
                        stack.append(y)

            componentes.append(comp)

        # Carriles por componente
        for comp in componentes:
            comp_ordenada = sorted(
                comp,
                key=lambda i: (bloques[i]["inicio"], bloques[i]["fin"])
            )

            lanes_end = []
            lane_asignada = {}

            for i in comp_ordenada:
                inicio = bloques[i]["inicio"]
                colocado = False

                for lane_idx, fin_prev in enumerate(lanes_end):
                    if inicio >= fin_prev:
                        lanes_end[lane_idx] = bloques[i]["fin"]
                        lane_asignada[i] = lane_idx
                        colocado = True
                        break

                if not colocado:
                    lanes_end.append(bloques[i]["fin"])
                    lane_asignada[i] = len(lanes_end) - 1

            lane_count = len(lanes_end)

            for i in comp:
                bloques[i]["lane_idx"] = lane_asignada[i]
                bloques[i]["lane_count"] = lane_count
                bloques[i]["conflict"] = lane_count > 1

    return bloques


def construir_schedule_html(matriculas):
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"]
    horas = list(range(7, 23))

    left_w = 78
    day_w = 150
    header_h = 44
    row_h = 52

    total_w = left_w + day_w * 6
    total_h = header_h + row_h * len(horas)

    bloques = armar_bloques_render(matriculas)
    bloques = calcular_lanes_y_conflictos(bloques)

    partes = []
    partes.append('<div class="schedule-wrap">')
    partes.append(
        f'<div class="schedule-board" style="width:{total_w}px; height:{total_h}px;">'
    )

    # Esquina superior izquierda
    partes.append(
        f'<div class="schedule-header" style="left:0px; top:0px; width:{left_w}px; height:{header_h}px;"></div>'
    )

    # Cabeceras de días
    for i, dia in enumerate(dias):
        left = left_w + i * day_w
        partes.append(
            f'<div class="schedule-header" '
            f'style="left:{left}px; top:0px; width:{day_w}px; height:{header_h}px;">'
            f'{html.escape(dia)}'
            f'</div>'
        )

    # Filas y celdas de fondo
    for fila_idx, h in enumerate(horas):
        top = header_h + fila_idx * row_h

        partes.append(
            f'<div class="schedule-time" '
            f'style="left:0px; top:{top}px; width:{left_w}px; height:{row_h}px;">'
            f'{h:02d}-{h+1:02d}'
            f'</div>'
        )

        for col_idx in range(6):
            left = left_w + col_idx * day_w
            partes.append(
                f'<div class="schedule-cell" '
                f'style="left:{left}px; top:{top}px; width:{day_w}px; height:{row_h}px;"></div>'
            )

    # Bloques matriculados
    dia_a_col = {
        "Lunes": 0,
        "Martes": 1,
        "Miércoles": 2,
        "Jueves": 3,
        "Viernes": 4,
        "Sábado": 5,
    }

    for b in bloques:
        if b["dia"] not in dia_a_col:
            continue

        col_idx = dia_a_col[b["dia"]]
        base_left = left_w + col_idx * day_w

        top = header_h + (b["inicio"] - 7) * row_h + 4
        height = (b["fin"] - b["inicio"]) * row_h - 8

        lane_count = max(1, b.get("lane_count", 1))
        lane_idx = b.get("lane_idx", 0)

        gap = 6
        inner_w = day_w - 8
        ancho_lane = inner_w / lane_count
        left = base_left + 4 + lane_idx * ancho_lane + gap / 2
        width = ancho_lane - gap

        left = int(round(left))
        top = int(round(top))
        width = int(round(width))
        height = int(round(height))

        if b.get("conflict", False):
            bg = "rgba(255, 99, 99, 0.78)"
        else:
            bg = color_para_curso(b["curso"])

        curso_html = html.escape(b["curso"])
        sesion_html = html.escape(b["sesion"])
        sub_html = html.escape(b["frecuencia"] if b["frecuencia"] else b["ubicacion"])

        partes.append(
            f'<div class="schedule-block" '
            f'style="left:{left}px; top:{top}px; width:{width}px; height:{height}px; background:{bg};">'
            f'<div class="schedule-block-title">{curso_html}</div>'
            f'<div>{sesion_html}</div>'
            f'<div class="schedule-block-sub">{sub_html}</div>'
            f'</div>'
        )

    partes.append('</div>')
    partes.append('</div>')

    return "".join(partes)


def render_teoria_card(teoria: dict, curso: str, seccion: str):
    item_id = f"T|{curso}|{seccion}|{teoria['sesion']}|{teoria['docente']}"
    item = {
        "id": item_id,
        "categoria": "TEORIA",
        "curso": curso,
        "seccion": seccion,
        "sesion": teoria["sesion"],
        "docente": teoria["docente"],
        "frecuencia": teoria["frecuencia"],
        "bloques": teoria["bloques"],
    }

    with st.container(border=True):
        st.markdown(f"**{teoria['docente']}**")
        st.write(teoria["sesion"])

        for bloque in teoria["bloques"]:
            with st.container(border=True):
                st.write(bloque["modalidad"])
                st.write(bloque["horario_visible"])
                st.write(bloque["ubicacion"])

        st.write(f"Vacantes: {teoria['vacantes']}")

        if existe_item(item_id):
            st.button(
                "Quitar",
                key=f"quitar_{item_id}",
                use_container_width=True,
                on_click=quitar_item,
                args=(item_id,),
            )
        else:
            st.button(
                "Matrícula",
                key=f"matricular_{item_id}",
                use_container_width=True,
                on_click=matricular_item,
                args=(item,),
            )


def render_lab_card(row: pd.Series, curso: str, seccion: str):
    docente = limpiar_texto(row["Docente"])
    sesion = limpiar_texto(row["Sesión Grupo"])
    frecuencia = limpiar_texto(row["Frecuencia"])
    modalidad = limpiar_texto(row["Modalidad"])
    horario_raw = limpiar_texto(row["Horario"])
    horario_visible = formatear_horario_visible(horario_raw)
    ubicacion = limpiar_texto(row["Ubicación"])
    vacantes = limpiar_texto(row["Vacantes"])

    item_id = f"L|{curso}|{seccion}|{sesion}|{docente}|{horario_raw}|{frecuencia}"
    item = {
        "id": item_id,
        "categoria": "LAB",
        "curso": curso,
        "seccion": seccion,
        "sesion": sesion,
        "docente": docente,
        "frecuencia": frecuencia,
        "bloques": [
            {
                "modalidad": modalidad,
                "horario_raw": horario_raw,
                "horario_visible": horario_visible,
                "ubicacion": ubicacion,
            }
        ],
    }

    with st.container(border=True):
        st.markdown(f"**{docente}**")
        st.write(sesion)
        st.write(frecuencia)

        with st.container(border=True):
            st.write(modalidad)
            st.write(horario_visible)
            st.write(ubicacion)

        st.write(f"Vacantes: {vacantes}")

        if existe_item(item_id):
            st.button(
                "Quitar",
                key=f"quitar_{item_id}",
                use_container_width=True,
                on_click=quitar_item,
                args=(item_id,),
            )
        else:
            st.button(
                "Matrícula",
                key=f"matricular_{item_id}",
                use_container_width=True,
                on_click=matricular_item,
                args=(item,),
            )

# =========================================================
# CARGA DE DATOS
# =========================================================
try:
    df = cargar_datos(ARCHIVO_EXCEL)
except FileNotFoundError:
    st.error(f"No se encontró el archivo: {ARCHIVO_EXCEL}")
    st.stop()
except Exception as e:
    st.error(f"Error al cargar la base de datos: {e}")
    st.stop()

# =========================================================
# ESTADO
# =========================================================
if "curso_seleccionado" not in st.session_state:
    st.session_state["curso_seleccionado"] = None

if "matriculas" not in st.session_state:
    st.session_state["matriculas"] = []

if "mensaje" not in st.session_state:
    st.session_state["mensaje"] = ""

if "tipo_mensaje" not in st.session_state:
    st.session_state["tipo_mensaje"] = "success"

# =========================================================
# TÍTULO
# =========================================================
st.title("Consulta de Horarios")
st.write("Selecciona teoría o laboratorio y se pintará en el horario.")

if st.session_state["mensaje"]:
    if st.session_state["tipo_mensaje"] == "success":
        st.success(st.session_state["mensaje"])
    elif st.session_state["tipo_mensaje"] == "warning":
        st.warning(st.session_state["mensaje"])
    else:
        st.error(st.session_state["mensaje"])

# =========================================================
# CURSOS
# =========================================================
cursos = sorted([c for c in df["Curso"].unique() if limpiar_texto(c) != ""])

# =========================================================
# LAYOUT PRINCIPAL
# =========================================================
col_izq, col_der = st.columns([1.08, 2.25], gap="large")

with col_izq:
    with st.container(border=True):
        st.markdown('<div class="bloque-titulo">Cursos disponibles</div>', unsafe_allow_html=True)

        buscador = st.text_input(
            "Buscar curso",
            placeholder="Escribe parte del nombre del curso..."
        )

        if buscador.strip():
            cursos_filtrados = [c for c in cursos if buscador.lower() in c.lower()]
        else:
            cursos_filtrados = cursos

        st.write("Haz clic en un curso para ver sus secciones y grupos.")

        with st.container(height=320, border=True):
            for i, curso in enumerate(cursos_filtrados):
                st.button(
                    curso,
                    key=f"curso_{i}",
                    use_container_width=True,
                    on_click=seleccionar_curso,
                    args=(curso,),
                )

        curso_sel = st.session_state["curso_seleccionado"]

        if curso_sel:
            st.divider()
            st.markdown(f'<div class="bloque-titulo">{curso_sel}</div>', unsafe_allow_html=True)

            df_curso = df[df["Curso"] == curso_sel].copy()
            secciones = sorted(df_curso["Sección_fmt"].unique(), key=ordenar_seccion)

            for sec in secciones:
                df_sec = df_curso[df_curso["Sección_fmt"] == sec].copy()

                teorias = df_sec[~df_sec["Sesión Grupo"].apply(es_laboratorio)].copy()
                laboratorios = df_sec[df_sec["Sesión Grupo"].apply(es_laboratorio)].copy()

                teorias_agrupadas = agrupar_teorias(teorias)

                st.subheader(f"Sección {sec}")

                c1, c2 = st.columns(2)

                with c1:
                    st.markdown("**Secciones**")
                    if teorias_agrupadas:
                        for teoria in teorias_agrupadas:
                            render_teoria_card(teoria, curso_sel, sec)
                    else:
                        with st.container(border=True):
                            st.write("Sin teoría registrada")

                with c2:
                    st.markdown("**Grupos**")
                    if not laboratorios.empty:
                        for _, row in laboratorios.iterrows():
                            render_lab_card(row, curso_sel, sec)
                    else:
                        with st.container(border=True):
                            st.write("Sin grupos / laboratorios")

with col_der:
    with st.container(border=True):
        ctop1, ctop2 = st.columns([3, 1])
        with ctop1:
            st.subheader("Horario")
        with ctop2:
            st.button("Limpiar horario", use_container_width=True, on_click=limpiar_horario)

        schedule_html = construir_schedule_html(st.session_state["matriculas"])
        st.markdown(schedule_html, unsafe_allow_html=True)

        if st.session_state["matriculas"]:
            st.markdown("### Cursos matriculados")
            for item in st.session_state["matriculas"]:
                st.write(f"- {item['curso']} | {item['sesion']} | Sección {item['seccion']}")