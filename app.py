import calculos as calc
import streamlit as st

st.set_page_config(
    page_title="Estudio de Interconexión y Flujos de Potencia",
    layout="wide",
)

# ==============================================================================
# 1. BARRA LATERAL (SIDEBAR): SELECCIÓN PRINCIPAL DEL SISTEMA
# ==============================================================================
st.sidebar.header("⚙️ 1. Configuración del Sistema Eléctrico")

nivel_tension = st.sidebar.radio(
    "Selecciona el Nivel de Tensión:",
    ["BAJA TENSION (BT)", "Media tensión (MT)"],
)

fases_opciones = list(calc.VOLTAJES_SISTEMA[nivel_tension].keys())
fases_sel = st.sidebar.selectbox("Selecciona el Esquema de Fases:", fases_opciones)

voltajes_disponibles = calc.VOLTAJES_SISTEMA[nivel_tension][fases_sel]
v_linea_kv = st.sidebar.selectbox(
    "Tensión Nominal de Línea (kV):",
    voltajes_disponibles,
    format_func=lambda x: f"{x} kV ({int(x*1000)} V)" if x < 1.0 else f"{x} kV",
)

st.sidebar.divider()
st.sidebar.header("📋 2. Datos del Usuario y Generación")
rpu = st.sidebar.text_input("RPU / Registro de Usuario", value="123456789012")
solicitud = st.sidebar.text_input("Número de Solicitud CFE", value="SOL-2026-099")

p_mw = st.sidebar.number_input(
    "Capacidad de generación (MW)",
    min_value=0.001,
    max_value=50.0,
    value=0.015,
    step=0.005,
    format="%.3f",
)
fp = st.sidebar.slider("Factor de Potencia (FP)", 0.80, 1.00, 0.90, 0.01)

# Datos de Centro de Carga
st.sidebar.divider()
st.sidebar.header("🏢 Datos del Centro de Carga")

asociada_centro_carga = st.sidebar.checkbox(
    "Central Eléctrica Asociada a Centro de Carga", value=True
)

if asociada_centro_carga:
  carga_contratada_kw = st.sidebar.number_input(
      "Carga Contratada Existente (kW)",
      min_value=0.0,
      value=10.0,
      step=1.0,
  )
  fases_contratadas_coinciden = st.sidebar.checkbox(
      "¿Coincide el número de fases del suministro con la interconexión?",
      value=True,
  )
else:
  carga_contratada_kw = 0.0
  fases_contratadas_coinciden = False

# ==============================================================================
# 2. SECCIÓN PRINCIPAL: EQUIPAMIENTO ADAPTATIVO
# ==============================================================================
st.title("⚡ Evaluación de Capacidad Eléctrica e Interconexión")

col1, col2 = st.columns(2)

with col1:
  st.subheader("🔌 Parámetros del Transformador")

  if "Monofásico" in fases_sel or "Bifásico" in fases_sel:
    lista_trafos = calc.CATALOGO_TRAFOS_MONOFASICOS
  else:
    lista_trafos = calc.CATALOGO_TRAFOS_TRIFASICOS

  trafo_kva = st.selectbox(
      "Capacidad Nominal del Transformador (kVA)",
      lista_trafos,
      index=2 if len(lista_trafos) > 2 else 0,
  )

  if "BAJA" in nivel_tension.upper() or "BT" in nivel_tension.upper():
    clases_aislamiento = ["BAJA TENSION(MENOR O IGUAL A 1 KV) (BT)"]
  else:
    clases_aislamiento = ["Clase 15 kV", "Clase 18 y 25 kV", "Clase 34.5 kV"]

  clase_aislamiento = st.selectbox(
      "Clase de Tensión de Aislamiento", clases_aislamiento
  )

  info_bil = calc.DATOS_DE_SOLICITUD[clase_aislamiento]
  st.success(
      f"🛡️ **NBA / BIL:** **{info_bil['de_solicitud']}** | Soportabilidad 60 Hz:"
      f" **{info_bil['tension_soporte_60hz']}**"
  )

with col2:
  st.subheader("🧵 Parámetros del Conductor")
  material_cable = st.radio("Material del Conductor", ["Cobre", "Aluminio"])

  calibres_disponibles = [
      c
      for c, v in calc.CATALOGO_CABLES_75C.items()
      if not (material_cable == "Aluminio" and v[1] is None)
  ]

  calibre_sel = st.selectbox(
      "Calibre del Conductor (NOM-001-SEDE 75 °C)",
      calibres_disponibles,
      index=calibres_disponibles.index("8 AWG")
      if "8 AWG" in calibres_disponibles
      else 0,
  )

  ampacidad = calc.obtener_ampacidad(calibre_sel, material_cable)
  st.info(
      f"⚡ **Ampacidad (75 °C):** **{ampacidad} A** ({material_cable} -"
      f" Calibre {calibre_sel})"
  )

# ==============================================================================
# 3. EJECUCIÓN DE CÁLCULOS Y DICTÁMENES
# ==============================================================================
res = calc.evaluar_solicitud_completa(
    rpu=rpu,
    solicitud=solicitud,
    nivel_tension=nivel_tension,
    fases=fases_sel,
    p_mw=p_mw,
    fp=fp,
    trafo_kva=trafo_kva,
    v_linea_kv=v_linea_kv,
    calibre_cable=calibre_sel,
    material_cable=material_cable,
    clase_aislamiento=clase_aislamiento,
)

normativa = calc.evaluar_criterios_normativos_cfe(
    nivel_tension=nivel_tension,
    fases=fases_sel,
    p_kw=res["p_kw"],
    s_solicitada_kva=res["s_solicitada_kva"],
    asociada_centro_carga=asociada_centro_carga,
    carga_contratada_kw=carga_contratada_kw,
    fases_contratadas_coinciden=fases_contratadas_coinciden,
    pct_trafo_100=res["pct_trafo_100"],
    pct_cond_100=res["pct_cond_100"],
)

# Métricas principales
m1, m2, m3, m4 = st.columns(4)
m1.metric("Generación Producida", f"{res['p_kw']} kW")
m2.metric("Potencia Aparente", f"{res['s_solicitada_kva']} kVA")
m3.metric(
    "Corriente Nominal (In)",
    f"{res['i_nominal']} A",
    delta=f"I_diseño (1.25): {res['i_diseno']} A",
    delta_color="off",
)
m4.metric("Flujo Inverso Est. a Red", f"{res['flujo_inverso_kw']} kW")

# ==============================================================================
# 4. DICTAMEN DE CAPACIDAD Y RECOMENDACIÓN DE CAMBIO
# ==============================================================================
st.divider()
st.header("📌 Dictamen Técnico de Alojamiento y Capacidad")

col_d1, col_d2 = st.columns(2)

with col_d1:
  if res["trafo_soporta"]:
    st.success(
        "✅ **TRANSFORMADOR APTO:** El transformador seleccionado tiene"
        f" capacidad suficiente para alojar los **{res['s_solicitada_kva']}"
        f" kVA** de generación."
    )
  else:
    st.error(
        "❌ **TRANSFORMADOR RECHAZADO (SOBRECARGADO):** La demanda aparente de"
        f" **{res['s_solicitada_kva']} kVA** supera la capacidad del"
        f" transformador actual ({res['trafo_kva']} kVA)."
    )
    st.warning(
        "💡 **Propuesta de Cambio:** Se recomienda instalar un transformador"
        f" comercial de **{res['trafo_sugerido_kva']} kVA**."
    )

with col_d2:
  if res["cable_soporta"]:
    st.success(
        "✅ **CONDUCTOR APTO:** El conductor soporta la corriente de diseño"
        f" (**{res['i_diseno']} A**) sin rebasar su ampacidad nominal"
        f" ({res['ampacidad_cable']} A)."
    )
  else:
    st.error(
        "❌ **CONDUCTOR RECHAZADO (SOBRECORRIENTE):** La corriente de diseño"
        f" de **{res['i_diseno']} A** (In x 1.25) excede la ampacidad del"
        f" calibre seleccionado ({res['ampacidad_cable']} A)."
    )
    st.warning(
        "💡 **Propuesta de Cambio:** Se sugiere reemplazar por calibre"
        f" **{res['calibre_sugerido']}**."
    )

# Detalle en la sección de Conductor
st.write("### 🧵 Evaluación del Conductor")
st.write(
    f"• **Calibre y Material:** {res['calibre_cable']} ({res['material_cable']})"
)
st.write(f"• **Ampacidad Nominal (75 °C):** {res['ampacidad_cable']} A")
st.write(f"• **Corriente Nominal de Operación ($I_n$):** {res['i_nominal']} A")
st.write(
    "• **Corriente de Diseño ($I_{\\text{diseño}} = I_n \\times 1.25$):**"
    f" **{res['i_diseno']} A**"
)
st.write(
    "• **Utilización del Conductor (vs $I_{\\text{diseño}}$):**"
    f" {res['pct_cond_100']}%"
)

# ==============================================================================
# 5. ANÁLISIS DE FLUJO INVERSO Y TRIÁNGULO DE POTENCIAS
# ==============================================================================
st.divider()
st.header("🔄 Análisis de Flujo Inverso a la Red")

st.markdown("""
El **Flujo Inverso** representa la potencia activa producida por el sistema de generación que **no es consumida localmente** y termina inyectándose aguas arriba hacia la red de distribución.

$$\\text{Flujo Inverso (kW)} = \\max(0, P_{\\text{Generación (kW)}} - P_{\\text{Carga Local Mínima (kW)}})$$

*Nota: Se considera una carga mínima local estimada correspondiente al 20% de la capacidad del transformador.*
""")

m1, m2, m3 = st.columns(3)
m1.metric("Generación Producida (P)", f"{res['p_kw']} kW")
m2.metric("Carga Local Estimada (20%)", f"{res['carga_local_kw']} kW")
m3.metric("Flujo Inverso Hacia la Red", f"{res['flujo_inverso_kw']} kW")

st.image(
    calc.generar_grafica_flujo_inverso(res),
    caption="Graficación del Balance de Flujo Inverso",
)

st.divider()
st.header("📐 Triángulo de Potencias y Cargabilidad")

g1, g2 = st.columns(2)

with g1:
  st.subheader("🔺 Potencia Activa, Reactiva y Aparente")
  st.write(f"**Potencia Activa ($P$):** {res['p_kw']} kW")
  st.write(f"**Potencia Reactiva ($Q$):** {res['q_kvar']} kVAR")
  st.write(f"**Potencia Aparente ($S$):** {res['s_solicitada_kva']} kVA")
  st.image(
      calc.generar_grafica_potencias(res), caption="Triángulo de Potencias"
  )

with g2:
  st.subheader("📊 Porcentajes de Utilización")
  st.write(f"**Utilización Trafo:** {res['pct_trafo_100']}%")
  st.write(f"**Utilización Cable:** {res['pct_cond_100']}%")
  st.image(
      calc.generar_grafica_utilizacion(res),
      caption="Utilización de Equipos",
  )

# ==============================================================================
# 6. DICTAMEN NORMATIVO CFE / CRE
# ==============================================================================
st.divider()
st.header("⚖️ Dictamen Normativo (Opinión Técnica y Estudio de Interconexión)")

col_op, col_est = st.columns(2)

with col_op:
  st.subheader("📋 Opinión Técnica")
  if normativa["requiere_opinion"]:
    st.error("🔴 **REQUIERE OPINIÓN TÉCNICA**")
    st.write("**Criterios activados:**")
    for m in normativa["motivos_opinion"]:
      st.write(f"• {m}")
  else:
    st.success("🟢 **NO REQUIERE OPINIÓN TÉCNICA**")
    st.write(
        "• La solicitud cumple con las exenciones del procedimiento técnico."
    )

with col_est:
  st.subheader("🔬 Estudio de Interconexión")
  if normativa["requiere_estudio"]:
    st.error("🔴 **REQUIERE ESTUDIO DE INTERCONEXIÓN**")
    st.write("**Criterios activados:**")
    for m in normativa["motivos_estudio"]:
      st.write(f"• {m}")
  else:
    st.success("🟢 **NO REQUIERE ESTUDIO DE INTERCONEXIÓN**")
    st.write(
        "• La solicitud se encuentra dentro de los márgenes de seguridad de la"
        " red."
    )

# ==============================================================================
# 7. EXPORTACIÓN DE REPORTES
# ==============================================================================
st.divider()
st.header("📥 Descargar Reportes")

col_d1, col_d2 = st.columns(2)

with col_d1:
  st.download_button(
      label="📄 Descargar Estudio Completo en Excel (.xlsx)",
      data=calc.generar_excel(res),
      file_name=f"Estudio_Interconexion_{rpu}.xlsx",
      mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  )

with col_d2:
  st.download_button(
      label="📕 Descargar Reporte Completo en PDF (.pdf)",
      data=calc.generar_pdf(res, normativa),
      file_name=f"Reporte_Interconexion_{rpu}.pdf",
      mime="application/pdf",
  )