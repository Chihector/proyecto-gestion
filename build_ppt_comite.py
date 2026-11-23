# -*- coding: utf-8 -*-
"""Construye la presentación del Comité usando la plantilla institucional.

Salida: PPT_Comite_Sala_de_Crisis.pptx
Contenido: cifras y figuras generadas por el pipeline del proyecto (reports/, dashboard/).
Las diapositivas son visuales (gráficos + KPIs); el relato completo va en notas del exponente.
"""

from pathlib import Path
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parent
PLANTILLA = ROOT / "Plantilla PPT Institucional.pptx"
SALIDA = ROOT / "PPT_Comite_Sala_de_Crisis.pptx"

FONT = "Montserrat"
RED = RGBColor(0xD0, 0x01, 0x20)
DARK = RGBColor(0x28, 0x28, 0x28)
GRAY = RGBColor(0x60, 0x60, 0x60)
LIGHT = RGBColor(0xF5, 0xF5, 0xF5)
LINE = RGBColor(0xDD, 0xDD, 0xDD)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation(str(PLANTILLA))


# ---------------------------------------------------------------- helpers ---
def textbox(slide, x, y, w, h, text, size=14, color=DARK, bold=False,
            align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP, font=FONT, italic=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.italic = italic
    r.font.name = font
    r.font.color.rgb = color
    return box


def rect(slide, x, y, w, h, fill=LIGHT, line=None, rounded=False):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    if rounded:
        try:
            shp.adjustments[0] = 0.06
        except Exception:
            pass
    return shp


def kpi(slide, x, y, w, h, number, label, sub="", accent=RED):
    rect(slide, x, y, w, h, LIGHT, LINE, rounded=True)
    rect(slide, x, y, 0.06, h, accent)
    textbox(slide, x + 0.22, y + 0.12, w - 0.35, 0.52, number, 26, accent, True)
    textbox(slide, x + 0.22, y + 0.66, w - 0.35, 0.34, label, 11, DARK, True)
    if sub:
        textbox(slide, x + 0.22, y + 0.98, w - 0.35, h - 1.05, sub, 9.5, GRAY)


def image_fit(slide, path, x, y, w, h, border=True):
    iw, ih = Image.open(path).size
    scale = min(w / iw, h / ih)
    nw, nh = iw * scale, ih * scale
    px, py = x + (w - nw) / 2, y + (h - nh) / 2
    if border:
        rect(slide, px - 0.035, py - 0.035, nw + 0.07, nh + 0.07, WHITE, LINE)
    slide.shapes.add_picture(str(path), Inches(px), Inches(py),
                             width=Inches(nw), height=Inches(nh))
    return px, py, nw, nh


def caption(slide, y, text):
    rect(slide, 0.56, y, 12.2, 0.015, LINE)
    textbox(slide, 0.56, y + 0.07, 12.2, 0.36, text, 10, GRAY)


def base(title, subtitle, tag, idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # "En blanco"
    textbox(slide, 0.56, 0.055, 11.9, 0.26,
            "SALA DE CRISIS COVID-19   ›   COMITÉ 24-NOV   ›   " + tag,
            8.5, RED, True)
    size = 25 if len(title) < 48 else 22
    textbox(slide, 0.56, 0.34, 12.2, 0.62, title, size, DARK, True)
    rect(slide, 0.56, 1.16, 1.8, 0.055, RED)
    textbox(slide, 0.56, 1.27, 12.2, 0.44, subtitle, 12, GRAY)
    textbox(slide, 0.56, 6.82, 9.5, 0.26,
            "Gestión de Datos · IN1232C · Sala de crisis COVID-19", 8, WHITE)
    textbox(slide, 11.8, 6.82, 0.95, 0.26, str(idx), 8, WHITE, align=PP_ALIGN.RIGHT)
    return slide


def notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text.strip()


# --------------------------------------------------- portada (de plantilla) ---
slide = prs.slides[0]
for shp in slide.shapes:
    if not shp.has_text_frame:
        continue
    txt = shp.text_frame.text
    if "Título de la presentación" in txt:
        p = shp.text_frame.paragraphs[0]
        p.runs[0].text = "Sala de crisis COVID-19"
        p.runs[0].font.size = Pt(40)
    elif "Nombre expositor" in txt:
        ps = shp.text_frame.paragraphs
        ps[0].runs[0].text = "Relato al Comité · martes 24 de noviembre de 2026"
        if len(ps[0].runs) > 1:
            ps[0].runs[1].text = ""
        ps[1].runs[0].text = "Gestión de Datos · IN1232C · Equipo [completar nombres]"
        for p in ps:
            p.runs[0].font.size = Pt(18)
notes(slide, """
PORTADA. Abrir con el encargo: una plataforma confiable con tres años de pandemia, evidencia sobre Chile y el mundo, y tres recomendaciones. Aclarar que el relato dura 7 minutos y se apoya en el tablero, no en texto. Completar los nombres del equipo antes de la sesión.
""")

# Quitar las tres diapositivas vacías que trae la plantilla
xml_slides = prs.slides._sldIdLst
for sld in list(xml_slides)[1:4]:
    rId = sld.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
    prs.part.drop_rel(rId)
    xml_slides.remove(sld)

# ------------------------------------------------------------ 2 · cadena ---
s = base("De 1.143 archivos a una decisión en vivo",
         "La cadena completa funciona, es reproducible y respeta la fecha de corte",
         "LA CADENA", 2)
pasos = [
    ("1.143 reportes", "22-ene-2020 → 9-mar-2023\n651 MB de CSV crudos"),
    ("5 esquemas unificados", "snake_case + fechas ISO\n4.287.473 filas"),
    ("Parquet + reglas R2", "109 MB (18,6 % del CSV)\nlectura 8,2× más rápida"),
    ("DW estrella DuckDB", "4.287.374 hechos\n2 fuentes externas por ISO3"),
    ("Tablero y modelos", "KPI, mapas, alerta\ny pronóstico a 14 días"),
]
x = 0.56
for i, (t, d) in enumerate(pasos):
    rect(s, x, 1.95, 2.22, 1.55, LIGHT, LINE, rounded=True)
    rect(s, x, 1.95, 2.22, 0.07, RED)
    textbox(s, x + 0.14, 2.12, 1.95, 0.32, str(i + 1), 13, RED, True)
    textbox(s, x + 0.14, 2.45, 1.95, 0.35, t, 11.5, DARK, True)
    textbox(s, x + 0.14, 2.82, 1.95, 0.6, d, 8.5, GRAY)
    if i < 4:
        textbox(s, x + 2.23, 2.5, 0.2, 0.4, "›", 18, RED, True)
    x += 2.43
kpi(s, 0.56, 3.85, 2.9, 1.25, "99,95 %", "filas con territorio UID", "4.284 territorios canónicos")
kpi(s, 3.62, 3.85, 2.9, 1.25, "201/218", "países cruzan con OWID", "92,2 % · vacunación")
kpi(s, 6.68, 3.85, 2.9, 1.25, "182/218", "países cruzan con OxCGRT", "83,5 % · restricciones")
kpi(s, 9.74, 3.85, 3.02, 1.25, "0", "fuga de datos", "todo usa solo datos ≤ corte")
rect(s, 0.56, 5.45, 12.2, 0.85, WHITE, LINE, rounded=True)
textbox(s, 0.78, 5.6, 11.8, 0.55,
        "Motor elegido: DuckDB (consulta Parquet con SQL) · equivalente en nube estimado en US$35–50/mes · "
        "el README regenera todo en < 15 min.",
        11, DARK)
notes(s, """
QUÉ CONSTRUIMOS (≈45 s). Mostrar la cadena de izquierda a derecha: descarga reproducible de los 1.143 reportes, cinco esquemas unificados en snake_case, capa limpia Parquet con reglas de calidad, almacén en estrella y tablero con modelos. Destacar que Parquet pesa el 18,6 % del CSV y se lee 8,2 veces más rápido, y que elegimos DuckDB frente a alternativas NoSQL porque el grano es territorial-día y consultamos con SQL. Los dos fuentes externas cruzan por ISO3; los territorios que no cruzan se informan, no se esconden. El linaje permite decir de qué archivo y fila sale cada número. Nada de esto depende de subclonar datos: el README lo regenera.
""")

# ------------------------------------------------------------- 3 · P1 -----
s = base("P1 · Chile frente a Sudamérica",
         "Segundo en incidencia acumulada y en mortalidad aparente", "P1 · ANÁLISIS", 3)
kpi(s, 0.56, 1.95, 3.5, 1.45, "27.162", "casos por 100.000", "2.º tras Uruguay (29.775)")
kpi(s, 0.56, 3.55, 3.5, 1.45, "336,2", "fallecidos por 100.000", "2.º tras Perú (665,8)")
image_fit(s, ROOT / "reports/fig_p1_suramerica.png", 4.35, 1.95, 8.4, 3.75)
caption(s, 5.95, "Perú lidera mortalidad aparente (665,8/100k) por la reconciliación de 2021; Chile 336,2 supera a Argentina (288,7) y Colombia (279,7).")
notes(s, """
P1 (≈30 s). Chile registró 27.162 casos y 336,2 fallecidos por 100.000 habitantes en todo el período: segundo país de Sudamérica en incidencia, detrás de Uruguay, y segundo en mortalidad aparente, detrás de Perú. La cifra peruana está inflada por la reconciliación oficial de 2021, así que conviene leer fallecidos por 100.000 y no solo la razón muertes/casos. Chile aguanta la comparación regional, pero con matices: su mortalidad aparente es mayor que la de Argentina y Colombia. Número, gráfico e interpretación: eso es lo que pide la pregunta.
""")

# --------------------------------------------------------- 4 · P1 olas ----
s = base("P1 · Cinco olas; la primera, la más letal",
         "Casos y fallecidos nuevos por 100.000 con media móvil de 7 días", "P1 · ANÁLISIS", 4)
image_fit(s, ROOT / "reports/fig_p1_chile_olas.png", 0.56, 1.85, 12.2, 4.25)
caption(s, 6.18, "Picos MA7: 17-jun-2020 · 14-abr-2021 · 13-feb-2022 (ómicron: 35.656 casos/día) · 17-jun-2022 · 10-nov-2022.")
notes(s, """
P1, OLAS (≈35 s). Chile tuvo cinco olas. La más letal fue la primera: 310 fallecidos por día en promedio móvil el 23 de julio de 2020, tras el pico de casos del 17 de junio. La de mayor magnitud fue ómicron, el 13 de febrero de 2022, con unos 35.700 casos diarios en promedio móvil —casi la mitad de todos los casos del país en tres años— pero con una letalidad mucho menor, unos 150 fallecidos diarios en promedio. La media móvil de 7 días se calcula siempre sobre casos nuevos, nunca sobre acumulados: es el error más frecuente con este conjunto.
""")

# ------------------------------------------------------------- 5 · P2 ----
s = base("P2 · El golpe no fue uniforme dentro de Chile",
         "Incidencia y fallecidos por 100.000 por región, desde junio de 2020", "P2 · ANÁLISIS", 5)
image_fit(s, ROOT / "reports/fig_p2_mapa_chile.png", 0.56, 1.85, 4.05, 4.25)
image_fit(s, ROOT / "reports/fig_p2_regiones.png", 4.8, 1.85, 7.96, 4.25)
caption(s, 6.18, "Magallanes (467,8) y Metropolitana (434,8) lideran fallecidos/100k; Biobío está en el puesto 10 de 16 (310,1).")
notes(s, """
P2 (≈30 s). Desde junio de 2020 —cuando Chile pasa de reporte nacional a 16 regiones— Magallanes y Metropolitana encabezan la mortalidad aparente por 100.000. Metropolitana además concentra el mayor volumen absoluto. Biobío quedó en el puesto 10 de 16, con 310 fallecidos por 100.000, en línea con su incidencia (puesto 8). El mapa regional se construye con latitud y longitud de la tabla UID; el ranking por 100.000 evita que las regiones más pobladas parezcan automáticamente las más golpeadas.
""")

# ------------------------------------------------------------- 6 · P3 ----
s = base("P3 · La letalidad aparente cayó… pero no solo por la vacuna",
         "CFR mensual cruzada con la cobertura de vacunación (fuente externa OWID)", "P3 · ANÁLISIS", 6)
image_fit(s, ROOT / "reports/fig_p3_letalidad.png", 0.56, 1.85, 7.25, 4.25)
kpi(s, 8.05, 1.95, 4.7, 1.25, "2,54 % → 0,92 %", "CFR aparente en Chile", "antes de vacunar → desde junio 2021")
kpi(s, 8.05, 3.35, 4.7, 1.22, "90,3 %", "cobertura completa al cierre", "Chile cruzó el 50 % antes que sus pares")
rect(s, 8.05, 4.75, 4.7, 1.55, WHITE, RED, rounded=True)
textbox(s, 8.25, 4.92, 4.3, 1.25,
        "ADVERTENCIA\nLa razón fallecidos/casos depende del testeo: con ómicron se detectaron muchos más casos leves. "
        "Para comparar, use fallecidos por 100.000.",
        10, DARK)
notes(s, """
P3 (≈35 s). La letalidad aparente chilena bajó de 2,54 % antes de la vacunación a 0,92 % desde junio de 2021. Parte de la caída es real y parte es mecánica: el testeo masivo detectó muchísimos más casos leves, especialmente con ómicron, y eso reduce el denominador de la razón por caso. Por eso la gráfica cruza la CFR con el porcentaje de vacunados y por eso la comparación se apoya en fallecidos por 100.000. Los días de corrección masiva —Chile 21-mar-2022, Perú 2-jun-2021, corrección global 23-may-2022— se excluyen del cálculo mensual, pero se conservan en los acumulados publicados.
""")

# ------------------------------------------------------------- 7 · P4 ----
s = base("P4 · Datos confiables no son datos bonitos",
         "Índice de calidad R2: seis dimensiones, umbrales y decisiones documentadas", "P4 · CALIDAD", 7)
kpi(s, 0.56, 1.9, 2.9, 1.15, "6", "dimensiones", "completitud a oportunidad")
kpi(s, 3.62, 1.9, 2.9, 1.15, "5 / 10 / 1", "OK / warn / fail", "reglas ejecutadas por carga")
kpi(s, 6.68, 1.9, 2.9, 1.15, "1.097.163", "casos retirados", "corrección global 23-may-2022")
kpi(s, 9.74, 1.9, 3.02, 1.15, "34,0 → 99", "EE.UU. → Chile", "índice de calidad (0–100)")
cols = [(0.56, 1.9, "País"), (2.46, 1.4, "Índice"), (3.86, 8.9, "Problema principal")]
x0, y0 = 0.56, 3.18
for x, w, label in cols:
    rect(s, x, y0, w, 0.42, RED)
    textbox(s, x + 0.12, y0 + 0.08, w - 0.2, 0.28, label, 10, WHITE, True)
filas = [
    ("USA", "34,0", "54.746 retrocesos · 7.125 fallecidos > casos"),
    ("COL", "64,1", "234 retrocesos · 1 día sin reporte"),
    ("PER", "65,8", "466 retrocesos · artefacto de reconciliación 2021"),
    ("BEL", "69,5", "348 fallecidos > casos (CFR aparente > 100 %)"),
    ("PRK", "70,0", "300 fallecidos > casos, sin retrocesos"),
]
for i, fila in enumerate(filas):
    y = y0 + 0.42 + i * 0.46
    for (x, w, _), val in zip(cols, fila):
        rect(s, x, y, w, 0.46, LIGHT if i % 2 == 0 else WHITE, LINE)
        textbox(s, x + 0.12, y + 0.09, w - 0.2, 0.3, val, 9.5, DARK,
                bold=(val == "34,0"))
rect(s, 0.56, 5.98, 12.2, 0.42, WHITE, RED, rounded=True)
textbox(s, 0.75, 6.05, 11.85, 0.28,
        "Decisión: marcar y conservar los retrocesos · excluir días de corrección de medias y modelos · imputar es inventar · linaje por archivo y fila.",
        9.5, DARK)
notes(s, """
P4 (≈35 s). El índice propio de calidad, con reglas ejecutables en las seis dimensiones, deja ver que los datos vienen con asteriscos. EE.UU. es el peor (34) por decenas de miles de retrocesos y miles de días con fallecidos mayores que casos; Colombia y Perú siguen. Chile ronda 99. No imputamos: los retrocesos se conservan marcados, porque que un acumulado baje por una corrección es información. Los días de corrección masiva se excluyen de promedios y modelos. Cada cifra del tablero puede rastrearse hasta el archivo y la fila de origen.
""")

# ------------------------------------------------------------- 8 · P5 ----
s = base("P5 · Tres pandemias; Chile en la de olas múltiples",
         "K-means sobre indicadores · k=3, silueta 0,325 · 131 países con ≥100.000 casos", "P5 · MODELOS", 8)
image_fit(s, ROOT / "reports/fig_p5_clusters.png", 0.56, 1.85, 5.7, 4.25)
groups = [
    ("GRUPO 0 · 54 países", "15.236 casos/100k · CFR 1,50 %", "América Latina, Europa del Este, EE.UU. · CHILE ESTÁ AQUÍ"),
    ("GRUPO 1 · 26 países", "1.248 casos/100k · CFR 1,41 %", "Baja incidencia acumulada, pandemia más tardía"),
    ("GRUPO 2 · 51 países", "39.520 casos/100k · CFR 0,41 %", "68 % de los casos en 2022 · testeo y vacunación altos"),
]
y = 1.9
for head, mid, foot in groups:
    rect(s, 6.5, y, 6.25, 1.3, LIGHT, LINE, rounded=True)
    rect(s, 6.5, y, 0.06, 1.3, RED)
    textbox(s, 6.72, y + 0.08, 5.85, 0.3, head, 11.5, RED, True)
    textbox(s, 6.72, y + 0.4, 5.85, 0.3, mid, 11, DARK, True)
    textbox(s, 6.72, y + 0.72, 5.85, 0.5, foot, 9, GRAY)
    y += 1.42
rect(s, 6.5, 6.32, 6.25, 0.28, WHITE)
textbox(s, 6.5, 6.12, 6.25, 0.26,
        "Por forma pura, todas las curvas convergen en ómicron (silueta 0,09).", 8.5, GRAY, italic=True)
notes(s, """
P5 (≈30 s). Agrupamos países por indicadores —casos y fallecidos por 100.000, CFR aparente, proporción de casos en 2020 y en 2022, y número de olas— porque agrupar solo por la forma de la curva no separa nada: todos los picos convergen en ómicron. Salieron tres grupos con silueta 0,325. Chile está en el grupo 0, junto a América Latina, Europa del Este y EE.UU.: olas múltiples con letalidad aparente alta, donde el esfuerzo de 2020-2021 queda eclipsado en volumen por ómicron, pero no en mortalidad.
""")

# ------------------------------------------------------------- 9 · P6 ----
s = base("P6 · Ómicron: no acertamos el número, sí la ola",
         "Pronóstico sin fuga de datos + alerta temprana evaluada en tres años de Chile", "P6 · MODELOS", 9)
image_fit(s, ROOT / "reports/fig_p6_pronostico.png", 0.56, 1.85, 7.5, 4.25)
kpi(s, 8.3, 1.9, 4.46, 1.1, "94 días", "de anticipación", "alerta 11-nov-2021 → pico 13-feb-2022")
kpi(s, 8.3, 3.1, 4.46, 1.1, "5 / 5", "olas detectadas", "39–100 días antes (mediana 48)")
kpi(s, 8.3, 4.3, 2.13, 1.35, "1", "falsa alarma", "en tres años")
kpi(s, 10.63, 4.3, 2.13, 1.35, "25,7 %", "MAPE Holt", "corte 1-dic-2021")
caption(s, 6.18, "Con corte al 2021-12-01 la curva era plana: un modelo de 14 días no podía extrapolar el salto ×20 de ómicron. La alerta, sí.")
notes(s, """
P6 (≈40 s). Con fecha de corte al 1 de diciembre de 2021, ningún modelo de 14 días podía anticipar el salto veinte veces de ómicron: la curva estaba plana y el mejor modelo, Holt, tuvo un error medio del 25,7 %. Lo que sí funcionó fue la alerta temprana —variación semanal de la media móvil de 7 días ≥ 30 % e incidencia ≥ 6 por 100.000— que encendió la primera señal el 11 de noviembre de 2021, 94 días antes del pico. En toda la historia de Chile detectó las cinco olas con 39 a 100 días de anticipación y dio una sola falsa alarma estricta. El pronóstico y la alerta reciben la fecha de corte como parámetro y no ven datos posteriores: eso se comprueba en vivo.
""")

# ------------------------------------------------------------ 10 · P7 ----
s = base("P7 · Más vacunación, menos mortalidad a 8 semanas",
         "Asociación ecológica en Chile, Perú, EE.UU. y Brasil · correlación ≠ causalidad", "P7 · PROPIA", 10)
image_fit(s, ROOT / "reports/fig_p7_vacunacion.png", 0.56, 1.85, 6.6, 4.25)
rect(s, 7.4, 1.95, 5.36, 2.5, LIGHT, LINE, rounded=True)
textbox(s, 7.65, 2.12, 4.9, 0.32, "Fallecidos / 100.000 / semana", 11, RED, True)
p7 = [("Chile", "2,33 → 1,25"), ("Perú", "6,84 → 0,84"),
      ("EE.UU.", "2,40 → 1,81"), ("Brasil", "3,12 → 0,62")]
y = 2.55
for pais, vals in p7:
    textbox(s, 7.65, y, 2.2, 0.32, pais, 11, DARK, True)
    textbox(s, 9.7, y, 2.8, 0.32, vals, 11, RED, True)
    y += 0.44
rect(s, 7.4, 4.62, 5.36, 1.75, WHITE, RED, rounded=True)
textbox(s, 7.65, 4.8, 4.9, 1.45,
        "LECTURA\nAsociación negativa en los cuatro países: a mayor cobertura, menos mortalidad ocho semanas después. "
        "Es ecológica, no causal. En Chile la señal se atenúa al superar el 50 % de vacunación (techo 90 %): "
        "importan también las olas y la vigilancia.",
        10, DARK)
notes(s, """
P7 (≈35 s). Nuestra pregunta propia cruza la cobertura de vacunación de OWID con la mortalidad semanal ocho semanas después. En los cuatro países analizados la asociación es negativa: Chile pasa de 2,33 a 1,25 fallecidos por 100.000 y semana, Perú de 6,84 a 0,84, EE.UU. de 2,40 a 1,81 y Brasil de 3,12 a 0,62. Pero es una asociación ecológica con datos agregados: no prueba que la vacuna explique toda la caída. En Chile la señal se atenúa al superar el 50 % de cobertura, cerca del techo del 90 %, lo que sugiere que otros factores —variantes, testeo, comportamiento— también inciden. Distinguir correlación de causalidad es parte de la respuesta.
""")

# -------------------------------------------------------- 11 · extra ------
s = base("Extra · Restricciones: contexto, no causalidad",
         "Segunda fuente externa (OxCGRT): 182/218 países cruzan por ISO3 (83,5 %)", "EXTRA", 11)
image_fit(s, ROOT / "reports/fig_restricciones.png", 0.56, 1.85, 12.2, 4.3)
rect(s, 0.56, 6.12, 12.2, 0.34, WHITE, LINE, rounded=True)
textbox(s, 0.75, 6.17, 11.85, 0.26,
        "Chile: índice 90,3 (jul-2020) → media 24,3 en 2022; ómicron llegó con rigor 29 y 87 % vacunados. "
        "El índice mide lo anunciado, no su cumplimiento.",
        9.5, DARK)
notes(s, """
EXTRA (≈20 s, solo si hay tiempo). Integramos también el panel de Oxford: 202.760 filas país-día, 182 de 218 países del DW cruzan por ISO3. El índice de respuesta es 'de jure': codifica lo que se anunció, no su cumplimiento, y termina 68 días antes que la serie de JHU. En Chile el rigor máximo fue 90,3 en julio de 2020 y la media de 2022 bajó a 24,3; la ola de ómicron ocurrió con un índice de 29 y cerca del 87 % de la población vacunada. Es una asociación descriptiva: las restricciones suben porque hay casos y bajan cuando la situación lo permite, así que no sostenemos causalidad.
""")

# ------------------------------------------------------- 12 · tablero ----
s = base("El tablero que el Comité puede usar en vivo",
         "Streamlit · filtros por territorio y fecha sin tocar el código", "R7 · TABLERO", 12)
image_fit(s, ROOT / "dashboard/capturas/tablero_mundo.png", 0.56, 1.9, 5.95, 3.9)
image_fit(s, ROOT / "dashboard/capturas/tablero_chile.png", 6.81, 1.9, 5.95, 3.9)
cards = [
    ("KPI por 100.000", "con media móvil de 7 días"),
    ("Mapa mundial y de Chile", "georreferenciado con la tabla UID"),
    ("Alerta y advertencias", "umbral visible, corte y calidad"),
]
x = 0.56
for head, sub in cards:
    rect(s, x, 5.86, 3.93, 0.54, LIGHT, LINE, rounded=True)
    textbox(s, x + 0.2, 5.93, 3.6, 0.23, head, 10, RED, True)
    textbox(s, x + 0.2, 6.16, 3.6, 0.22, sub, 8.5, GRAY)
    x += 4.13
notes(s, """
TABLERO (≈30 s). Abrimos el tablero y filtramos en vivo: país o región de Chile y fecha, sin editar código. Muestra KPIs por 100.000, tendencia con media móvil, ranking con supresión de celdas pequeñas —menos de 5 se muestra como '<5'—, mapa mundial y mapa regional de Chile con la latitud y longitud de la tabla UID, y el indicador de alerta con su umbral, la fecha de corte y las advertencias de calidad. La captura también muestra la pestaña de calidad. Está verificado en navegador sin errores.
""")

# ------------------------------------------------------ 13 · desafío ------
s = base("Desafío en vivo: listos para el sorteo",
         "KPIs a la fecha → estado de la alerta → pronosticar(territorio, fecha_corte, 14)", "DESAFÍO", 13)
image_fit(s, ROOT / "dashboard/capturas/tablero_desafio.png", 0.56, 1.9, 7.4, 4.6)
pasos = [
    ("1 · FILTRAR", "Territorio y fecha de corte que sortee el Comité."),
    ("2 · LEER", "KPIs a esa fecha y si la alerta estaba activa."),
    ("3 · EJECUTAR", "pronosticar(territorio, fecha_corte, 14) sin ver el futuro."),
    ("4 · COMPARAR", "Resultado frente a lo ocurrido: error o anticipación."),
]
y = 1.95
for head, body in pasos:
    rect(s, 8.2, y, 4.56, 0.98, LIGHT, LINE, rounded=True)
    rect(s, 8.2, y, 0.06, 0.98, RED)
    textbox(s, 8.42, y + 0.08, 4.15, 0.26, head, 10.5, RED, True)
    textbox(s, 8.42, y + 0.38, 4.15, 0.52, body, 9.5, DARK)
    y += 1.06
textbox(s, 8.2, 6.18, 4.56, 0.26, "Sin fuga de datos: nada posterior al corte.", 9, GRAY, italic=True)
notes(s, """
DESAFÍO (se explica antes de que sorteen, ≈20 s). La pestaña 'Desafío en vivo' del tablero recibe el territorio y la fecha de corte; ahí leemos los KPIs a esa fecha y el estado de la alerta. Después ejecutamos pronosticar(territorio, fecha_corte, 14): la función filtra el histórico con fecha ≤ corte, usa dos modelos —media móvil y Holt— y devuelve 14 días. Finalmente comparamos con lo que realmente pasó. Cualquier integrante puede hacerlo: ninguna función ve datos posteriores al corte, y eso es justamente lo que el Comité comprueba.
""")

# ------------------------------------------------ 14 · recomendaciones ---
s = base("Tres recomendaciones para la próxima pandemia",
         "Cada una con evidencia del proyecto, indicador medible y responsable", "R8 · CIERRE", 14)
recs = [
    ("R1", "Plataforma auditada desde la semana 1",
     "Evidencia: cinco esquemas unificados, reglas ejecutadas en cada carga e índice de confiabilidad publicado. Las anomalías se marcan, nunca se arreglan en silencio.",
     "Indicador: % de días con datos consolidados en < 24 h — meta ≥ 99 %.\nResponsable: unidad de datos de salud + auditoría externa anual."),
    ("R2", "Alerta oficial evaluada antes de confiar en ella",
     "Evidencia: variación MA7 ≥ +30 % e incidencia ≥ 6/100.000 detectó 5/5 olas con 39–100 días de anticipación y una sola falsa alarma.",
     "Indicador: 100 % de olas con ≥ 14 días de aviso; < 2 falsas alarmas por trimestre.\nResponsable: inteligencia epidemiológica MINSAL."),
    ("R3", "Tablero público con calidad visible y supresión 1–4",
     "Evidencia: fecha de corte, advertencias por país y supresión de conteos pequeños (317 condados de EE.UU. con < 5.000 hab.).",
     "Indicador: 100 % de cifras con método y corte visibles.\nResponsable: comunicaciones + datos + Consejo Asesor."),
]
y = 1.82
for num, head, ev, ind in recs:
    rect(s, 0.56, y, 12.2, 1.36, LIGHT, LINE, rounded=True)
    rect(s, 0.56, y, 0.75, 1.36, RED)
    textbox(s, 0.7, y + 0.42, 0.5, 0.5, num, 22, WHITE, True, PP_ALIGN.CENTER)
    textbox(s, 1.55, y + 0.12, 10.9, 0.34, head, 14, DARK, True)
    textbox(s, 1.55, y + 0.5, 7.55, 0.78, ev, 9.5, GRAY)
    rect(s, 9.3, y + 0.48, 0.02, 0.82, LINE)
    textbox(s, 9.45, y + 0.48, 3.1, 0.85, ind, 8.8, RED, True)
    y += 1.50
notes(s, """
RECOMENDACIONES (≈60 s, el cierre del relato). No son genéricas: cada una sale de un resultado del proyecto y trae indicador y responsable. R1: la cadena auditada desde el día uno, con reglas visibles y anomalías marcadas, medida como porcentaje de días consolidados en menos de 24 horas. R2: una alerta oficial probada contra los tres años de historia antes de confiar en ella, con metas de anticipación y falsas alarmas, a cargo de inteligencia epidemiológica. R3: un tablero público que muestre la fecha de corte, las advertencias de calidad y la supresión de celdas pequeñas para proteger a comunas y condados; el cien por cien de las cifras debe llevar método y corte visibles.
""")

# ----------------------------------------------------------- 15 · cierre --
s = base("Preguntas", "Todos podemos explicar y ejecutar cualquier parte del proyecto", "CIERRE", 15)
rect(s, 0.56, 2.0, 12.2, 2.1, LIGHT, LINE, rounded=True)
rect(s, 0.56, 2.0, 0.09, 2.1, RED)
textbox(s, 1.0, 2.28, 11.3, 0.7, "Del dato a la decisión, con fecha de corte", 28, RED, True)
textbox(s, 1.0, 3.15, 11.3, 0.7,
        "1.143 reportes → calidad → DW → P1–P7 → alerta y pronóstico → tablero → 3 recomendaciones",
        13, DARK)
textbox(s, 0.56, 4.5, 12.2, 0.5,
        "Lo que no podamos explicar en la sesión se considera no realizado: preguntemos a cualquiera del equipo.",
        12, GRAY)
notes(s, """
CIERRE. Invitamos a las preguntas del Comité. Recordar que el trabajo fue revisado por todos y que cualquier integrante puede explicar ingesta, calidad, DW, modelos, tablero e informes, incluido el código. Si queda tiempo, reforzar que ninguna cifra fue tecleada a mano: todas salen del DW reproducible.
""")

# ------------------------------------------------------------ guardar -----
prs.core_properties.title = "Sala de crisis COVID-19 — Relato al Comité"
prs.core_properties.subject = "Sesión del Comité · 24-nov-2026 · Gestión de Datos IN1232C"
prs.core_properties.author = "Equipo Sala de crisis COVID-19"
prs.core_properties.keywords = "COVID-19, DuckDB, calidad de datos, tablero, alerta temprana"
prs.save(str(SALIDA))
print("Guardado:", SALIDA, "· diapositivas:", len(prs.slides._sldIdLst))
