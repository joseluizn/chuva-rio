#!/usr/bin/env python3
"""Gera site/completo.html (versão completa/exploratória do dashboard de chuva no Rio).

Somente biblioteca padrão. Idempotente: a mesma entrada produz o mesmo arquivo.
Uso: python3 scripts/build_full.py
"""
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY = os.path.join(ROOT, "data", "daily")
REFS = os.path.join(ROOT, "data", "refs")
OUT = os.path.join(ROOT, "site", "completo.html")
REPO = "https://github.com/joseluizn/chuva-rio"
T0 = "1995-01-01"


# ---------------------------------------------------------------- carga
def load_series(name):
    rows = list(csv.reader(open(os.path.join(DAILY, name + ".csv"), encoding="utf-8")))[1:]
    dates = [r[0] for r in rows]
    vals = []
    for r in rows:
        v = r[1].strip()
        vals.append(-1 if v == "" else int(round(float(v) * 10)))
    return dates, vals


def days_between(d0, d1):
    import datetime as dt
    a = dt.date.fromisoformat(d0)
    b = dt.date.fromisoformat(d1)
    return (b - a).days


def build_data():
    ser = {}
    dates = None
    for key, f in (("era5", "era5"), ("ifs", "ecmwf_ifs"), ("bm", "best_match")):
        d, v = load_series(f)
        if dates is None:
            dates = d
        elif d != dates:
            sys.exit("datas divergentes entre arquivos")
        ser[key] = v
    if dates[0] != T0 or len(dates) != days_between(dates[0], dates[-1]) + 1:
        sys.exit("série diária não é contígua a partir de 1995-01-01")
    # verifica a emenda de best_match (descontinuidade de 2017)
    cut = dates.index("2017-01-01")
    ok = all(ser["bm"][i] == ser["era5"][i] for i in range(cut)) and all(
        ser["bm"][i] == ser["ifs"][i] for i in range(cut, len(dates)))
    if not ok:
        print("AVISO: best_match deixou de ser ERA5 (<2017) + IFS (>=2017); o texto sobre a emenda precisa de revisão",
              file=sys.stderr)
    return dates, ser


def mean(x):
    return sum(x) / len(x)


def year_stats(dates, vals, thr_tenths=10):
    """total mm e dias >= limiar por ano civil completo (1995-2025)."""
    tot, wet, n = {}, {}, {}
    for d, v in zip(dates, vals):
        y = int(d[:4])
        if v < 0:
            continue
        n[y] = n.get(y, 0) + 1
        tot[y] = tot.get(y, 0) + v / 10
        if v >= thr_tenths:
            wet[y] = wet.get(y, 0) + 1
    return tot, wet, n


# ---------------------------------------------------------------- cor (OKLab)
def _lin2srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _srgb2lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def oklch_to_rgb(L, C, h):
    a = C * math.cos(math.radians(h))
    b = C * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    bb = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_
    return [round(_lin2srgb(x) * 255) for x in (r, g, bb)]


def rel_lum(rgb):
    r, g, b = [_srgb2lin(c / 255) for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def hex2rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def make_hue_ramp(hue, chroma, n=33):
    """Rampa sequencial (claro e escuro) de uma matiz, mais escuro = mais; contraste >= 3:1 no extremo baixo."""
    light, dark = [], []
    for i in range(n):
        t = i / (n - 1)
        light.append(oklch_to_rgb(0.645 - 0.405 * t, chroma * (1 + 0.7 * math.sin(math.pi * t)), hue))
        dark.append(oklch_to_rgb(0.92 - 0.50 * t, chroma * (0.7 + 1.5 * t), hue))
    s_light, s_dark = hex2rgb("#fcfcfb"), hex2rgb("#1a1a19")
    if contrast(light[0], s_light) < 3 or contrast(dark[0], s_dark) < 3:
        sys.exit(f"rampa de matiz {hue} sem contraste 3:1 no extremo baixo")
    return {"light": light, "dark": dark}


def make_ramps(n=33):
    """Rampa sequencial (matiz azul) com L linear em OKLab: uniforme por construção.
    Extremo baixo com contraste >= 3:1 contra a superfície de cada tema (WCAG 1.4.11)."""
    light, dark = [], []
    for i in range(n):
        t = i / (n - 1)
        light.append(oklch_to_rgb(0.645 - 0.405 * t, 0.075 + 0.055 * math.sin(math.pi * t), 250))
        dark.append(oklch_to_rgb(0.92 - 0.50 * t, 0.05 + 0.11 * t, 250))  # azul mais escuro = mais chuva, nos dois temas
    s_light, s_dark = hex2rgb("#fcfcfb"), hex2rgb("#1a1a19")
    cl, cd = contrast(light[0], s_light), contrast(dark[0], s_dark)
    if cl < 3 or cd < 3:
        sys.exit(f"rampa sem contraste 3:1 no extremo baixo (claro {cl:.2f}, escuro {cd:.2f})")
    return light, dark, round(cl, 2), round(cd, 2)


# ---------------------------------------------------------------- texto metodológico
def br(x, d=0):
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def sbr(x, d=0):
    return ("+" if x >= 0 else "−") + br(abs(x), d)


def pt_date(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[:4]}"


def derive(dates, ser):
    """Tudo que depende dos dados é derivado aqui (a Action mensal roda sem argumentos)."""
    last = dates[-1]
    ly = int(last[:4])
    complete = last == f"{ly}-12-31"
    ylast = ly if complete else ly - 1
    ypart = None if complete else ly
    first_ifs = next(i for i, v in enumerate(ser["ifs"]) if v >= 0)
    first_diff = next((i for i in range(len(dates)) if ser["bm"][i] != ser["era5"][i]), None)
    trailing = 0
    for v in reversed(ser["era5"]):
        if v < 0:
            trailing += 1
        else:
            break
    return dict(last=last, ylast=ylast, ypart=ypart, y0=int(dates[0][:4]),
                ifs0=dates[first_ifs], ifs_year0=int(dates[first_ifs][:4]) + (0 if dates[first_ifs][5:] == "01-01" else 1),
                splice=None if first_diff is None else dates[first_diff], era5_trailing=trailing)


def cloud_method_html(dates):
    cl = C.load_cloud()
    assert [c[0].isoformat() for c in cl] == dates, "datas da nebulosidade divergem das da chuva"
    years = [y for y in range(int(dates[0][:4]), int(dates[-1][:4]) + 1) if y < int(dates[-1][:4]) or dates[-1].endswith("-12-31")]
    sun = C.sun_fraction_stats(cl, years)
    ms = C.monthly_sun_fraction(cl, years)
    last = max(c[0] for c in cl if c[4] is not None).isoformat()
    meta_c = json.load(open(os.path.join(DAILY, "meta.json"), encoding="utf-8")).get("cloud", {})
    return (f"<p>Variável horária <code>cloud_cover</code> (cobertura total de nuvens, %) do ERA5 via Open-Meteo, na mesma célula da chuva "
            f"({br(meta_c.get('returned_latitude', float('nan')), 2)}; {br(meta_c.get('returned_longitude', float('nan')), 2)}), com valores até {pt_date(last)}. "
            f"<strong>Nebulosidade diurna</strong> = média das 9 horas locais de 09 a 17 h (a média de 24 h inclui a noite). "
            f"<strong>Dia de céu aberto</strong> = nebulosidade diurna ≤ limiar escolhido no controle da barra superior; o padrão é {br(C.OPEN_THR)}%, "
            f"que corresponde à classe “clear” do NOAA/NCEI (cobertura média do céu de 0 a 3/10 nas horas de luz; parcialmente nublado = 4–7/10, "
            f"nublado = 8–10/10; <a href=\"{C.NCEI_URL}\">Comparative Climatic Data</a>). O limiar é convencional: "
            f"as frequências mudam bastante com ele, e o controle serve para ver essa sensibilidade. A nebulosidade do ERA5 é saída de modelo, "
            f"não observação, e não achei referência observada para conferi-la; ela é sempre do ERA5, mesmo quando a fonte de chuva é outra. "
            f"Médias por mês usam anos completos; mediana e p10–p90 são entre anos.</p>"
            f"<p><strong>Insolação checada e descartada.</strong> A fração de insolação do ERA5 (<code>sunshine_duration</code> ÷ <code>daylight_duration</code>) "
            f"é quase constante no ano (médias mensais de {br(min(ms), 2)} a {br(max(ms), 2)}; média geral {br(sun['mean_fraction'], 2)}) e correlaciona só "
            f"r = {br(sun['r'], 2)} com a nebulosidade diurna diária; por isso não é oferecida como definição de céu aberto "
            f"(<a href=\"{REPO}/blob/main/docs/modelo_periodos.md\">docs/modelo_periodos.md</a>).</p>")


def method_html(meta, refs, ser, dates, cl, cd, dv):
    cloud_html = cloud_method_html(dates)
    era_t, era_w, era_n = year_stats(dates, ser["era5"])
    ifs_t, ifs_w, _ = year_stats(dates, ser["ifs"])
    y0, yl = dv["y0"], dv["ylast"]
    ya, yb = 1997, min(2024, yl)  # período da referência Alerta Rio (estático)
    era_mean = mean([era_t[y] for y in range(ya, yb + 1)])
    aler = refs["alertario"]["annual_mm"]
    vies_vol = (era_mean / aler - 1) * 100
    era_w_mean = mean([era_w[y] for y in range(y0, yl + 1)])
    inmet_w = refs["inmet"]["annual_wet_days"]
    vies_freq = (era_w_mean / inmet_w - 1) * 100
    gal = json.load(open(os.path.join(REFS, "galeao_ghcn.json"), encoding="utf-8"))["years"]
    gal_txt = []
    for y in sorted(gal):
        g = gal[y]
        if int(y) > yl:
            continue
        gal_txt.append(
            f"{y}: ERA5 {br(era_t[int(y)])} mm e {era_w[int(y)]} dias contra {br(g['total_mm'], 1)} mm e "
            f"{g['wet_days_ge1']} dias no Galeão ({sbr((era_t[int(y)] / g['total_mm'] - 1) * 100)}% em volume, "
            f"{sbr((era_w[int(y)] / g['wet_days_ge1'] - 1) * 100)}% em dias)")
    iy = [y for y in range(dv["ifs_year0"], yl + 1) if y in ifs_t and y in era_t]
    ratios = [ifs_t[y] / era_t[y] for y in iy]
    ifs_ratio = sum(ifs_t[y] for y in iy) / sum(era_t[y] for y in iy)
    m = meta["models"]
    nd = len(dates)
    cnt = {k: sum(1 for v in ser[kk] if v >= 0) for k, kk in (("era5", "era5"), ("ecmwf_ifs", "ifs"), ("best_match", "bm"))}
    ncomp = yl - y0 + 1
    era_last = next(dates[i] for i in range(len(dates) - 1, -1, -1) if ser["era5"][i] >= 0)  # última data com valor do ERA5
    part = (f"{dv['ypart']} (parcial, até {pt_date(era_last)[:5]})" if dv["ypart"] else "")
    splice = pt_date(dv["splice"]) if dv["splice"] else "nenhuma"

    def cell(k):
        x = m[k]
        return f"{x['returned_latitude']:.4f}, {x['returned_longitude']:.4f} (elevação {x['elevation_m']:.0f} m)"

    km = abs(m['era5']['returned_latitude'] - meta['requested']['latitude']) * 111
    trail = (f"; os últimos {dv['era5_trailing']} dias estão ausentes" if dv["era5_trailing"] else "")
    return f"""
<details class="method" id="metodo">
<summary>Nota metodológica (fonte, células, viés, estatística)</summary>
<div class="mbody">
<p class="attrib">Dados: <a href="https://open-meteo.com/">Open-Meteo.com</a> (<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>), reanálise ERA5 e ECMWF IFS — Copernicus/ECMWF. Nebulosidade e insolação: ERA5 via Open-Meteo, CC BY 4.0.</p>
<h3>Fonte dos dados</h3>
<p>Precipitação diária (<code>precipitation_sum</code>, mm, fuso {meta['requested']['timezone']}) da API de arquivo histórico da
Open-Meteo, consultada em {pt_date(meta['accessed'])} para o ponto solicitado ({br(meta['requested']['latitude'], 4)}; {br(meta['requested']['longitude'], 4)}),
de {pt_date(dates[0])} a {pt_date(dv['last'])}.
URL-base: <code>https://archive-api.open-meteo.com/v1/archive</code> (parâmetros <code>models=era5</code>,
<code>ecmwf_ifs</code> e <code>best_match</code>). A série é de <strong>reanálise/modelo em grade</strong>, não de pluviômetro.
As URLs exatas de cada consulta estão em <a href="{REPO}/blob/main/data/daily/meta.json">data/daily/meta.json</a>.</p>
<table class="mt"><thead><tr><th>Modelo</th><th>Célula retornada (lat, lon)</th><th>Dias com valor</th><th>Observação</th></tr></thead><tbody>
<tr><td>ERA5</td><td>{cell('era5')}</td><td>{br(cnt['era5'])}</td><td>série homogênea (produto único){trail}</td></tr>
<tr><td>ECMWF IFS</td><td>{cell('ecmwf_ifs')}</td><td>{br(cnt['ecmwf_ifs'])}</td><td>somente a partir de {pt_date(dv['ifs0'])}</td></tr>
<tr><td>best_match</td><td>{cell('best_match')}</td><td>{br(cnt['best_match'])}</td><td>igual ao ERA5 antes de {splice} e ao IFS a partir dessa data: emenda artificial</td></tr>
<tr><td>ERA5-Land</td><td>{cell('era5_land')}</td><td>{br(m['era5_land']['days'] - m['era5_land']['null_days'])}</td><td>{'a API devolveu todos os valores nulos neste ponto; não usado' if m['era5_land']['null_days'] == m['era5_land']['days'] else 'não usado nesta página'}</td></tr>
</tbody></table>
<p>As células do ERA5 (~25 km) e do IFS (~9 km) diferem entre si e nenhuma é o ponto pedido: cada valor é uma média espacial
sobre a célula (a latitude do ERA5 difere do ponto em ~{km:.0f} km).</p>

<h3>Viés frente a observações (recalculado a cada geração da página)</h3>
<ul>
<li><strong>Volume:</strong> média anual do ERA5 em {ya}–{yb} = {br(era_mean)} mm contra {br(aler, 1)} mm da rede Alerta Rio (média de 33 pluviômetros, 1997–2024): <strong>{sbr(vies_vol)}%</strong>.</li>
<li><strong>Frequência:</strong> o ERA5 tem em média {br(era_w_mean, 0)} dias/ano com chuva ≥ 1 mm ({y0}–{yl}) contra {inmet_w} da normal do INMET (Saúde): <strong>{sbr(vies_freq)}%</strong>. Os períodos diferem ({refs['inmet']['period_note']}).</li>
<li><strong>Galeão (NOAA GHCN, ponto único):</strong> {'; '.join(gal_txt)}. Só estes anos têm cobertura &gt; 95%.</li>
<li><strong>IFS/ERA5:</strong> em {iy[0]}–{iy[-1]} o IFS soma {br(ifs_ratio * 100)}% do volume do ERA5 (razão anual entre {br(min(ratios), 2)} e {br(max(ratios), 2)}).</li>
</ul>
<p>As referências Alerta Rio e INMET estão marcadas como “referência, não conferida” em <code>data/refs/refs.json</code>
(lidas por resumo automático do PDF e da Wikipédia). Os valores anuais de 2024 e 2025 do Alerta Rio usados na aba Fontes
(1.198,2 e 890,9 mm) são aproximados. Nenhuma referência é a célula do modelo: a comparação é indicativa. O ERA5 serve para
<em>variação relativa</em>; os volumes absolutos têm viés úmido.</p>

<h3>Definições</h3>
<ul>
<li><strong>Ano e período.</strong> Médias e totais usam os {ncomp} anos civis completos ({y0}–{yl}). {('O ano ' + part + ' é sempre marcado e nunca entra em médias, faixas, testes ou cumulativos de referência. ') if part else ''}Um ano só é usado se a fonte tiver ≥ 98% dos dias.</li>
<li><strong>Dia chuvoso:</strong> precipitação diária ≥ limiar escolhido (0,1; 1; 5; 10 ou 25 mm). <strong>Volume</strong> = soma de todos os dias (independe do limiar). <strong>Frequência</strong> = número de dias chuvosos. <strong>Intensidade</strong> = mm nos dias chuvosos ÷ número de dias chuvosos (indefinida se não há dia chuvoso).</li>
<li><strong>Participação mensal:</strong> volume (ou dias chuvosos) do mês ÷ total do mesmo ano; a mediana e a faixa p10–p90 (interpolação linear) são tomadas <em>entre anos</em>. Em % do total anual o viés multiplicativo do modelo se cancela em boa parte.</li>
<li><strong>Estação chuvosa:</strong> out–mar contra abr–set agrupados <em>por ano civil</em> (jan–mar e out–dez do mesmo ano), de modo que as participações somem 100% em cada ano.</li>
<li><strong>Calendário (mês × dia):</strong> cada célula combina os mesmos dias do ano ao longo dos anos selecionados. A suavização soma numeradores e denominadores numa janela circular de ±3 ou ±7 dias (atravessa meses e a virada do ano) e depois divide. O diagnóstico de ruído é a razão entre a variância observada das frequências diárias dentro de cada mês e a variância binomial esperada para o mesmo n de anos; razão próxima de 1 indica que a estrutura dia a dia é compatível com ruído amostral.</li>
<li><strong>Períodos A × B:</strong> diferença das médias por mês (ou grupo), com intervalo percentil de 95% obtido por <strong>bootstrap em blocos de ano</strong>: reamostram-se anos inteiros, com reposição, dentro de A e dentro de B, separadamente, e os mesmos anos reamostrados valem para todos os meses (preserva a covariância entre meses de um mesmo ano). 1.000 reamostragens, gerador pseudoaleatório com semente fixa (resultado reprodutível). Com menos de 10 anos em um período o intervalo é pouco confiável; ele não corrige comparações múltiplas (com 12 meses mais o ano, espera-se que cerca de 0,6 intervalo exclua o zero só por acaso).</li>
<li><strong>Cumulativo:</strong> soma ao longo do dia do ano (dia 1 = 1º de jan); em anos bissextos a data real se desloca 1 dia após fevereiro.</li>
</ul>

<h3>Nebulosidade e dias de céu aberto</h3>
{cloud_html}
<h3>Cuidados de leitura</h3>
<ul>
<li>Uma única célula de grade, poucas décadas e forte variabilidade interanual: diferenças entre períodos são frequentemente indistinguíveis do acaso. A queda de patamar aparente do best_match após a emenda é em boa parte troca de produto, não clima (detalhes e testes de permutação em <a href="{REPO}/blob/main/docs/analise_modelos.md">docs/analise_modelos.md</a>).</li>
<li>Muitos controles significam muitas comparações possíveis. Esta página é exploratória: trate achados como hipóteses.</li>
<li>Extremos diários em grade subestimam picos pontuais de pluviômetro.</li>
</ul>
<p>Análise completa dos modelos e da emenda: <a href="{REPO}/blob/main/docs/analise_modelos.md">docs/analise_modelos.md</a>.
Código: <a href="{REPO}">github.com/joseluizn/chuva-rio</a>. Contraste do extremo baixo da escala de cor: {cl}:1 (claro) e {cd}:1 (escuro) contra a superfície do gráfico.</p>
</div>
</details>
"""


# ---------------------------------------------------------------- montagem
def main():
    dates, ser = build_data()
    meta = json.load(open(os.path.join(DAILY, "meta.json"), encoding="utf-8"))
    refs = json.load(open(os.path.join(REFS, "refs.json"), encoding="utf-8"))
    gal = json.load(open(os.path.join(REFS, "galeao_ghcn.json"), encoding="utf-8"))
    light, dark, cl, cd = make_ramps()
    ramp_open = make_hue_ramp(165, 0.075)
    ramp_cloud = make_hue_ramp(250, 0.012)
    dv = derive(dates, ser)
    cloud = C.load_cloud()
    if [c[0].isoformat() for c in cloud] != dates:
        sys.exit("datas da nebulosidade divergem das da chuva")
    opts = sorted({10.0, 20.0, C.OPEN_THR, 40.0, 50.0})

    data = {"t0": T0, "n": len(dates), "last": dates[-1], "accessed": meta["accessed"],
            "ylast": dv["ylast"], "ypart": dv["ypart"], "ifs0": dv["ifs0"], "splice": dv["splice"],
            "era5": ser["era5"], "ifs": ser["ifs"], "bm": ser["bm"],
            "cl": C.encode_cloud_tenths(cloud), "openThr": C.OPEN_THR, "openOpts": opts}
    ref = {
        "alertario": {k: refs["alertario"][k] for k in ("monthly_mm", "annual_mm", "label")},
        "inmet": {k: refs["inmet"][k] for k in ("monthly_mm", "annual_mm", "wet_days", "annual_wet_days", "label")},
        "galeao": gal["years"],
        "alertario_anos": {"2024": 1198.2, "2025": 890.9},
    }
    html = TEMPLATE
    html = html.replace("/*__DATA__*/", json.dumps(data, separators=(",", ":")))
    html = html.replace("/*__REF__*/", json.dumps(ref, ensure_ascii=False, separators=(",", ":")))
    html = html.replace("/*__RAMP__*/", json.dumps({"light": light, "dark": dark, "open": ramp_open, "cloud": ramp_cloud}, separators=(",", ":")))
    html = html.replace("<!--__METHOD__-->", method_html(meta, refs, ser, dates, cl, cd, dv))
    html = html.replace("__ACCESSED__", meta["accessed"]).replace("__NCEI__", C.NCEI_URL)
    html = html.replace("__REPO__", REPO)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"escrito {OUT} ({len(html) / 1024:.0f} KB); contraste extremo baixo da rampa: {cl}:1 claro, {cd}:1 escuro")


TEMPLATE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "full_template.html"), encoding="utf-8").read() \
    if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), "full_template.html")) else ""

if __name__ == "__main__":
    main()
