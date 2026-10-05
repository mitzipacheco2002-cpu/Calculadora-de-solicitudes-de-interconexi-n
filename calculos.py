import io
import math
import matplotlib.pyplot as plt
import pandas as pd

# ==============================================================================
# 1. CATÁLOGOS Y TABLAS DE REFERENCIA
# ==============================================================================

VOLTAJES_SISTEMA = {
    "BAJA TENSION (BT)": {
        "Monofásico (1Φ - 2 hilos) (1F-2H)": [0.120, 0.127],
        "Bifásico (2Φ - 3 hilos) (1F-3H / 2F-3H)": [0.120, 0.127, 0.220, 0.240],
        "Trifásico (3Φ - 4 hilos) (3F-4H)": [0.220, 0.440, 0.480],
    },
    "Media tensión (MT)": {
        "Monofásico (1Φ - 2 hilos)": [7.62, 13.2],
        "Bifásico (2Φ - 3 hilos)": [13.2, 22.9],
        "Trifásico (3Φ - 4 hilos)": [13.8, 23.0, 34.5],
    },
}

CATALOGO_TRAFOS_MONOFASICOS = [5.0, 10.0, 15.0, 25.0, 37.5, 50.0, 75.0, 100.0]
CATALOGO_TRAFOS_TRIFASICOS = [
    15.0,
    30.0,
    45.0,
    75.0,
    112.5,
    150.0,
    225.0,
    300.0,
    500.0,
]

CATALOGO_CABLES_75C = {
    "14 AWG": [20, None],
    "12 AWG": [25, None],
    "10 AWG": [35, None],
    "8 AWG": [50, 40],
    "6 AWG": [65, 50],
    "4 AWG": [85, 65],
    "3 AWG": [100, 75],
    "2 AWG": [115, 90],
    "1 AWG": [130, 100],
    "1/0 AWG": [150, 120],
    "2/0 AWG": [175, 135],
    "3/0 AWG": [200, 155],
    "4/0 AWG": [230, 180],
    "250 kcmil": [255, 205],
    "300 kcmil": [285, 230],
    "350 kcmil": [310, 250],
    "400 kcmil": [335, 270],
    "500 kcmil": [380, 310],
}

DATOS_DE_SOLICITUD = {
    "BAJA TENSION(MENOR O IGUAL A 1 KV) (BT)": {
        "de_solicitud": "N/A (BT)",
        "tension_soporte_60hz": "2.5 kV",
    },
    "Clase 15 kV": {
        "de_solicitud": "95 kV BIL",
        "tension_soporte_60hz": "34 kV",
    },
    "Clase 18 y 25 kV": {
        "de_solicitud": "125 kV BIL",
        "tension_soporte_60hz": "40 kV",
    },
    "Clase 34.5 kV": {
        "de_solicitud": "150 kV BIL",
        "tension_soporte_60hz": "50 kV",
    },
}

# ==============================================================================
# 2. FUNCIONES DE CÁLCULO ELÉCTRICO Y EVALUACIÓN TÉCNICA
# ==============================================================================


def obtener_ampacidad(calibre, material):
    """Devuelve la ampacidad nominal en Amperes a 75 °C según NOM-001-SEDE."""
    datos = CATALOGO_CABLES_75C.get(calibre, [0, 0])
    return datos[0] if material == "Cobre" else (datos[1] if datos[1] else 0)


def sugerir_transformador(s_solicitada_kva, fases):
    """Sugiere la capacidad comercial de transformador inmediata superior."""
    catalogo = (
        CATALOGO_TRAFOS_MONOFASICOS
        if ("Monofásico" in fases or "Bifásico" in fases)
        else CATALOGO_TRAFOS_TRIFASICOS
    )
    for cap in catalogo:
        if cap >= s_solicitada_kva:
            return cap
    return catalogo[-1]


def sugerir_calibre_conductor(i_diseno, material):
    """Sugiere el calibre de conductor que soporta la corriente de diseño (1.25 * In)."""
    idx_mat = 0 if material == "Cobre" else 1
    for calibre, caps in CATALOGO_CABLES_75C.items():
        cap = caps[idx_mat]
        if cap is not None and cap >= i_diseno:
            return calibre
    return "500 kcmil (múltiples conductores por fase)"


def evaluar_solicitud_completa(
    rpu,
    solicitud,
    nivel_tension,
    fases,
    p_mw,
    fp,
    trafo_kva,
    v_linea_kv,
    calibre_cable,
    material_cable,
    clase_aislamiento,
):
    """Realiza el balance de potencias, corrientes y dictamen técnico de capacidad."""
    p_kw = p_mw * 1000.0
    s_solicitada_kva = p_kw / fp if fp > 0 else p_kw
    q_kvar = (s_solicitada_kva**2 - p_kw**2) ** 0.5 if s_solicitada_kva >= p_kw else 0.0

    # Corriente Nominal
    if "Monofásico (1Φ - 2 hilos)" in fases or "Monofásico (1Φ - 3 hilos)" in fases:
        i_nominal = (s_solicitada_kva * 1000.0) / (v_linea_kv * 1000.0)
    else:  # Trifásico
        i_nominal = (s_solicitada_kva * 1000.0) / ((3**0.5) * v_linea_kv * 1000.0)

    i_diseno = i_nominal * 1.25
    ampacidad_cable = obtener_ampacidad(calibre_cable, material_cable)

    # Porcentajes de utilización
    pct_trafo_100 = round((s_solicitada_kva / trafo_kva) * 100.0, 2)
    pct_trafo_80 = round((s_solicitada_kva / (trafo_kva * 0.80)) * 100.0, 2)

    pct_cond_100 = round((i_diseno / ampacidad_cable) * 100.0, 2) if ampacidad_cable > 0 else 0.0
    pct_cond_80 = round((i_diseno / (ampacidad_cable * 0.80)) * 100.0, 2) if ampacidad_cable > 0 else 0.0

    trafo_soporta = s_solicitada_kva <= trafo_kva
    cable_soporta = i_diseno <= ampacidad_cable

    return {
        "rpu": rpu,
        "solicitud": solicitud,
        "nivel_tension": nivel_tension,
        "fases": fases,
        "p_mw": p_mw,
        "p_kw": round(p_kw, 2),
        "fp": fp,
        "s_solicitada_kva": round(s_solicitada_kva, 2),
        "q_kvar": round(q_kvar, 2),
        "v_linea_kv": v_linea_kv,
        "trafo_kva": trafo_kva,
        "i_nominal": round(i_nominal, 2),
        "i_diseno": round(i_diseno, 2),
        "calibre_cable": calibre_cable,
        "material_cable": material_cable,
        "ampacidad_cable": ampacidad_cable,
        "clase_aislamiento": clase_aislamiento,
        "flujo_inverso_kw": round(p_kw, 2),
        "pct_trafo_100": pct_trafo_100,
        "pct_trafo_80": pct_trafo_80,
        "pct_cond_100": pct_cond_100,
        "pct_cond_80": pct_cond_80,
        "trafo_soporta": trafo_soporta,
        "cable_soporta": cable_soporta,
        "trafo_sugerido_kva": sugerir_transformador(s_solicitada_kva, fases),
        "calibre_sugerido": sugerir_calibre_conductor(i_diseno, material_cable),
    }


def evaluar_criterios_normativos_cfe(
    nivel_tension,
    fases,
    p_kw,
    s_solicitada_kva,
    asociada_centro_carga,
    carga_contratada_kw,
    fases_contratadas_coinciden,
    pct_trafo_100,
    pct_cond_100,
):
    """Aplica la normativa CFE / CRE para evaluar si se requiere Opinión Técnica o Estudio."""
    requiere_opinion = False
    motivos_opinion = []

    requiere_estudio = False
    motivos_estudio = []

    if "Media" in nivel_tension:
        if p_kw > 500.0:
            requiere_estudio = True
            motivos_estudio.append("Capacidad mayor a 500 kW en Media Tensión.")
        else:
            requiere_opinion = True
            motivos_opinion.append("Interconexión en Media Tensión (<= 500 kW).")
    else:
        if p_kw > 50.0:
            requiere_estudio = True
            motivos_estudio.append("Capacidad mayor a 50 kW en Baja Tensión excede límite simplificado.")

        if asociada_centro_carga and p_kw > carga_contratada_kw:
            requiere_opinion = True
            motivos_opinion.append(f"La capacidad de generación ({p_kw} kW) supera la carga contratada ({carga_contratada_kw} kW).")

        if asociada_centro_carga and not fases_contratadas_coinciden:
            requiere_opinion = True
            motivos_opinion.append("El esquema de fases del suministro no coincide con la interconexión.")

    if pct_trafo_100 > 100.0:
        requiere_opinion = True
        motivos_opinion.append(f"Sobrecarga en transformador detectada ({pct_trafo_100}%).")

    if pct_cond_100 > 100.0:
        requiere_opinion = True
        motivos_opinion.append(f"Sobrecarga en conductor detectada ({pct_cond_100}%).")

    return {
        "requiere_opinion": requiere_opinion,
        "motivos_opinion": motivos_opinion,
        "requiere_estudio": requiere_estudio,
        "motivos_estudio": motivos_estudio,
    }


# ==============================================================================
# 3. GENERACIÓN DE GRÁFICAS (MATPLOTLIB)
# ==============================================================================


def generar_grafica_triangulo_potencias(p_kw, q_kvar, s_kva, fp):
    """Genera la gráfica vectorial del Triángulo de Potencias (P, Q, S)."""
    fig, ax = plt.subplots(figsize=(6, 3.8))

    # Coordenadas del triángulo: (0,0) -> (P, 0) -> (P, Q)
    x = [0, p_kw, p_kw, 0]
    y = [0, 0, q_kvar, 0]

    # Dibujar los vectores principales
    ax.plot([0, p_kw], [0, 0], color="#27ae60", linewidth=3, label=f"P (Activa): {p_kw:.2f} kW")
    ax.plot([p_kw, p_kw], [0, q_kvar], color="#e67e22", linewidth=3, label=f"Q (Reactiva): {q_kvar:.2f} kvar")
    ax.plot([0, p_kw], [0, q_kvar], color="#2980b9", linewidth=3, label=f"S (Aparente): {s_kva:.2f} kVA")

    # Relleno sombreado dentro del triángulo
    ax.fill(x, y, color="#3498db", alpha=0.15)

    # Indicación del Ángulo theta (FP = cos(theta))
    theta_rad = math.acos(fp) if 0 <= fp <= 1 else 0
    theta_deg = math.degrees(theta_rad)

    # Añadir texto explicativo
    ax.text(p_kw / 2, -max(q_kvar, 1) * 0.12, f"P = {p_kw:.2f} kW", ha="center", va="top", fontsize=9, fontweight="bold", color="#27ae60")
    ax.text(p_kw * 1.03, q_kvar / 2, f"Q = {q_kvar:.2f} kvar", ha="left", va="center", fontsize=9, fontweight="bold", color="#e67e22")
    ax.text(p_kw / 2, q_kvar / 2 * 1.1, f"S = {s_kva:.2f} kVA\n(FP = {fp:.2f}, θ = {theta_deg:.1f}°)", ha="right", va="bottom", fontsize=8, fontweight="bold", color="#2980b9")

    # Estética de ejes
    ax.set_title("Triángulo de Potencias Solicitado (P, Q, S)", fontsize=10, fontweight="bold", pad=10)
    ax.set_xlabel("Potencia Activa (kW)", fontsize=9, fontweight="bold")
    ax.set_ylabel("Potencia Reactiva (kvar)", fontsize=9, fontweight="bold")

    # Ajuste dinámico de márgenes
    ax.set_xlim(-p_kw * 0.05, p_kw * 1.25)
    ax.set_ylim(-max(q_kvar, 1) * 0.2, max(q_kvar, 1) * 1.25 if q_kvar > 0 else 10)
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.legend(loc="upper left", fontsize=8)

    plt.tight_layout()
    return fig


import io
import matplotlib.pyplot as plt


import io
import matplotlib.pyplot as plt


def generar_grafica_porcentaje_utilizacion(res):
    """Genera la gráfica de 4 barras: 'Utilización del Sistema'."""
    # Extraer utilidades base al 100%
    pct_trafo_100 = res.get("pct_trafo_100", 0)
    pct_cond_100 = res.get("pct_cond_100", 0)

    # Calcular porcentajes al 80% de capacidad
    pct_trafo_80 = pct_trafo_100 * 0.8
    pct_cond_80 = pct_cond_100 * 0.8

    categorias = [
        "Trafo (100%)",
        "Trafo (80%)",
        "Cable (100%)",
        "Cable (80%)",
    ]
    valores = [pct_trafo_100, pct_trafo_80, pct_cond_100, pct_cond_80]

    # Colores: Verde (#5cb85c / #58b957) si ok, Rojo (#d9534f) si supera el 100%
    colores = ["#d9534f" if v > 100 else "#58b957" for v in valores]

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(categorias, valores, color=colores, width=0.45)

    # Formato de ejes y títulos idénticos
    ax.set_title("Utilización del Sistema", fontsize=10, pad=8)
    ax.set_ylabel("% utilizacion", fontsize=9)
    ax.set_xlabel("Utilización de Equipos", fontsize=10, labelpad=10)

    # Línea punteada en el 100%
    ax.axhline(100, color="black", linestyle="--", linewidth=1)

    # Formato de malla y márgenes superiores para que no se corten los textos
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    max_val = max(valores) if valores else 100
    ax.set_ylim(0, max_val * 1.18)

    # Etiquetas de porcentaje sobre cada barra
    for bar in bars:
        yval = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            yval + (max_val * 0.02),
            f"{yval:.2f}%",
            ha="center",
            va="bottom",
            fontsize=7.5,
            fontweight="bold",
        )

    plt.tight_layout()
    return fig


def figura_a_bytes(fig):
    """Convierte la figura Matplotlib a bytes (PNG) para incluir en reportes."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    return buf.getvalue()

def generar_grafica_flujo_inverso(trafo_kva, potencia_previa_kva, potencia_nueva_kva):
    """Genera gráfica comparativa de la capacidad del transformador vs potencia acumulada en kVA."""
    fig, ax = plt.subplots(figsize=(6, 3.8))

    potencia_total_kva = potencia_previa_kva + potencia_nueva_kva

    categorias = ["Previa Conectada", "Nueva Solicitud", "Total Acumulado", "Capacidad Trafo"]
    valores = [potencia_previa_kva, potencia_nueva_kva, potencia_total_kva, trafo_kva]

    color_total = "#e74c3c" if potencia_total_kva > trafo_kva else "#27ae60"
    colores = ["#3498db", "#2ecc71", color_total, "#34495e"]

    bars = ax.bar(categorias, valores, color=colores, width=0.5)
    ax.set_ylabel("Potencia Aparente (kVA)", fontsize=9, fontweight="bold")
    ax.set_title("Flujo Inverso Acumulado en Transformador (kVA)", fontsize=10, fontweight="bold", pad=10)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{height:.2f} kVA",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
        )

    ax.axhline(
        y=trafo_kva,
        color="#c0392b",
        linestyle="--",
        linewidth=1.2,
        label=f"Límite Trafo ({trafo_kva} kVA)",
    )
    ax.legend(loc="upper left", fontsize=8)

    plt.tight_layout()
    return fig


def _generar_grafica_utilizacion(nombre, valor, capacidad, unidad):
    """Genera una gráfica de utilización de un equipo respecto a su capacidad."""
    porcentaje = valor / capacidad * 100 if capacidad > 0 else 0
    color = "#d9534f" if porcentaje > 100 else "#5cb85c"

    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar([nombre], [porcentaje], color=color, width=0.5)
    ax.axhline(100, color="black", linestyle="--", linewidth=1)
    ax.set_ylabel("% de utilización", fontsize=9)
    ax.set_title(f"Utilización de {nombre}", fontsize=10, pad=10)
    ax.set_ylim(0, max(110, porcentaje * 1.15))
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.text(0, porcentaje + max(2, porcentaje * 0.02), f"{porcentaje:.2f}%", ha="center", fontsize=8)
    plt.tight_layout()
    return fig


def generar_grafica_utilizacion_trafo(s_solicitada_kva, trafo_kva):
    return _generar_grafica_utilizacion("Transformador", s_solicitada_kva, trafo_kva, "kVA")


def generar_grafica_utilizacion_conductor(i_diseno, ampacidad_cable):
    return _generar_grafica_utilizacion("Conductor", i_diseno, ampacidad_cable, "A")


# ==============================================================================
# 4. EXPORTACIÓN A EXCEL (.XLSX)
# ==============================================================================


def generar_excel(res):
    """Genera un reporte técnico estructurado en formato Excel usando BytesIO."""
    output = io.BytesIO()

    datos_resumen = {
        "Parámetro": [
            "RPU / Registro de Usuario",
            "Número de Solicitud CFE",
            "Nivel de Tensión",
            "Esquema de Fases",
            "Tensión Nominal (kV)",
            "Potencia Activa Solicitada (P en kW)",
            "Factor de Potencia (FP)",
            "Potencia Reactiva Solicitada (Q en kvar)",
            "Potencia Aparente Solicitada (S en kVA)",
            "Corriente Nominal In (A)",
            "Corriente de Diseño Id (1.25 In) (A)",
            "Capacidad Transformador Actual (kVA)",
            "Utilización Transformador vs 100% (%)",
            "Utilización Transformador vs 80% (%)",
            "Sugerencia Transformador (kVA)",
            "Calibre Conductor Seleccionado",
            "Material del Conductor",
            "Ampacidad Conductor (A)",
            "Utilización Conductor vs 100% (%)",
            "Utilización Conductor vs 80% (%)",
            "Sugerencia Conductor",
            "Clase de Aislamiento",
            "Evaluación Flujo Inverso Realizada",
            "Potencia FV Previa en Trafo (kVA)",
            "Potencia Acumulada Total en Trafo (kVA)",
        ],
        "Valor": [
            res.get("rpu", ""),
            res.get("solicitud", ""),
            res.get("nivel_tension", ""),
            res.get("fases", ""),
            res.get("v_linea_kv", 0.0),
            res.get("p_kw", 0.0),
            res.get("fp", 0.0),
            res.get("q_kvar", 0.0),
            res.get("s_solicitada_kva", 0.0),
            res.get("i_nominal", 0.0),
            res.get("i_diseno", 0.0),
            res.get("trafo_kva", 0.0),
            f"{res.get('pct_trafo_100', 0.0)}%",
            f"{res.get('pct_trafo_80', 0.0)}%",
            res.get("trafo_sugerido_kva", 0.0),
            res.get("calibre_cable", ""),
            res.get("material_cable", ""),
            res.get("ampacidad_cable", 0.0),
            f"{res.get('pct_cond_100', 0.0)}%",
            f"{res.get('pct_cond_80', 0.0)}%",
            res.get("calibre_sugerido", ""),
            res.get("clase_aislamiento", ""),
            "SÍ" if res.get("flujo_inverso_evaluado", False) else "NO",
            res.get("fv_conectada_kva", 0.0),
            res.get("potencia_total_kva", res.get("s_solicitada_kva", 0.0)),
        ],
    }

    df = pd.DataFrame(datos_resumen)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Estudio_Interconexion", index=False)

    output.seek(0)
    return output.getvalue()


# ==============================================================================
# 5. EXPORTACIÓN A PDF (.PDF)
# ==============================================================================

import io
import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# --- 1. FUNCIÓN: TRIÁNGULO DE POTENCIAS ---
def generar_grafica_triangulo(res):
    p = res.get("p_kw", 15.0)
    q = res.get("q_kvar", 7.26)
    s = res.get("s_solicitada_kva", 16.67)

    fig, ax = plt.subplots(figsize=(6, 2.8))
    # Dibuja las lineas del triángulo
    ax.plot([0, p], [0, 0], color="#27ae60", linewidth=3, label=f"P (Activa): {p:.2f} kW")
    ax.plot([p, p], [0, q], color="#e67e22", linewidth=3, label=f"Q (Reactiva): {q:.2f} kvar")
    ax.plot([0, p], [0, q], color="#2980b9", linewidth=3, label=f"S (Aparente): {s:.2f} kVA")
    ax.fill_between([0, p], [0, q], color="#2980b9", alpha=0.1)

    ax.set_title("Triángulo de Potencias Solicitado (P, Q, S)", fontsize=10, fontweight="bold")
    ax.set_xlabel("Potencia Activa (kW)", fontsize=9, fontweight="bold")
    ax.set_ylabel("Potencia Reactiva (kvar)", fontsize=9, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="upper left", fontsize=8)

    # Etiquetas flotantes
    ax.text(p/2, -q*0.15, f"P = {p:.2f} kW", color="#27ae60", fontweight="bold", ha="center", fontsize=8)
    ax.text(p*1.02, q/2, f"Q = {q:.2f} kvar", color="#e67e22", fontweight="bold", va="center", fontsize=8)
    ax.text(p/2, q/2 + q*0.1, f"S = {s:.2f} kVA", color="#2980b9", fontweight="bold", ha="center", fontsize=8)

    plt.tight_layout()
    return fig

# --- 3. FUNCIÓN: UTILIZACIÓN DEL SISTEMA (4 BARRAS) ---
def generar_grafica_porcentaje_utilizacion(res):
    pct_trafo_100 = res.get("pct_trafo_100", 111.11)
    pct_cond_100 = res.get("pct_cond_100", 277.78)

    pct_trafo_80 = pct_trafo_100 * 0.8
    pct_cond_80 = pct_cond_100 * 0.8

    categorias = ["Trafo (100%)", "Trafo (80%)", "Cable (100%)", "Cable (80%)"]
    valores = [pct_trafo_100, pct_trafo_80, pct_cond_100, pct_cond_80]
    colores = ["#d9534f" if v > 100 else "#58b957" for v in valores]

    fig, ax = plt.subplots(figsize=(6, 3.2))
    bars = ax.bar(categorias, valores, color=colores, width=0.45)

    ax.set_title("Utilización del Sistema", fontsize=10, fontweight="bold")
    ax.set_ylabel("% utilizacion", fontsize=9, fontweight="bold")
    ax.set_xlabel("Utilización de Equipos", fontsize=9, fontweight="bold")

    ax.axhline(100, color="black", linestyle="--", linewidth=1)
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    max_val = max(valores) if valores and max(valores) > 0 else 100
    ax.set_ylim(0, max_val * 1.25)

    for bar in bars:
        yval = bar.get_height()
        # Ajuste de posición si choca con la línea de 100%
        if 85 <= yval <= 105:
            text_y = yval - (max_val * 0.08)
            va_align = "top"
        else:
            text_y = yval + (max_val * 0.02)
            va_align = "bottom"

        ax.text(
            bar.get_x() + bar.get_width() / 2,
            text_y,
            f"{yval:.2f}%",
            ha="center",
            va=va_align,
            fontsize=8,
            fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85)
        )

    plt.tight_layout()
    return fig

# --- GENERADOR DEL PDF COMPLETO ---
def generar_pdf(res, normativa="NOM-001-SEDE"):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("HeaderTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=12, leading=14, alignment=1)
    cell_style = ParagraphStyle("CellText", parent=styles["Normal"], fontName="Helvetica", fontSize=7, leading=8)
    cell_bold = ParagraphStyle("CellBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=7, leading=8)

    # Título y Tablas
    story.append(Paragraph("<b>REPORTE DE ESTUDIO DE INTERCONEXIÓN Y FLUJOS DE POTENCIA</b>", title_style))
    story.append(Spacer(1, 8))

    data_t1 = [
        ["Componente", "Capacidad Actual", "Dictamen Técnico", "Recomendación"],
        ["Transformador", f"{res.get('trafo_kva', 15.0)} kVA", res.get("dictamen_trafo", "RECHAZADO"), res.get("rec_trafo", "Cambiar a 25.0 kVA")],
        ["Conductor", res.get("cable_info", "8 AWG"), res.get("dictamen_cond", "NO APTO"), res.get("rec_cond", "Sin cambio")]
    ]
    t1 = Table(data_t1, colWidths=[130, 130, 140, 140])
    t1.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2C2C2C")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#A0A0A0")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(t1)
    story.append(Spacer(1, 6))

    data_t2 = [
        [Paragraph("RPU / Registro:", cell_bold), Paragraph(str(res.get("rpu", "123456789012")), cell_style), Paragraph("No. Solicitud:", cell_bold), Paragraph(str(res.get("solicitud", "SOL-2026-099")), cell_style)],
        [Paragraph("Nivel Tensión:", cell_bold), Paragraph(str(res.get("nivel_tension", "BAJA TENSIÓN (BT)")), cell_style), Paragraph("Esquema Fases:", cell_bold), Paragraph(str(res.get("esquema_fases", "Monofásico 2 hilos (1F-2H)")), cell_style)],
        [Paragraph("Potencia Activa (P):", cell_bold), Paragraph(f"{res.get('p_kw', 15.0):.1f} kW", cell_style), Paragraph("Potencia Reactiva (Q):", cell_bold), Paragraph(f"{res.get('q_kvar', 7.26):.2f} kVAR", cell_style)],
        [Paragraph("Potencia Aparente (S):", cell_bold), Paragraph(f"{res.get('s_solicitada_kva', 16.67):.2f} kVA", cell_style), Paragraph("Flujo Inverso Red:", cell_bold), Paragraph(f"{res.get('flujo_inverso_kw', 12.3):.1f} kW", cell_style)],
        [Paragraph("Corriente Nominal (In):", cell_bold), Paragraph(f"{res.get('i_nom', 131.23):.2f} A", cell_style), Paragraph("Corriente Diseño (1.25):", cell_bold), Paragraph(f"{res.get('i_diseno', 173.61):.2f} A", cell_style)],
    ]
    t2 = Table(data_t2, colWidths=[120, 150, 120, 150])
    t2.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#CCCCCC")),
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#FAFAFA")),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("TOPPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(t2)
    story.append(Spacer(1, 6))

    data_t3 = [
        ["Trámite / Requerimiento", "Resultado", "Rubro / Criterio Aplicado"],
        ["Opinión Técnica (CFE)", res.get("opinion_tec", "REQUIERE"), Paragraph("- Criterio I (BT): Generación Monofásica mayor a 5 kW.<br/>- Criterio II: Capacidad de generación supera la carga contratada.", cell_style)],
        ["Estudio de Interconexión", res.get("estudio_inter", "REQUIERE"), Paragraph("- Criterio I (BT): La capacidad agregada excede el 80% del trafo.<br/>- Criterio II (BT): La corriente calculada excede el 80% del conductor.", cell_style)],
    ]
    t3 = Table(data_t3, colWidths=[150, 100, 290])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1F618D")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ALIGN", (0,0), (1,-1), "CENTER"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#A0A0A0")),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("TOPPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(t3)
    story.append(Spacer(1, 8))

    # CONVERTIDOR DE MATPLOTLIB A IMAGEN REPORTLAB
    def fig_a_img(fig, width=350, height=130):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        img = Image(buf, width=width, height=height)
        img.hAlign = "CENTER"
        return img

    # --- GENERAR E INSERTA LAS 3 GRÁFICAS DIRECTAMENTE ---
    
    # 1. Triángulo de Potencias
    fig_tri = generar_grafica_triangulo(res)
    story.append(fig_a_img(fig_tri))
    story.append(Spacer(1, 4))


    # 3. Utilización del Sistema (4 barras)
    fig_pct = generar_grafica_porcentaje_utilizacion(res)
    story.append(fig_a_img(fig_pct))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()