import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Voltajes nominales según nivel de tensión
VOLTAJES_SISTEMA = {
    "BAJA TENSION (BT)": {
        "Monofásico (1Φ - 2 hilos)": [0.127, 0.220],
        "Bifásico (2Φ - 3 hilos)": [0.127, 0.220],
        "Trifásico (3Φ - 4 hilos)": [0.220, 0.440, 0.480],
    },
    "Media tensión (MT)": {
        "Monofásico (1Φ - 2 hilos)": [7.62, 13.2],
        "Bifásico (2Φ - 3 hilos)": [13.2, 22.9],
        "Trifásico (3Φ - 4 hilos)": [13.8, 23.0, 34.5],
    },
}

CATALOGO_TRAFOS_MONOFASICOS = [
    5.0,
    10.0,
    15.0,
    25.0,
    37.5,
    50.0,
    75.0,
    100.0,
    167.0,
]

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
    750.0,
    1000.0,
    1500.0,
    2000.0,
    2500.0,
]

DATOS_DE_SOLICITUD = {
    "BAJA TENSION(MENOR O IGUAL A 1 KV) (BT)": {
        "Tensión nominal": "0.127-0.480 kV",
        "de_solicitud": "10 kV",
        "tension_soporte_60hz": "2.5 kV (1 min)",
    },
    "Clase 15 kV": {
        "tension_nominal": "13.8 kV / 15 kV",
        "de_solicitud": "95 kV",
        "tension_soporte_60hz": "34 kV (1 min)",
    },
    "Clase 18 y 25 kV": {
        "tension_nominal": "22.9 kV / 23 kV / 25 kV",
        "de_solicitud": "150 kV",
        "tension_soporte_60hz": "50 kV (1 min)",
    },
    "Clase 34.5 kV": {
        "tension_nominal": "34.5 kV",
        "de_solicitud": "200 kV",
        "tension_soporte_60hz": "70 kV (1 min)",
    },
}

# Tabla de Ampacidad NOM-001-SEDE-2012 75°C (COBRE, ALUMINIO)
CATALOGO_CABLES_75C = {
    "18 AWG": [7, None],
    "16 AWG": [10, None],
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
    "600 kcmil": [420, 340],
    "700 kcmil": [460, 375],
    "750 kcmil": [475, 385],
    "800 kcmil": [490, 395],
    "900 kcmil": [520, 425],
    "1000 kcmil": [545, 445],
}


def evaluar_criterios_normativos_cfe(
    nivel_tension: str,
    fases: str,
    p_kw: float,
    s_solicitada_kva: float,
    asociada_centro_carga: bool,
    carga_contratada_kw: float,
    fases_contratadas_coinciden: bool,
    pct_trafo_100: float,
    pct_cond_100: float,
):
  es_bt = "BAJA" in nivel_tension.upper() or "BT" in nivel_tension.upper()
  motivos_opinion = []
  motivos_estudio = []

  if es_bt:
    if "Monofásico" in fases and p_kw > 5.0:
      motivos_opinion.append(
          "Criterio I (BT): Generación en Monofásico (1F-2H) es mayor a 5 kW"
          f" ({p_kw:.2f} kW)."
      )
    elif ("Bifásico" in fases or "Trifásico" in fases) and p_kw > 10.0:
      motivos_opinion.append(
          "Criterio I (BT): Generación en Bifásico/Trifásico es mayor a 10 kW"
          f" ({p_kw:.2f} kW)."
      )

  capacidad_generacion_compared = max(p_kw, s_solicitada_kva)
  if asociada_centro_carga and (
      p_kw > carga_contratada_kw or s_solicitada_kva > carga_contratada_kw
  ):
    motivos_opinion.append(
        "Criterio II: La capacidad de generación "
        f"({capacidad_generacion_compared:.2f} kW/kVA) supera la carga contratada del suministro existente ({carga_contratada_kw:.2f} kW)."
    )

  if asociada_centro_carga and not fases_contratadas_coinciden:
    motivos_opinion.append(
        "Criterio III: No coincide el número de fases entre el punto de"
        " interconexión y el contrato de suministro existente."
    )

  if not es_bt and not asociada_centro_carga:
    motivos_opinion.append(
        "Criterio IV: Central en Media Tensión (MT1/MT2) no asociada a un"
        " Centro de Carga."
    )

  requiere_opinion = len(motivos_opinion) > 0

  if es_bt:
    if pct_trafo_100 > 80.0:
      motivos_estudio.append(
          "Criterio I (BT): La capacidad agregada excede el 80% de la capacidad"
          f" del transformador del circuito ({pct_trafo_100:.1f}%)."
      )
    if pct_cond_100 > 80.0:
      motivos_estudio.append(
          "Criterio I (BT): La corriente calculada excede el 80% de la"
          f" ampacidad nominal del conductor ({pct_cond_100:.1f}%)."
      )
  else:
    if p_kw > carga_contratada_kw or s_solicitada_kva > carga_contratada_kw:
      motivos_estudio.append(
          "Criterio II (MT): La capacidad de la Central Eléctrica "
          f"({max(p_kw, s_solicitada_kva):.2f} kW/kVA) supera la carga contratada existente ({carga_contratada_kw:.2f} kW)."
      )

  requiere_estudio = len(motivos_estudio) > 0

  return {
      "requiere_opinion": requiere_opinion,
      "motivos_opinion": motivos_opinion,
      "requiere_estudio": requiere_estudio,
      "motivos_estudio": motivos_estudio,
  }


def obtener_ampacidad(calibre: str, material: str = "Cobre") -> int:
  datos = CATALOGO_CABLES_75C.get(calibre)
  if not datos:
    return 0
  idx = 0 if material.strip().capitalize() == "Cobre" else 1
  amp = datos[idx]
  if amp is None:
    raise ValueError(
        f"El calibre {calibre} no está disponible en Aluminio (requiere mín."
        " CATALOGO_CABLES_75C AWG)."
    )
  return amp


def calcular_corriente(s_kva: float, v_kv: float, fases: str) -> float:
  if v_kv <= 0:
    return 0.0
  v_volts = v_kv * 1000.0

  if "Monofásico" in fases:
    return (s_kva * 1000.0) / v_volts
  elif "Bifásico" in fases:
    return (s_kva * 1000.0) / (2.0 * v_volts)
  elif "Trifásico" in fases:
    return (s_kva * 1000.0) / (np.sqrt(3) * v_volts)
  return 0.0


def evaluar_solicitud_completa(
    rpu: str,
    solicitud: str,
    nivel_tension: str,
    fases: str,
    p_mw: float,
    fp: float,
    trafo_kva: float,
    v_linea_kv: float,
    calibre_cable: str,
    material_cable: str,
    clase_aislamiento: str,
):
  p_kw = p_mw * 1000.0
  s_solicitada_kva = p_kw / fp if fp > 0 else 0.0
  q_kvar = np.sqrt(max(0.0, s_solicitada_kva**2 - p_kw**2))

  i_calculada = calcular_corriente(s_solicitada_kva, v_linea_kv, fases)
  i_nominal = i_calculada
  i_diseno = i_nominal * 1.25

  ampacidad_cable = obtener_ampacidad(calibre_cable, material_cable)

  info_nba = DATOS_DE_SOLICITUD.get(
      clase_aislamiento,
      {
          "de_solicitud": "N/A",
          "tension_soporte_60hz": "N/A",
          "tension_nominal": "N/A",
      },
  )

  trafo_kw_100 = trafo_kva * fp
  trafo_kva_80 = trafo_kva * 0.80

  pct_trafo_100 = (
      (s_solicitada_kva / trafo_kva) * 100.0 if trafo_kva > 0 else 0.0
  )
  pct_trafo_80 = (
      (s_solicitada_kva * 0.80 / trafo_kva) * 100.0 if trafo_kva > 0 else 0.0
  )

  disp_trafo_kva_100 = max(0.0, trafo_kva - s_solicitada_kva)
  disp_trafo_kw_100 = max(0.0, trafo_kw_100 - p_kw)

  pct_cond_100 = (
      (i_diseno / ampacidad_cable) * 100.0 if ampacidad_cable > 0 else 0.0
  )
  pct_cond_80 = (
      (i_diseno / (ampacidad_cable )) * 0.80*100.0
      if ampacidad_cable > 0
      else 0.0
  )

  cable_soporta = ampacidad_cable >= i_diseno
  trafo_soporta = s_solicitada_kva <= trafo_kva

  trafo_sugerido_kva = trafo_kva
  if not trafo_soporta:
    cat = (
        CATALOGO_TRAFOS_MONOFASICOS
        if ("Monofásico" in fases or "Bifásico" in fases)
        else CATALOGO_TRAFOS_TRIFASICOS
    )
    for t_cap in cat:
      if t_cap >= s_solicitada_kva:
        trafo_sugerido_kva = t_cap
        break
    if trafo_sugerido_kva < s_solicitada_kva:
      trafo_sugerido_kva = cat[-1]

  calibre_sugerido = calibre_cable
  if not cable_soporta:
    for cal, amps in CATALOGO_CABLES_75C.items():
      amp_val = amps[0] if material_cable == "Cobre" else amps[1]
      if amp_val and amp_val >= i_diseno:
        calibre_sugerido = cal
        break

  carga_local_estimada_kw = trafo_kw_100 * 0.20
  flujo_inverso_kw = max(0.0, p_kw - carga_local_estimada_kw)

  return {
      "rpu": rpu,
      "solicitud": solicitud,
      "nivel_tension": nivel_tension,
      "fases": fases,
      "p_kw": round(p_kw, 2),
      "q_kvar": round(q_kvar, 2),
      "s_solicitada_kva": round(s_solicitada_kva, 2),
      "i_calculada": round(i_calculada, 2),
      "i_nominal": round(i_nominal, 2),
      "i_diseno": round(i_diseno, 2),
      "v_linea_kv": v_linea_kv,
      "fp": fp,
      "carga_local_kw": round(carga_local_estimada_kw, 2),
      "flujo_inverso_kw": round(flujo_inverso_kw, 2),
      "trafo_kva": trafo_kva,
      "pct_trafo_100": round(pct_trafo_100, 2),
      "pct_trafo_80": round(pct_trafo_80, 2),
      "disp_trafo_kva_100": round(disp_trafo_kva_100, 2),
      "disp_trafo_kw_100": round(disp_trafo_kw_100, 2),
      "calibre_cable": calibre_cable,
      "material_cable": material_cable,
      "ampacidad_cable": ampacidad_cable,
      "pct_cond_100": round(pct_cond_100, 2),
      "pct_cond_80": round(pct_cond_80, 2),
      "clase_aislamiento": clase_aislamiento,
      "de_solicitud": info_nba.get("de_solicitud", "N/A"),
      "tension_soporte_60hz": info_nba.get("tension_soporte_60hz", "N/A"),
      "trafo_soporta": trafo_soporta,
      "cable_soporta": cable_soporta,
      "trafo_sugerido_kva": trafo_sugerido_kva,
      "calibre_sugerido": calibre_sugerido,
  }


def generar_grafica_utilizacion(res):
  fig, ax = plt.subplots(figsize=(8, 4))
  elementos = ["Trafo (100%)", "Trafo (80%)", "Cable (100%)", "Cable (80%)"]
  porcentajes = [
      res["pct_trafo_100"],
      res["pct_trafo_80"],
      res["pct_cond_100"],
      res["pct_cond_80"],
  ]
  colores = ["#d9534f" if p > 100 else "#5cb85c" for p in porcentajes]
  bars = ax.bar(elementos, porcentajes, color=colores, width=0.45)
  ax.axhline(100, color="black", linestyle="--", linewidth=1)
  ax.set_ylabel("% utilizacion")
  ax.set_title("Utilización del Sistema")
  ax.set_ylim(0, max(max(porcentajes) + 20, 120))
  for bar in bars:
    yval = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2.0,
        yval + 2,
        f"{yval}%",
        ha="center",
        va="bottom",
        fontsize=8,
        fontweight="bold",
    )
  plt.tight_layout()
  buf = io.BytesIO()
  plt.savefig(buf, format="png", dpi=150)
  plt.close(fig)
  buf.seek(0)
  return buf


def generar_grafica_potencias(res):
  fig, ax = plt.subplots(figsize=(6, 3))
  categorias = ["Activa (P)", "Reactiva (Q)", "Aparente (S)"]
  valores = [res["p_kw"], res["q_kvar"], res["s_solicitada_kva"]]
  unidades = ["kW", "kVAR", "kVA"]
  colores = ["#1f77b4", "#d423ae", "#47f247"]

  bars = ax.bar(categorias, valores, color=colores, width=0.45)
  ax.set_ylabel("Valor (kW / kVAR / kVA)")
  ax.set_title("Triángulo de Potencias")
  ax.set_ylim(0, max(valores) * 1.25 if max(valores) > 0 else 10)

  for bar, u in zip(bars, unidades):
    yval = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2.0,
        yval + (max(valores) * 0.03 if max(valores) > 0 else 0.2),
        f"{yval} {u}",
        ha="center",
        va="bottom",
        fontsize=8,
        fontweight="bold",
    )

  plt.tight_layout()
  buf = io.BytesIO()
  plt.savefig(buf, format="png", dpi=150)
  plt.close(fig)
  buf.seek(0)
  return buf


def generar_grafica_flujo_inverso(res):
  fig, ax = plt.subplots(figsize=(6, 3))
  categorias = [
      "Generación (P)",
      "Carga Local Est. (20%)",
      "Flujo Inverso a Red",
  ]
  valores = [res["p_kw"], res["carga_local_kw"], res["flujo_inverso_kw"]]
  colores = ["#0275d8", "#f0ad4e", "#d9534f"]

  bars = ax.bar(categorias, valores, color=colores, width=0.45)
  ax.set_ylabel("Potencia (kW)")
  ax.set_title("Balance de Flujo Inverso hacia la Red")
  ax.set_ylim(0, max(valores) * 1.25 if max(valores) > 0 else 10)

  for bar in bars:
    yval = bar.get_height()
    ax.text(
        bar.get_x() + bar.get_width() / 2.0,
        yval + (max(valores) * 0.03 if max(valores) > 0 else 0.2),
        f"{yval} kW",
        ha="center",
        va="bottom",
        fontsize=8,
        fontweight="bold",
    )

  plt.tight_layout()
  buf = io.BytesIO()
  plt.savefig(buf, format="png", dpi=150)
  plt.close(fig)
  buf.seek(0)
  return buf


from openpyxl.drawing.image import Image as OpenPyxlImage


def generar_excel(res):
  """Genera el reporte técnico en un archivo Excel incluyendo tablas y gráficas incrustadas."""
  output = io.BytesIO()

  # 1. Generar los gráficos en buffer de memoria
  img_pot_buf = generar_grafica_potencias(res)
  img_flujo_buf = generar_grafica_flujo_inverso(res)
  img_carg_buf = generar_grafica_utilizacion(res)

  with pd.ExcelWriter(output, engine="openpyxl") as writer:
    # 2. Hoja 1: Datos de Generación
    df_id = pd.DataFrame([{
        "RPU": res["rpu"],
        "Número de Solicitud": res["solicitud"],
        "Nivel de Tensión": res["nivel_tension"],
        "Esquema de Fases": res["fases"],
        "Generación Producida (kW)": res["p_kw"],
        "Potencia Aparente (kVA)": res["s_solicitada_kva"],
        "Corriente Nominal (A)": res["i_nominal"],
        "Corriente de Diseño 1.25 (A)": res["i_diseno"],
        "Factor de Potencia": res["fp"],
        "Tensión de Operación (kV)": res["v_linea_kv"],
    }])
    df_id.to_excel(writer, sheet_name="Datos_Generacion", index=False)

    # 3. Hoja 2: Evaluacion de Transformador y Cable
    df_trafo = pd.DataFrame([{
        "Capacidad Trafo (kVA)": res["trafo_kva"],
        "Clase Tensión": res["clase_aislamiento"],
        "Dictamen Trafo": "APTO" if res["trafo_soporta"] else "RECHAZADO",
        "Trafo Sugerido (kVA)": res["trafo_sugerido_kva"],
        "Dictamen Conductor": "APTO" if res["cable_soporta"] else "RECHAZADO",
        "Calibre Actual": res["calibre_cable"],
        "Calibre Sugerido": res["calibre_sugerido"],
        "Ampacidad (A)": res["ampacidad_cable"],
        "I_diseño (A)": res["i_diseno"],
    }])
    df_trafo.to_excel(
        writer, sheet_name="Evaluacion_Equipamiento", index=False
    )

    # 4. Hoja 3: Triangulo de Potencias y Flujo Inverso
    df_flujo = pd.DataFrame([{
        "Potencia Activa P (kW)": res["p_kw"],
        "Potencia Reactiva Q (kVAR)": res["q_kvar"],
        "Potencia Aparente S (kVA)": res["s_solicitada_kva"],
        "Carga Local Est. 20% (kW)": res["carga_local_kw"],
        "Flujo Inverso a Red (kW)": res["flujo_inverso_kw"],
    }])
    df_flujo.to_excel(writer, sheet_name="Graficas_y_Flujos", index=False)

    # 5. Insertar las imágenes en las pestañas correspondientes
    wb = writer.book

    # Pegar Triángulo de Potencias en la Hoja 3 (Celda A5)
    ws_flujo = wb["Graficas_y_Flujos"]
    img_pot = OpenPyxlImage(img_pot_buf)
    ws_flujo.add_image(img_pot, "A5")

    # Pegar Flujo Inverso a un costado (Celda I5)
    img_flujo = OpenPyxlImage(img_flujo_buf)
    ws_flujo.add_image(img_flujo, "I5")

    # Pegar Utilización en la Hoja 2 (Celda A5)
    ws_trafo = wb["Evaluacion_Equipamiento"]
    img_carg = OpenPyxlImage(img_carg_buf)
    ws_trafo.add_image(img_carg, "A5")

  output.seek(0)
  return output


def generar_pdf(res, normativa):
  """Genera el reporte ejecutivo en formato PDF incluyendo corrientes y dictamen CFE/CRE."""
  buffer = io.BytesIO()
  doc = SimpleDocTemplate(
      buffer,
      pagesize=letter,
      rightMargin=30,
      leftMargin=30,
      topMargin=30,
      bottomMargin=30,
  )
  elements = []
  styles = getSampleStyleSheet()

  # Estilo personalizado para celdas con texto largo
  style_cell = styles["Normal"]
  style_cell.fontSize = 8
  style_cell.leading = 10

  # Título Principal
  elements.append(
      Paragraph(
          "<b>REPORTE DE ESTUDIO DE INTERCONEXIÓN Y FLUJOS DE POTENCIA</b>",
          styles["Title"],
      )
  )
  elements.append(Spacer(1, 10))

  # 1. TABLA: Dictamen Técnico de Componentes
  data_componentes = [
      ["Componente", "Capacidad Actual", "Dictamen Técnico", "Recomendación"],
      [
          "Transformador",
          f"{res['trafo_kva']} kVA",
          "APTO" if res["trafo_soporta"] else "RECHAZADO",
          (
              "Sin cambio"
              if res["trafo_soporta"]
              else f"Cambiar a {res['trafo_sugerido_kva']} kVA"
          ),
      ],
      [
          "Conductor",
          f"{res['calibre_cable']} ({res['material_cable']})",
          "APTO" if res["cable_soporta"] else "RECHAZADO",
          (
              "Sin cambio"
              if res["cable_soporta"]
              else f"Cambiar a {res['calibre_sugerido']}"
          ),
      ],
  ]
  t_comp = Table(data_componentes, colWidths=[130, 130, 130, 140])
  t_comp.setStyle(
      TableStyle([
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
          ("ALIGN", (0, 0), (-1, -1), "CENTER"),
          ("FONTSIZE", (0, 0), (-1, -1), 8.5),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
      ])
  )
  elements.append(t_comp)
  elements.append(Spacer(1, 10))

  # 2. TABLA: Parámetros Eléctricos y Corrientes
  data_id = [
      ["RPU / Registro:", res["rpu"], "No. Solicitud:", res["solicitud"]],
      [
          "Nivel Tensión:",
          res["nivel_tension"],
          "Esquema Fases:",
          res["fases"],
      ],
      [
          "Potencia Activa (P):",
          f"{res['p_kw']} kW",
          "Potencia Reactiva (Q):",
          f"{res['q_kvar']} kVAR",
      ],
      [
          "Potencia Aparente (S):",
          f"{res['s_solicitada_kva']} kVA",
          "Flujo Inverso Red:",
          f"{res['flujo_inverso_kw']} kW",
      ],
      [
          "Corriente Nominal (In):",
          f"{res['i_nominal']} A",
          "Corriente Diseñó (1.25):",
          f"{res['i_diseno']} A",
      ],
  ]
  t_id = Table(data_id, colWidths=[130, 140, 130, 140])
  t_id.setStyle(
      TableStyle([
          ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
          ("ALIGN", (0, 0), (-1, -1), "LEFT"),
          ("FONTSIZE", (0, 0), (-1, -1), 8.5),
          ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0F0F0")),
          ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F0F0F0")),
      ])
  )
  elements.append(t_id)
  elements.append(Spacer(1, 10))

  # 3. TABLA: Dictamen Normativo CFE / CRE (Opinión Técnica y Estudio)
  str_opinion = "REQUIERE" if normativa["requiere_opinion"] else "NO REQUIERE"
  motivos_op = (
      "<br/>".join([f"• {m}" for m in normativa["motivos_opinion"]])
      if normativa["motivos_opinion"]
      else "Exento según procedimiento simplificado."
  )

  str_estudio = "REQUIERE" if normativa["requiere_estudio"] else "NO REQUIERE"
  motivos_est = (
      "<br/>".join([f"• {m}" for m in normativa["motivos_estudio"]])
      if normativa["motivos_estudio"]
      else "Dentro de los márgenes de cargabilidad y potencia."
  )

  data_normativa = [
      ["Trámite / Requerimiento", "Resultado", "Rubro / Criterio Aplicado"],
      [
          "Opinión Técnica (CFE)",
          str_opinion,
          Paragraph(motivos_op, style_cell),
      ],
      [
          "Estudio de Interconexión",
          str_estudio,
          Paragraph(motivos_est, style_cell),
      ],
  ]
  t_norm = Table(data_normativa, colWidths=[140, 100, 300])
  t_norm.setStyle(
      TableStyle([
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F77B4")),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
          ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
          ("ALIGN", (0, 0), (1, -1), "CENTER"),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("FONTSIZE", (0, 0), (-1, -1), 8.5),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
      ])
  )
  elements.append(t_norm)
  elements.append(Spacer(1, 10))

  # 4. GRÁFICAS: Triángulo de Potencias y Flujo Inverso
  img_pot = generar_grafica_potencias(res)
  img_flujo = generar_grafica_flujo_inverso(res)
  img_carg = generar_grafica_utilizacion(res)

  elements.append(Image(img_pot, width=380, height=180))
  elements.append(Spacer(1, 8))
  elements.append(Image(img_flujo, width=380, height=180))
  elements.append(Spacer(1, 8))
  elements.append(Image(img_carg, width=380, height=180))

  doc.build(elements)
  buffer.seek(0)
  return buffer