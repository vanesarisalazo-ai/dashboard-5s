import base64
import csv
import html as H
import io
import math
import unicodedata
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

# ----------------------------------------------------------------------------
# CONFIGURACION (lo unico que normalmente tendras que tocar)
# ----------------------------------------------------------------------------
SHEET_ID = "1px3_kx45dam-C4HsNR5m5RLHFjMO1mfwFYAGK_FiCIk"
GID = "1035405662"          # numero de la pestana "Control innecesarios"
META = 0.60                 # meta de retiro o reubicacion
ZONA_HORARIA = "America/Lima"
ACTUALIZAR_CADA = "60s"     # cada cuanto se vuelve a leer la hoja

URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
HECHO = {"retirado", "reubicado"}
COLORES = ["#34D399", "#8B7CFF", "#FF8A75", "#FFC24B", "#38BDF8", "#F472B6", "#2DD4BF", "#A78BFA"]

st.set_page_config(page_title="Dashboard 5S", page_icon=":label:", layout="wide")


# ----------------------------------------------------------------------------
# LECTURA Y LIMPIEZA DE DATOS
# ----------------------------------------------------------------------------
def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


@st.cache_data(ttl=55, show_spinner=False)
def cargar_hoja():
    r = requests.get(URL, timeout=30)
    texto = r.content.decode("utf-8", errors="replace")
    if r.status_code != 200 or texto.lstrip().lower().startswith(("<!doctype", "<html")):
        raise RuntimeError(
            f"Google no dejo leer la hoja (codigo {r.status_code}). "
            "Revisa que este compartida como: Cualquier persona con el enlace -> Lector."
        )
    filas = list(csv.reader(io.StringIO(texto)))
    idx = None
    for i, fila in enumerate(filas):
        if fila and "tarjeta" in norm(fila[0]) and norm(fila[0]).startswith("n"):
            idx = i
            break
    if idx is None:
        raise RuntimeError("No encontre la fila de encabezados (la que empieza con 'N tarjeta').")
    enc = [h.strip() for h in filas[idx]]
    ancho = len(enc)
    datos = [(f + [""] * ancho)[:ancho] for f in filas[idx + 1:] if any(c.strip() for c in f)]
    return pd.DataFrame(datos, columns=enc)


def buscar(cols, *claves, excluir=()):
    for c in cols:
        n = norm(c)
        if all(k in n for k in claves) and not any(x in n for x in excluir):
            return c
    return None


def a_fecha(valor, mes_primero):
    s = str(valor).strip()
    if not s:
        return pd.NaT
    formatos = ["%m/%d/%Y", "%d/%m/%Y"] if mes_primero else ["%d/%m/%Y", "%m/%d/%Y"]
    formatos += ["%Y-%m-%d", "%d-%m-%Y"]
    for f in formatos:
        try:
            return pd.Timestamp(datetime.strptime(s, f))
        except ValueError:
            continue
    return pd.NaT


def preparar(df_crudo, hoy):
    cols = list(df_crudo.columns)
    mapa = {
        "tarjeta": cols[0],
        "area": buscar(cols, "area"),
        "desc": buscar(cols, "descripcion"),
        "destino": buscar(cols, "destino"),
        "estado": buscar(cols, "estado"),
        "retiro": buscar(cols, "fecha", "retiro"),
        "resp": buscar(cols, "responsable"),
        "fantes": buscar(cols, "foto", "antes"),
        "fdesp": buscar(cols, "foto", "despues"),
        "cond": buscar(cols, "condicion"),
    }
    obligatorias = ["area", "estado", "retiro", "resp"]
    faltan = [k for k in obligatorias if mapa[k] is None]
    if faltan:
        raise RuntimeError(
            "No encontre estas columnas en tu hoja: " + ", ".join(faltan)
            + ". No cambies los nombres de los encabezados."
        )
    d = pd.DataFrame()
    for k, c in mapa.items():
        d[k] = df_crudo[c].astype(str).str.strip() if c else ""
    d = d[d["tarjeta"] != ""].copy()
    d["area"] = d["area"].replace("", "Sin area")
    d["retiro_f"] = pd.to_datetime(d["retiro"].map(lambda v: a_fecha(v, mes_primero=True)))
    d["hecho"] = d["estado"].map(norm).isin(HECHO)
    d["vencida"] = (~d["hecho"]) & d["retiro_f"].notna() & (d["retiro_f"] < hoy)
    d["dias"] = (hoy - d["retiro_f"]).dt.days.fillna(0).astype(int)
    return d.reset_index(drop=True)


# ----------------------------------------------------------------------------
# ESTILOS (modo oscuro)
# ----------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');
.stApp, [data-testid="stAppViewContainer"] {
  background: radial-gradient(1100px 520px at 12% -10%, rgba(139,124,255,.16), transparent 60%),
              radial-gradient(900px 480px at 95% 0%, rgba(52,211,153,.10), transparent 55%),
              #0B1220;
}
[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 1180px; padding-top: 1.5rem; padding-bottom: 3rem; }
.stApp, .stApp label, .stApp p { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; }
.stApp label p, .stApp [data-testid="stWidgetLabel"] p { color: #C9D6E8 !important; font-weight: 600; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #8FA3BF !important; }
.d5s { font-family: 'Plus Jakarta Sans', system-ui, sans-serif; color: #E6EDF7; }
.d5s * { box-sizing: border-box; }
@keyframes rise { from { opacity: 0; transform: translateY(16px) } to { opacity: 1; transform: none } }
@keyframes growx { from { transform: scaleX(0) } to { transform: scaleX(1) } }
@keyframes growy { from { transform: scaleY(0) } to { transform: scaleY(1) } }
@keyframes draw { to { stroke-dashoffset: 0 } }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(52,211,153,.65) } 70% { box-shadow: 0 0 0 8px rgba(52,211,153,0) } 100% { box-shadow: 0 0 0 0 rgba(52,211,153,0) } }
@keyframes pulsered { 0% { box-shadow: 0 0 0 0 rgba(255,138,117,.6) } 70% { box-shadow: 0 0 0 7px rgba(255,138,117,0) } 100% { box-shadow: 0 0 0 0 rgba(255,138,117,0) } }
.d5s .rise { animation: rise .6s cubic-bezier(.2,.7,.2,1) both }
.d5s .growx { transform-origin: left center; animation: growx .9s cubic-bezier(.2,.7,.2,1) .35s both }
.d5s .growy { transform-origin: center bottom; animation: growy .8s cubic-bezier(.2,.7,.2,1) .35s both }
.d5s .draw { animation: draw 1.3s cubic-bezier(.2,.7,.2,1) .3s forwards }
.d5s .livered { animation: pulsered 2s infinite }
.d5s .lift { transition: transform .25s ease, box-shadow .25s ease }
.d5s .lift:hover { transform: translateY(-4px); box-shadow: 0 16px 36px rgba(0,0,0,.45) }
.d5s .row:hover td { background: #16233B }
.d5s .flex { display: flex; flex-wrap: wrap; gap: 20px; align-items: stretch }
.d5s .card { background: linear-gradient(180deg, #131E33, #0F182A); border: 1px solid #22314B; border-radius: 28px; padding: 26px 28px; box-shadow: 0 12px 32px rgba(0,0,0,.35) }
.d5s h2 { margin: 0; font-size: 20px; font-weight: 800; color: #F1F6FD }
.d5s .sub { margin: 4px 0 0; font-size: 14px; color: #8FA3BF; font-weight: 500 }
.d5s th { padding: 10px 14px; font-weight: 700; font-size: 12px; letter-spacing: .06em; border-bottom: 2px solid #22314B; text-align: left; color: #8FA3BF }
.d5s td { padding: 12px 14px; border-bottom: 1px solid #1A2840; font-size: 14px; color: #E6EDF7 }
@media (prefers-reduced-motion: reduce) { .d5s * { animation: none !important } .d5s .draw { stroke-dashoffset: 0 !important } }
</style>
"""


# ----------------------------------------------------------------------------
# PIEZAS DEL DASHBOARD
# ----------------------------------------------------------------------------
def svg_img(svg, w, h, alt=""):
    """Streamlit borra las etiquetas <svg>; como imagen incrustada si se muestran."""
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return (
        f'<img alt="{H.escape(alt)}" width="{w}" height="{h}" '
        f'src="data:image/svg+xml;base64,{b64}" style="display:block">'
    )


def ico(path, color, size=20):
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    )
    return svg_img(svg, size, size)


def kpi(delay, rgb, color, icono, valor, titulo, detalle):
    return f"""
<div class="rise lift" style="animation-delay:{delay}s;flex:1 1 170px;position:relative;overflow:hidden;background:linear-gradient(150deg,rgba({rgb},.24),rgba({rgb},.05) 72%);border:1px solid rgba({rgb},.40);border-radius:24px;padding:22px;display:flex;flex-direction:column;gap:6px">
  <div style="position:absolute;right:-30px;top:-30px;width:110px;height:110px;border-radius:50%;background:rgba({rgb},.22);filter:blur(18px)"></div>
  <div style="position:relative;width:38px;height:38px;border-radius:12px;background:rgba({rgb},.20);display:flex;align-items:center;justify-content:center">
    {ico(icono, color)}
  </div>
  <div style="position:relative;font-size:46px;font-weight:800;line-height:1.1;margin-top:8px;color:{color}">{valor}</div>
  <div style="position:relative;font-size:14px;font-weight:700;color:#E6EDF7">{titulo}</div>
  <div style="position:relative;font-size:13px;font-weight:500;color:#8FA3BF">{detalle}</div>
</div>"""


ICO_TAG = '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'
ICO_OK = '<polyline points="20 6 9 17 4 12"/>'
ICO_CHART = '<path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/>'
ICO_CLOCK = '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
ICO_LABEL = '<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.5"/>'


def construir_html(d, hoy):
    n = len(d)
    hechas = int(d["hecho"].sum())
    venc = int(d["vencida"].sum())
    pct = hechas / n if n else 0
    meta_n = math.ceil(META * n)
    faltan = max(0, meta_n - hechas)
    cumple = pct >= META
    estado_txt = "Cumple la meta" if cumple else "En camino"
    n_areas = d["area"].nunique()

    Co = 2 * math.pi * 88
    Ci = 2 * math.pi * 66
    meta_len = Co * META
    val_len = Ci * pct
    meta_arr = f"{meta_len:.2f} {Co:.2f}"
    val_arr = f"{val_len:.2f} {Ci:.2f}"

    msg = (
        f"Vas en <b style='color:#fff'>{pct:.0%}</b> de la meta del <b style='color:#fff'>{META:.0%}</b>. "
        + (
            f"Faltan <b style='color:#fff'>{faltan} tarjetas</b> por retirar o reubicar."
            if not cumple
            else "Ya alcanzaron la meta. Sigan con las pendientes."
        )
    )

    anillo_svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="210" height="210" viewBox="0 0 200 200">
<style>
@keyframes draw {{ to {{ stroke-dashoffset: 0 }} }}
.draw {{ animation: draw 1.3s cubic-bezier(.2,.7,.2,1) .3s forwards }}
@media (prefers-reduced-motion: reduce) {{ .draw {{ animation: none; stroke-dashoffset: 0 }} }}
</style>
<circle cx="100" cy="100" r="88" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="10"/>
<circle class="draw" cx="100" cy="100" r="88" fill="none" stroke="#FF8A75" stroke-width="10" stroke-linecap="round" stroke-dasharray="{meta_arr}" stroke-dashoffset="{meta_len:.2f}" transform="rotate(-90 100 100)" style="filter:drop-shadow(0 0 6px rgba(255,138,117,.55))"/>
<circle cx="100" cy="100" r="66" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="16"/>
<circle class="draw" cx="100" cy="100" r="66" fill="none" stroke="#34D399" stroke-width="16" stroke-dasharray="{val_arr}" stroke-dashoffset="{val_len:.2f}" transform="rotate(-90 100 100)" style="filter:drop-shadow(0 0 8px rgba(52,211,153,.7))"/>
</svg>"""
    anillo = svg_img(anillo_svg, 210, 210, f"Avance de {pct:.0%} frente a una meta de {META:.0%}")

    hero = f"""
<div class="rise" style="flex:1.4 1 520px;min-width:0;position:relative;overflow:hidden;background:linear-gradient(135deg,#1A2B55,#0E1730 70%);border:1px solid #2A3D6B;color:#fff;border-radius:28px;padding:32px;display:flex;flex-wrap:wrap;gap:28px;align-items:center;box-shadow:0 18px 44px rgba(0,0,0,.45)">
  <div style="position:absolute;right:-60px;top:-60px;width:240px;height:240px;border-radius:50%;background:rgba(139,124,255,.30);filter:blur(30px)"></div>
  <div style="position:absolute;left:-50px;bottom:-70px;width:200px;height:200px;border-radius:50%;background:rgba(52,211,153,.20);filter:blur(30px)"></div>
  <div style="position:relative;flex:1 1 260px;display:flex;flex-direction:column;gap:16px">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <div style="width:46px;height:46px;border-radius:14px;background:#34D399;display:flex;align-items:center;justify-content:center;box-shadow:0 0 22px rgba(52,211,153,.55)">
        {ico(ICO_LABEL, "#0B1220", 24)}
      </div>
      <span style="background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.14);border-radius:999px;padding:6px 14px;font-size:12px;font-weight:700;letter-spacing:.08em">5S · SEIRI · CLASIFICAR</span>
    </div>
    <div style="margin:0;font-size:38px;line-height:1.1;font-weight:800;color:#fff">Control de<br>tarjetas rojas</div>
    <p style="margin:0;font-size:16px;line-height:1.5;color:#B7C6D6;font-weight:500">{msg}</p>
  </div>
  <div style="position:relative;width:210px;height:210px;flex-shrink:0;margin:0 auto">
    {anillo}
    <div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center">
      <span style="font-size:44px;font-weight:800;line-height:1">{pct:.0%}</span>
      <span style="font-size:12px;color:#B7C6D6;font-weight:600;margin-top:4px">meta {META:.0%}</span>
    </div>
  </div>
</div>"""

    kpis = (
        '<div style="flex:1 1 380px;min-width:0;display:flex;flex-wrap:wrap;gap:16px">'
        + kpi(0.08, "52,211,153", "#34D399", ICO_TAG, n, "Etiquetadas", f"en {n_areas} áreas")
        + kpi(0.16, "139,124,255", "#A99BFF", ICO_OK, hechas, "Retiradas o reubicadas", f"meta: {meta_n} tarjetas")
        + kpi(0.24, "255,194,75", "#FFC24B", ICO_CHART, f"{pct:.0%}", "% logrado", f"{estado_txt} · meta {META:.0%}")
        + kpi(0.32, "255,122,102", "#FF8A75", ICO_CLOCK, venc, "Vencidas", "pasaron su fecha límite")
        + "</div>"
    )

    grupos = []
    for i, (area, g) in enumerate(d.groupby("area", sort=False)):
        grupos.append((area, len(g), int(g["hecho"].sum()), COLORES[i % len(COLORES)]))
    maxn = max([t for _, t, _, _ in grupos] or [1])

    cols_html = ""
    for area, t, hh, color in grupos:
        h = max(6, round(t / maxn * 160))
        cols_html += f"""
<div style="flex:1 1 0;min-width:0;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;gap:6px;height:100%">
  <span style="font-size:16px;font-weight:800;color:#F1F6FD">{t}</span>
  <div class="growy" style="width:100%;max-width:54px;border-radius:14px 14px 6px 6px;height:{h}px;background:linear-gradient(180deg,{color},{color}99);box-shadow:0 0 18px {color}55"></div>
  <span style="font-size:12px;font-weight:700;color:#8FA3BF;text-align:center;line-height:1.2;min-height:30px">{H.escape(area)}</span>
</div>"""

    barras_html = ""
    for area, t, hh, color in grupos:
        p = hh / t if t else 0
        barras_html += f"""
<div style="display:flex;flex-direction:column;gap:7px">
  <div style="display:flex;justify-content:space-between;gap:12px;font-size:14px;font-weight:700;color:#E6EDF7">
    <span>{H.escape(area)}</span>
    <span style="color:#8FA3BF;font-weight:600">{hh} de {t} · {p:.0%}</span>
  </div>
  <div style="position:relative;height:12px;background:#1B2840;border-radius:999px">
    <div class="growx" style="position:absolute;left:0;top:0;bottom:0;border-radius:999px;width:{p * 100:.1f}%;background:{color};box-shadow:0 0 12px {color}88"></div>
    <div style="position:absolute;left:{META * 100:.0f}%;top:-4px;bottom:-4px;width:3px;background:#FF8A75;border-radius:2px"></div>
  </div>
</div>"""

    graficos = f"""
<div class="flex" style="margin-top:20px">
  <div class="card rise" style="animation-delay:.2s;flex:1 1 420px;min-width:0;display:flex;flex-direction:column;gap:20px">
    <div><h2>Tarjetas por área</h2><p class="sub">Dónde se concentran los innecesarios</p></div>
    <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:10px;height:230px;padding-top:8px">{cols_html}</div>
  </div>
  <div class="card rise" style="animation-delay:.28s;flex:1 1 420px;min-width:0;display:flex;flex-direction:column;gap:18px">
    <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-start;gap:8px">
      <div><h2>Avance por área</h2><p class="sub">% retirado o reubicado frente a la meta</p></div>
      <span style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:700;color:#FF8A75;background:rgba(255,138,117,.14);border:1px solid rgba(255,138,117,.30);border-radius:999px;padding:6px 12px">
        <span style="width:3px;height:14px;background:#FF8A75;border-radius:2px"></span>Meta {META:.0%}
      </span>
    </div>
    {barras_html}
  </div>
</div>"""

    v = d[d["vencida"]].sort_values(["retiro_f", "tarjeta"]).head(10)
    filas = ""
    for _, r in v.iterrows():
        reub = norm(r["destino"]).startswith("reubic")
        dbg, dfg = ("rgba(56,189,248,.16)", "#7DD3FC") if reub else ("rgba(255,194,75,.16)", "#FFC24B")
        inicial = H.escape((r["resp"][:1] or "?").upper())
        lim = r["retiro_f"].strftime("%d/%m/%Y")
        filas += f"""
<tr class="row">
  <td style="font-weight:800">{H.escape(r['tarjeta'])}</td>
  <td style="font-weight:600">{H.escape(r['area'])}</td>
  <td>{H.escape(r['desc'])}</td>
  <td><span style="border-radius:999px;padding:4px 12px;font-size:13px;font-weight:700;background:{dbg};color:{dfg}">{H.escape(r['destino'] or '-')}</span></td>
  <td><span style="display:inline-flex;align-items:center;gap:8px;font-weight:600"><span style="width:28px;height:28px;border-radius:50%;background:#6D5DF6;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:13px;font-weight:800">{inicial}</span>{H.escape(r['resp'])}</span></td>
  <td>{lim}</td>
  <td><span style="display:inline-flex;align-items:center;gap:8px;background:rgba(255,138,117,.14);color:#FF8A75;border-radius:999px;padding:4px 12px;font-size:13px;font-weight:700"><span class="livered" style="width:8px;height:8px;border-radius:50%;background:#FF8A75"></span>{int(r['dias'])} días</span></td>
</tr>"""
    if not filas:
        filas = '<tr><td colspan="7" style="text-align:center;color:#8FA3BF;font-weight:600;padding:28px">No hay tarjetas vencidas. Buen trabajo.</td></tr>'

    tabla = f"""
<div class="card rise" style="animation-delay:.36s;margin-top:20px;display:flex;flex-direction:column;gap:16px">
  <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:10px">
    <div><h2>Tarjetas vencidas</h2><p class="sub">Pendientes de retiro o reubicación · las {min(10, venc)} más atrasadas</p></div>
    <span style="background:rgba(255,138,117,.14);border:1px solid rgba(255,138,117,.30);color:#FF8A75;border-radius:999px;padding:7px 14px;font-size:13px;font-weight:800">{venc} pendientes</span>
  </div>
  <div style="overflow-x:auto">
    <table style="width:100%;min-width:760px;border-collapse:separate;border-spacing:0">
      <thead><tr><th>N° TARJETA</th><th>ÁREA</th><th>DESCRIPCIÓN</th><th>DESTINO</th><th>RESPONSABLE</th><th>LÍMITE</th><th>RETRASO</th></tr></thead>
      <tbody>{filas}</tbody>
    </table>
  </div>
</div>"""

    return f'<div class="d5s"><div class="flex">{hero}{kpis}</div>{graficos}{tabla}</div>'


# ----------------------------------------------------------------------------
# PANTALLA
# ----------------------------------------------------------------------------
@st.fragment(run_every=ACTUALIZAR_CADA)
def tablero():
    hoy = pd.Timestamp.now(tz=ZONA_HORARIA).tz_localize(None).normalize()
    try:
        d = preparar(cargar_hoja(), hoy)
    except Exception as e:
        st.error(str(e))
        return

    c1, c2, c3, c4 = st.columns([2, 2, 1.4, 1])
    areas = c1.multiselect("Área", sorted(d["area"].unique()), placeholder="Todas las áreas")
    resps = c2.multiselect("Responsable", sorted(x for x in d["resp"].unique() if x), placeholder="Todos")
    est = c3.selectbox("Estado", ["Todas", "Pendientes", "Retiradas o reubicadas", "Vencidas"])
    c4.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if c4.button("Actualizar", use_container_width=True):
        cargar_hoja.clear()
        st.rerun(scope="fragment")

    if areas:
        d = d[d["area"].isin(areas)]
    if resps:
        d = d[d["resp"].isin(resps)]
    if est == "Pendientes":
        d = d[~d["hecho"]]
    elif est == "Retiradas o reubicadas":
        d = d[d["hecho"]]
    elif est == "Vencidas":
        d = d[d["vencida"]]

    if d.empty:
        st.info("No hay tarjetas con esos filtros.")
        return

    st.html(construir_html(d.reset_index(drop=True), hoy))
    st.caption(f"Datos leídos de Google Sheets · se actualiza solo cada {ACTUALIZAR_CADA} · hoy: {hoy:%d/%m/%Y}")


st.html(CSS)
tablero()
