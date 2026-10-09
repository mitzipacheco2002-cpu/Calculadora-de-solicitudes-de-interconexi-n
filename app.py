import importlib
import calculos as calc

try:
    st = importlib.import_module("streamlit")
except ModuleNotFoundError as exc:
    if exc.name != "streamlit":
        raise
    raise SystemExit(
        "No se encontró Streamlit. Instálalo en el entorno de Python activo con: "
        "python -m pip install streamlit"
    ) from exc

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
st.title("⚡ Calculadora de Solicitudes y Estudio de Interconexión de centrales electricas de Generación Distribuida  CFE ")

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
# 3. EJECUCIÓN DE CÁLCULOS PRINCIPALES Y NORMATIVA
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

# Valores por defecto para el diccionario de resultados (se actualizan si se activa el flujo inverso)
res["flujo_inverso_evaluado"] = False
res["fv_conectada_kva"] = 0.0
res["potencia_total_kva"] = res["s_solicitada_kva"]

# Despliegue de Métricas Principales de la Solicitud
m1, m2, m3, m4 = st.columns(4)
m1.metric("Generación Producida", f"{res['p_kw']} kW")
m2.metric("Potencia Aparente Solicitada", f"{res['s_solicitada_kva']} kVA")
m3.metric(
    "Corriente Nominal (In)",
    f"{res['i_nominal']} A",
    delta=f"I_diseño (1.25): {res['i_diseno']} A",
    delta_color="off",
)
m4.metric("Flujo Inverso Est. Solicitud", f"{res['flujo_inverso_kw']} kW")

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
            f" kVA** de generación solicitada."
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
# 5. DICTAMEN NORMATIVO CFE
# ==============================================================================
st.divider()
st.header("⚖️ Dictamen Normativo (Opinión Técnica y Estudio de Interconexión)")

col_op, col_est = st.columns(2)

with col_op:
    st.subheader("📋 Opinión Técnica")
    if normativa.get("requiere_opinion", False):
        st.error("🔴 **REQUIERE OPINIÓN TÉCNICA**")
        st.write("**Criterios activados:**")
        for m in normativa.get("motivos_opinion", []):
            st.write(f"• {m}")
    else:
        st.success("🟢 **NO REQUIERE OPINIÓN TÉCNICA**")
        st.write(
            "• La solicitud cumple con las exenciones del procedimiento técnico."
        )

with col_est:
    st.subheader("⚠️ Estudio de Interconexión")
    if normativa.get("requiere_estudio", False):
        st.error("🔴 **REQUIERE ESTUDIO DE INTERCONEXIÓN**")
        st.write("**Criterios activados:**")
        for m in normativa.get("motivos_estudio", []):
            st.write(f"• {m}")
    else:
        st.success("🟢 **NO REQUIERE ESTUDIO DE INTERCONEXIÓN**")
        st.write("• El proyecto califica para el procedimiento simplificado.")

# ==============================================================================
# 6. SECCIÓN DE VISUALIZACIÓN GRÁFICA (TRIÁNGULO DE POTENCIA Y HOSTING CAPACITY)
# ==============================================================================
st.divider()
st.header("📊 Análisis Gráfico de Operación y Hosting Capacity")

col_g1, col_g2 = st.columns(2)

with col_g1:
    st.subheader("📐 Triángulo de Potencia")
    fig_tri = calc.generar_grafica_triangulo_potencias(
        p_kw=res["p_kw"],
        s_kva=res["s_solicitada_kva"],
        q_kvar=res["q_kvar"],
        fp=fp,
    )
    st.pyplot(fig_tri)

with col_g2:
    st.subheader("📊 Hosting Capacity")
    fig_trafo = calc.generar_grafica_Hosting_Capacity_trafo(res["s_solicitada_kva"], res["trafo_kva"])
    st.pyplot(fig_trafo)

# 1. Llamada a la gráfica individual del trafo (pasando los valores del diccionario)
img_bytes_trafo = calc.figura_a_bytes(fig_trafo)

# 2. Llamada a la gráfica global de porcentajes de utilización (4 barras)
fig_pct = calc.generar_grafica_Hosting_Capacity(res)
st.pyplot(fig_pct)


# 3. Exportación a bytes para PDF o Excel:
img_bytes_pct = calc.figura_a_bytes(fig_pct)

# Pasa 'img_bytes_pct' o 'img_bytes_trafo' a tus generadores de reporte en PDF/Excel

# ==============================================================================
# 7. SECCIÓN OPCIONAL (AL FINAL): EVALUACIÓN DE FLUJO INVERSO EN KVA
# ==============================================================================
st.divider()
st.header("🔄 Evaluación de Flujo Inverso Acumulado en Transformador (Opcional)")

evaluar_flujo_inverso = st.checkbox(
    "¿Desea evaluar el flujo inverso con generación fotovoltaica previamente conectada al transformador?"
)

if evaluar_flujo_inverso:
    st.markdown("---")
    fv_conectada_kva = st.number_input(
        "Potencia Total Fotovoltaica Ya Conectada al Transformador (kVA):",
        min_value=0.0,
        value=0.0,
        step=1.0,
        help="Suma total de la capacidad aparente (kVA) de los sistemas fotovoltaicos previamente instalados en este transformador.",
    )

    potencia_nueva_kva = res["s_solicitada_kva"]
    potencia_total_kva = fv_conectada_kva + potencia_nueva_kva

    # Actualizar estado de evaluación en el diccionario de resultados
    res["flujo_inverso_evaluado"] = True
    res["fv_conectada_kva"] = fv_conectada_kva
    res["potencia_total_kva"] = potencia_total_kva

    st.write(f"- **Capacidad del Transformador:** {trafo_kva:.2f} kVA")
    st.write(f"- **Potencia previa conectada:** {fv_conectada_kva:.2f} kVA")
    st.write(f"- **Nueva potencia a interconectar (Solicitud):** {potencia_nueva_kva:.2f} kVA")
    st.write(f"- **Potencia Total Acumulada en Transformador:** {potencia_total_kva:.2f} kVA")

    # Evaluación del límite del transformador
    if potencia_total_kva > trafo_kva:
        st.error(
            f"⚠️ **RIESGO DE FLUJO INVERSO DETECTADO:** La potencia acumulada ({potencia_total_kva:.2f} kVA) "
            f"supera la capacidad del transformador ({trafo_kva:.2f} kVA)."
        )
    else:
        st.success(
            f"✅ **SIN FLUJO INVERSO:** La potencia acumulada ({potencia_total_kva:.2f} kVA) está dentro del "
            f"límite nominal del transformador ({trafo_kva:.2f} kVA)."
        )

    # Generación de la gráfica de Flujo Inverso Acumulado
    fig_flujo = calc.generar_grafica_flujo_inverso(
        trafo_kva=trafo_kva,
        potencia_previa_kva=fv_conectada_kva,
        potencia_nueva_kva=potencia_nueva_kva,
    )
    st.pyplot(fig_flujo)
else:
    st.info(
        "ℹ️ No se evaluó el flujo inverso acumulado. Los cálculos y reportes se generarán considerando únicamente la potencia aparente de la solicitud actual."
    )

# ==============================================================================
# 7. EXPORTACIÓN DE REPORTES (EXCEL Y PDF)
# ==============================================================================
st.divider()
st.header("📥 Descargar Reportes Técnicos")

col_ex, col_pdf = st.columns(2)

with col_ex:
    st.download_button(
        label="📄 Descargar Estudio Completo en Excel (.xlsx)",
        data=calc.generar_excel(res),
        file_name=f"Estudio_Interconexion_{rpu}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with col_pdf:
    pdf_bytes = calc.generar_pdf(res, normativa)
    st.download_button(
        label="📄 Descargar Reporte Completo en PDF",
        data=pdf_bytes,
        file_name="Reporte_Estudio_Interconexion.pdf",
        mime="application/pdf",
    )

# ==============================================================================
# 8. PIE DE PÁGINA (CRÉDITOS Y LOGOTIPO)
# ==============================================================================
st.divider()

col_foot1, col_foot2 = st.columns([3, 1])

with col_foot1:
    st.markdown("### 🛠️ Desarrollo del Proyecto")
    st.markdown("**Creado por:** Mitzi Pacheco Martinez")
    st.markdown(
        "Herramienta desarrollada para el estudio de capacidad de alojamiento y análisis de interconexión en redes de distribución."
    )