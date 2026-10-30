/* Ventanilla de consulta SAT — React clásico + Apache ECharts, estilos del Kit UNAL. */
const { useState, useMemo, useEffect, useRef } = React;

const META = window.SAT_META, EST = window.SAT_EST, ASIG = window.SAT_ASIG, NOTAS = window.SAT_NOTAS, FICHA = window.SAT_FICHA, RIESGO = window.SAT_RIESGO, PARC = window.SAT_PARCIALES;
const NIV = ['Bajo', 'Medio', 'Alto'];
const COLOR = ['#289a64', '#d49d00', '#d40f00'];

/* ------------------------------------------------------------ utilidades */
const nf = (n, d = 0) => n == null ? '—' : Number(n).toLocaleString('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d });
const pc = (n, d = 1) => n == null ? '—' : nf(n, d);
const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

function csv(nombre, cols, filas) {
  const q = v => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  const t = '﻿' + [cols.map(c => q(c.t)).join(';')].concat(filas.map(f => cols.map(c => q(c.v(f))).join(';'))).join('\r\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([t], { type: 'text/csv;charset=utf-8' }));
  a.download = nombre + '.csv'; a.click(); URL.revokeObjectURL(a.href);
}

/* Índices construidos una vez */
/* Origen según departamento y municipio de procedencia: 0 Valle de Aburrá, 1 foráneo (otro municipio), 2 sin dato. */
const VALLE = new Set(['Barbosa', 'Bello', 'Caldas', 'Copacabana', 'Envigado', 'Girardota', 'Itagüí', 'La Estrella', 'Medellín', 'Sabaneta']);
const ORIGEN = {};
{
  const [cd, cm] = [FICHA.campos[20][2], FICHA.campos[21][2]];
  EST.forEach((e, i) => {
    const f = FICHA.filas[i], d = f && f[20], m = f && f[21];
    ORIGEN[e[0]] = d == null || m == null || d < 0 || m < 0 ? 2 : (cd[d] === 'Antioquia' && VALLE.has(cm[m]) ? 0 : 1);
  });
}

const NOTAS_POR_EST = {}, NOTAS_POR_ASIG = {};
NOTAS.forEach(n => { (NOTAS_POR_EST[n[0]] = NOTAS_POR_EST[n[0]] || []).push(n); (NOTAS_POR_ASIG[ASIG[n[1]][0]] = NOTAS_POR_ASIG[ASIG[n[1]][0]] || []).push(n); });
const UABS = [...new Set(ASIG.map(a => a[2]).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'es'));

/* ------------------------------------------------------------ componentes */
const Icono = ({ n }) => <span className="material-symbols-outlined" aria-hidden="true" style={{ fontSize: 18 }}>{n}</span>;
const Nivel = ({ n }) => <span className={'niv n' + n}>{NIV[n]}</span>;

function Grafico({ opcion, alto = 340, onClick }) {
  const ref = useRef(null), ch = useRef(null);
  useEffect(() => {
    ch.current = echarts.init(ref.current);
    const rs = () => ch.current.resize(); window.addEventListener('resize', rs);
    return () => { window.removeEventListener('resize', rs); ch.current.dispose(); };
  }, []);
  useEffect(() => {
    ch.current.setOption(opcion, true);
    ch.current.off('click'); if (onClick) ch.current.on('click', onClick);
  }, [opcion]);
  return <div ref={ref} className="dsh-grafico" style={{ height: alto }} role="img" aria-label="Gráfico" />;
}

function Tabla({ cols, filas, orden0, onFila, nombreCsv, tope = 200, vacio = 'Sin resultados con los filtros actuales.' }) {
  const [ord, setOrd] = useState(orden0 || { k: 0, d: -1 });
  const [mas, setMas] = useState(tope);
  useEffect(() => setMas(tope), [filas]);
  const orden = useMemo(() => {
    const c = cols[ord.k], f = c.s || c.v;
    return [...filas].sort((a, b) => {
      const x = f(a), y = f(b);
      if (x == null) return 1; if (y == null) return -1;
      return (typeof x === 'string' ? x.localeCompare(y, 'es') : x - y) * ord.d;
    });
  }, [filas, ord]);
  return <>
    <div className="dsh-card-h">
      <span className="dsh-conteo">{nf(filas.length)} registros</span>
      {nombreCsv && <div className="dsh-acc"><button className="dsh-btn" style={{ padding: '.35rem .8rem', fontSize: '.8rem' }}
        onClick={() => csv(nombreCsv, cols, orden)}><Icono n="download" />Descargar CSV</button></div>}
    </div>
    {filas.length === 0 ? <p className="dsh-vacio">{vacio}</p> :
      <div className="dsh-tabla-wrap"><table className="dsh-tabla fijo" style={{ minWidth: cols.reduce((a, c) => a + (c.w || 190), 0) }}>
        <colgroup>{cols.map((c, i) => <col key={i} style={c.w ? { width: c.w + 'px' } : c.f ? { width: c.f + '%' } : null} />)}</colgroup>
        <thead><tr>{cols.map((c, i) => <th key={i} className={c.izq ? 'izq' : ''} onClick={() => setOrd(o => ({ k: i, d: o.k === i ? -o.d : -1 }))}>
          {c.t} {ord.k === i && <span className="ord">{ord.d < 0 ? '▼' : '▲'}</span>}</th>)}</tr></thead>
        <tbody>{orden.slice(0, mas).map((f, j) => <tr key={j} className={onFila ? 'clic' : ''} onClick={onFila ? () => onFila(f) : undefined}>
          {cols.map((c, i) => <td key={i} className={(c.izq ? 'izq ' : '') + 'num'} style={c.izq ? { whiteSpace: 'normal' } : null}>{c.r ? c.r(f) : c.v(f)}</td>)}</tr>)}</tbody>
      </table></div>}
    {mas < orden.length && <p className="dsh-ayuda">Se muestran {nf(mas)} de {nf(orden.length)}. <button className="dsh-limpiar-sel" onClick={() => setMas(m => m + tope)}>Mostrar más</button></p>}
  </>;
}

const IC = {
  visto: 'M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2Z',
  circulo: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm0 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm-1-5h2v2h-2v-2Zm0-8h2v6h-2V7Z',
  tasa: 'M3.5 18.5 9 13l4 4 7.5-7.5-1.4-1.4L13 14.2l-4-4-6.9 6.9 1.4 1.4Z',
  doc: 'M6 2h9l5 5v15H6V2Zm8 1.5V8h4.5L14 3.5ZM8 12h8v1.6H8V12Zm0 3.4h8V17H8v-1.6Z',
  malla: 'M3 3h8v8H3V3Zm10 0h8v8h-8V3ZM3 13h8v8H3v-8Zm10 0h8v8h-8v-8Z',
  persona: 'M12 12a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0 2c-5 0-9 2.5-9 5.5V22h18v-2.5c0-3-4-5.5-9-5.5Z'
};
const Kpi = ({ ic, color, lab, val, pie }) => <div className="dsh-kpi">
  <span className="dsh-kpi-ic" style={{ background: color }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d={IC[ic]} /></svg></span>
  <span><span className="dsh-kpi-lab">{lab}</span><span className="dsh-kpi-val">{val}</span>{pie && <span className="dsh-kpi-pie">{/^[\d—]/.test(pie) ? 'Porcentaje ' + pie : pie}</span>}</span></div>;

const Segmento = ({ valor, op, onCambio }) => <div className="dsh-segmento" role="group">
  {op.map(([v, t]) => <button key={v} aria-pressed={valor === v} onClick={() => onCambio(v)}>{t}</button>)}</div>;

/* ------------------------------------------------------------ ingreso */
/* Huella SHA-256 (puro JS, funciona también en HTTP). Solo se guarda la huella de usuario y contraseña. */
const _P = []; for (let n = 2; _P.length < 64; n++) if (_P.every(p => n % p)) _P.push(n);
const _K = _P.map(p => Math.floor((Math.cbrt(p) % 1) * 2 ** 32)), _H0 = _P.slice(0, 8).map(p => Math.floor((Math.sqrt(p) % 1) * 2 ** 32));
function sha256hex(txt) {
  const b = new TextEncoder().encode(txt), l = b.length, nb = ((l + 9 + 63) >> 6) << 6, m = new Uint8Array(nb); m.set(b); m[l] = 0x80;
  const dv = new DataView(m.buffer); dv.setUint32(nb - 4, (l * 8) >>> 0); dv.setUint32(nb - 8, Math.floor(l * 8 / 2 ** 32));
  const h = _H0.slice(), w = new Uint32Array(64), rr = (x, n) => (x >>> n) | (x << (32 - n));
  for (let i = 0; i < nb; i += 64) {
    for (let t = 0; t < 16; t++) w[t] = dv.getUint32(i + t * 4);
    for (let t = 16; t < 64; t++) { const s0 = rr(w[t - 15], 7) ^ rr(w[t - 15], 18) ^ (w[t - 15] >>> 3), s1 = rr(w[t - 2], 17) ^ rr(w[t - 2], 19) ^ (w[t - 2] >>> 10); w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0; }
    let [a, bb, c, d, e, f, g, hh] = h;
    for (let t = 0; t < 64; t++) {
      const t1 = (hh + (rr(e, 6) ^ rr(e, 11) ^ rr(e, 25)) + ((e & f) ^ (~e & g)) + _K[t] + w[t]) >>> 0, t2 = ((rr(a, 2) ^ rr(a, 13) ^ rr(a, 22)) + ((a & bb) ^ (a & c) ^ (bb & c))) >>> 0;
      hh = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = bb; bb = a; a = (t1 + t2) >>> 0;
    }
    [a, bb, c, d, e, f, g, hh].forEach((v, k) => { h[k] = (h[k] + v) >>> 0; });
  }
  return h.map(x => x.toString(16).padStart(8, '0')).join('');
}
const HUELLA_ACCESO = "c682b4febe09ab126f1e2202282fead927069c0d18402c6187f6f4b5d3a2ef43";

function Ingreso({ onEntrar }) {
  const [u, setU] = useState(''), [p, setP] = useState(''), [ver, setVer] = useState(false), [ok, setOk] = useState(false), [err, setErr] = useState('');
  function enviar(e) {
    e.preventDefault();
    if (!u.trim() || !p) return setErr('Ingrese su usuario y su contraseña.');
    if (!ok) return setErr('Debe aceptar la Política de Tratamiento de Datos Personales.');
    /* PUNTO DE INTEGRACIÓN: reemplazar por la autenticación institucional.
       Mientras tanto se compara la huella de usuario y contraseña; nada se envía ni se almacena. */
    const usuario = u.trim().toLowerCase().replace(/@unal\.edu\.co$/, '');
    if (sha256hex('sat-medellin:' + usuario + ':' + p) !== HUELLA_ACCESO) return setErr('Usuario o contraseña incorrectos.');
    onEntrar(usuario);
  }
  return <div className="d-flex justify-content-center align-items-center bg-fixed-primary flex-grow-1 sat-login">
    <form noValidate className="login rounded-5" onSubmit={enviar}>
      <div className="vstack justify-content-center align-self-stretch">
        <p id="header-login" className="text-center text-neutral-30 mb-9">Ingresa con tu usuario UNAL</p>
        <div className="vstack gap-5"><div className="vstack gap-3">
          <div><label htmlFor="username" className="form-label required">Correo electrónico</label>
            <div className="input-group"><span translate="no" className="input-group-text start material-symbols-outlined">person</span>
              <input id="username" type="text" placeholder="Ej. juanfl" className="form-control" value={u} onChange={e => setU(e.target.value)} autoComplete="username" />
              <span translate="no" className="input-group-text end">@unal.edu.co</span></div></div>
          <div><label htmlFor="password" className="form-label required">Contraseña</label>
            <div className="input-group"><span translate="no" className="input-group-text start material-symbols-outlined">lock</span>
              <input id="password" type={ver ? 'text' : 'password'} placeholder="Ej. asdf123-" className="form-control" value={p} onChange={e => setP(e.target.value)} autoComplete="current-password" />
              <button type="button" translate="no" aria-label="Mostrar u ocultar contraseña" className="input-group-text end material-symbols-outlined" onClick={() => setVer(!ver)}>{ver ? 'visibility_off' : 'visibility'}</button></div></div>
        </div>
          <hr className="hr bg-neutral-80" />
          <div className="form-check"><input type="checkbox" className="form-check-input" id="data-privacy" checked={ok} onChange={e => setOk(e.target.checked)} />
            <label htmlFor="data-privacy" className="form-check-label text-justify"> De acuerdo a la Ley 1581 de 2012 de Protección de Datos Personales, he leído, entendido y aceptado los términos descritos en la <a href="https://unal.edu.co/proteccion-de-datos-personales" target="_blank" rel="noopener" className="link link-primary">Política de Tratamiento de Datos Personales.</a></label></div>
          {err && <div className="dsh-aviso" role="alert" style={{ margin: 0 }}>{err}</div>}
          <button className="btn btn-primary w-100" type="submit">Iniciar sesión</button>
          <div className="vstack justify-content-center align-items-center"><a href="https://cuenta.unal.edu.co/index.php?p=recoverPassword" target="_blank" rel="noopener" className="link link-primary text-center w-100">Olvidé mi contraseña</a></div>
        </div></div></form></div>;
}


function Buscador({ onElegir }) {
  const [q, setQ] = useState(''), [abierto, setAbierto] = useState(false);
  const sug = useMemo(() => {
    const t = norm(q).trim(); if (t.length < 3) return [];
    const r = []; for (const e of EST) { if (norm(e[1]).includes(t) || e[0].includes(t)) { r.push(e); if (r.length >= 8) break; } } return r;
  }, [q]);
  return <div className="dsh-filtros"><div className="dsh-campo" style={{ position: 'relative', maxWidth: 560 }}>
    <label>Buscar estudiante por documento o nombre (mínimo 3 caracteres)</label>
    <input className="dsh-texto" value={q} onChange={ev => { setQ(ev.target.value); setAbierto(true); }} placeholder="Ingrese documento o nombre" />
    {abierto && sug.length > 0 && <div className="dsh-multi-panel" style={{ maxHeight: 320, overflow: 'auto' }}>
      {sug.map(s => <button key={s[0]} className="dsh-ficha" style={{ width: '100%', borderRadius: '.3rem', margin: '.15rem 0', justifyContent: 'space-between' }}
        onClick={() => { onElegir(s[0]); setQ(''); setAbierto(false); }}><span>{s[1]} · {s[0]}</span><Nivel n={s[4]} /></button>)}</div>}
  </div></div>;
}

function DetalleAsignatura({ sel, cerrar, abrir }) {
  const detalle = (NOTAS_POR_ASIG[sel[0]] || []).map(n => ({ e: EST[n[0]], n })).sort((a, b) => b.e[4] - a.e[4] || b.e[5] - a.e[5]);
  const cols = [{ t: 'Documento', w: 120, v: x => x.e[0], izq: true }, { t: 'Estudiante', v: x => x.e[1], izq: true }, { t: 'Grupo', w: 80, v: x => x.n[2] },
    { t: 'Nivel de riesgo', w: 120, v: x => NIV[x.e[4]], s: x => x.e[5], r: x => <Nivel n={x.e[4]} /> }, { t: 'Probabilidad de pérdida', w: 120, v: x => x.e[5] },
    { t: 'Prom. parciales', w: 100, v: x => x.n[3], r: x => nf(x.n[3], 2) }, { t: 'Mediana del grupo', w: 110, v: x => x.n[4], r: x => nf(x.n[4], 2) },
    { t: 'Cuarto inferior', w: 110, v: x => x.n[8] ? 'Sí' : 'No' }];
  return <div className="dsh-card"><div className="dsh-card-h"><h2>{sel[1]} <small style={{ fontWeight: 400, color: 'var(--dsh-tinta-2)' }}>({sel[0]})</small></h2>
    <button className="dsh-quitar" onClick={cerrar}>Cerrar <span>×</span></button></div>
    <Tabla cols={cols} filas={detalle} orden0={{ k: 3, d: -1 }} onFila={x => abrir(x.e[0])} nombreCsv={'estudiantes_' + sel[0]}
      vacio="La asignatura no aparece en el reporte de notas parciales de 2026-2S." /></div>;
}

/* ------------------------------------------------------------ módulo 1 */
function ModuloEstudiantes({ abrir }) {
  const [fac, setFac] = useState(''), [prog, setProg] = useState(''), [niv, setNiv] = useState('t'), [ori, setOri] = useState('t'), [q, setQ] = useState('');
  const progsDe = useMemo(() => META.progs.map((p, i) => [i, p]).filter(([i]) => fac === '' || META.prog_fac[i] === +fac), [fac]);
  const filas = useMemo(() => {
    const t = norm(q);
    return EST.filter(e => (fac === '' || e[3] === +fac) && (prog === '' || e[2] === +prog) && (niv === 't' || e[4] === +niv)
      && (ori === 't' || ORIGEN[e[0]] === +ori) && (!t || norm(e[1]).includes(t) || e[0].includes(t)));
  }, [fac, prog, niv, ori, q]);
  const cn = [0, 0, 0]; filas.forEach(e => cn[e[4]]++);
  const prom = filas.length ? filas.reduce((s, e) => s + (e[5] || 0), 0) / filas.length : null;
  const porProg = useMemo(() => {
    const m = {}; filas.forEach(e => { (m[e[2]] = m[e[2]] || [0, 0, 0])[e[4]]++; });
    return Object.entries(m).map(([i, c]) => ({ p: META.progs[i], c, n: c[0] + c[1] + c[2] })).sort((a, b) => (b.c[2] / b.n) - (a.c[2] / a.n));
  }, [filas]);
  const opcion = useMemo(() => {
    const d = porProg.slice(0, 15).reverse();
    return { grid: { left: 240, right: 40, top: 10, bottom: 92 }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      valueFormatter: v => nf(v, 1) }, legend: { bottom: 4, left: 'center', itemWidth: 10, itemHeight: 10 },
      xAxis: { type: 'value', max: 100, name: 'Porcentaje', nameLocation: 'middle', nameGap: 30 },
      yAxis: { type: 'category', data: d.map(x => x.p), axisLabel: { width: 225, overflow: 'truncate', fontSize: 11 } },
      series: [2, 1, 0].map(k => ({ name: NIV[k], type: 'bar', stack: 't', itemStyle: { color: COLOR[k] },
        data: d.map(x => +(x.c[k] / x.n * 100).toFixed(1)) })) };
  }, [porProg]);
  const cols = [
    { t: 'Documento', w: 120, v: e => e[0], izq: true }, { t: 'Estudiante', v: e => e[1], izq: true },
    { t: 'Programa curricular', v: e => META.progs[e[2]], izq: true },
    { t: 'Nivel de riesgo', w: 120, v: e => NIV[e[4]], s: e => e[5], r: e => <Nivel n={e[4]} /> },
    { t: 'Probabilidad de pérdida ajustada', w: 120, v: e => e[5] }, { t: 'Probabilidad de pérdida base', w: 110, v: e => e[6] },
    { t: 'Matrículas', w: 100, v: e => e[7] }, { t: 'Asig. con parcial / inscritas', w: 130, v: e => e[9] + ' / ' + e[8], s: e => e[8] }];
  return <>
    <div className="dsh-filtros"><div className="dsh-grid-f f-4" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(210px,1fr))' }}>
      <div className="dsh-campo"><label>Facultad</label><select className="dsh-select" value={fac} onChange={e => { setFac(e.target.value); setProg(''); }}>
        <option value="">Todas</option>{META.facs.map((f, i) => <option key={i} value={i}>{f}</option>)}</select></div>
      <div className="dsh-campo"><label>Programa curricular</label><select className="dsh-select" value={prog} onChange={e => setProg(e.target.value)}>
        <option value="">Todos</option>{progsDe.map(([i, p]) => <option key={i} value={i}>{p}</option>)}</select></div>
      <div className="dsh-campo"><label>Nivel de riesgo</label><Segmento valor={niv} onCambio={setNiv} op={[['t', 'Todos'], ['2', 'Alto'], ['1', 'Medio'], ['0', 'Bajo']]} /></div>
      <div className="dsh-campo"><label>Procedencia</label><Segmento valor={ori} onCambio={setOri} op={[['t', 'Todos'], ['0', 'Valle de Aburrá'], ['1', 'Foráneos']]} /></div>
      <div className="dsh-campo"><label>Buscar por nombre o documento</label><input className="dsh-texto" value={q} onChange={e => setQ(e.target.value)} placeholder="Ingrese documento o nombre" /></div>
    </div></div>
    <div className="dsh-kpis">
      <Kpi ic="persona" color="#677d29" lab="Estudiantes" val={nf(filas.length)} pie={'Periodo ' + META.periodo} />
      <Kpi ic="circulo" color={COLOR[2]} lab="Riesgo alto" val={nf(cn[2])} pie={pc(filas.length ? cn[2] / filas.length * 100 : null)} />
      <Kpi ic="circulo" color={COLOR[1]} lab="Riesgo medio" val={nf(cn[1])} pie={pc(filas.length ? cn[1] / filas.length * 100 : null)} />
      <Kpi ic="visto" color={COLOR[0]} lab="Riesgo bajo" val={nf(cn[0])} pie={pc(filas.length ? cn[0] / filas.length * 100 : null)} />
      <Kpi ic="tasa" color="#2ba6cb" lab="Probabilidad de pérdida promedio" val={pc(prom)} />
    </div>
    <div className="dsh-card" style={{ marginBottom: '1.1rem' }}>
      <div className="dsh-card-h"><h2>Composición por nivel de riesgo en los 15 programas con mayor proporción de riesgo alto</h2></div>
      <div className="dsh-cuerpo">{filas.length ? <Grafico opcion={opcion} alto={470} /> : <p className="dsh-vacio">Sin datos.</p>}</div></div>
    <div className="dsh-card"><div className="dsh-card-h"><h2>Detalle por estudiante</h2></div>
      <Tabla cols={cols} filas={filas} orden0={{ k: 3, d: -1 }} onFila={e => abrir(e[0])} nombreCsv="riesgo_por_estudiante" />
      <p className="dsh-ayuda">Haga clic en una fila para abrir la consulta individual.</p></div>
  </>;
}

/* ------------------------------------------------------------ módulo 2 */
function ModuloAsignaturas({ abrir }) {
  const [uab, setUab] = useState(''), [min, setMin] = useState('20'), [q, setQ] = useState(''), [sel, setSel] = useState(null);
  const filas = useMemo(() => {
    const t = norm(q);
    return ASIG.filter(a => (uab === '' || a[2] === uab) && a[4] >= +min && (!t || norm(a[1]).includes(t) || a[0].includes(t)));
  }, [uab, min, q]);
  const tot = filas.reduce((s, a) => s + a[4], 0), alto = filas.reduce((s, a) => s + a[6], 0), medio = filas.reduce((s, a) => s + a[7], 0);
  const top = useMemo(() => [...filas].sort((a, b) => (b[6] + b[7]) - (a[6] + a[7])).slice(0, 20).reverse(), [filas]);
  const opcion = useMemo(() => ({
    grid: { left: 250, right: 40, top: 10, bottom: 64 }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 4, left: 'center', itemWidth: 10, itemHeight: 10 }, xAxis: { type: 'value' },
    yAxis: { type: 'category', data: top.map(a => a[1]), axisLabel: { width: 235, overflow: 'truncate', fontSize: 11 } },
    series: [[2, 6], [1, 7]].map(([k, i]) => ({ name: NIV[k], type: 'bar', stack: 't', itemStyle: { color: COLOR[k] }, data: top.map(a => a[i]) }))
  }), [top]);
  const cols = [
    { t: 'Código', w: 110, v: a => a[0], izq: true }, { t: 'Asignatura', f: 30, v: a => a[1], izq: true }, { t: 'Unidad académica básica', f: 30, v: a => a[2], izq: true },
    { t: 'Inscritos', w: 90, v: a => a[4] }, { t: 'Alto', w: 80, v: a => a[6] }, { t: 'Medio', w: 80, v: a => a[7] }, { t: 'Bajo', w: 80, v: a => a[8] },
    { t: 'Porcentaje alto + medio', w: 110, v: a => +((a[6] + a[7]) / a[4] * 100).toFixed(1), r: a => pc((a[6] + a[7]) / a[4] * 100) },
    { t: 'Prom. parciales', w: 100, v: a => a[11], r: a => nf(a[11], 2) },
    { t: 'Porcentaje bajo 3,0 (avance)', w: 120, v: a => a[9] ? +(a[10] / a[9] * 100).toFixed(1) : null, r: a => a[9] ? pc(a[10] / a[9] * 100) : '—' },
    { t: 'Porcentaje de pérdida histórica', w: 120, v: a => a[12], r: a => pc(a[12]) }];
  return <>
    <div className="dsh-filtros"><div className="dsh-grid-f" style={{ gridTemplateColumns: 'repeat(auto-fit,minmax(230px,1fr))' }}>
      <div className="dsh-campo"><label>Unidad académica básica</label><select className="dsh-select" value={uab} onChange={e => setUab(e.target.value)}>
        <option value="">Todas</option>{UABS.map(u => <option key={u}>{u}</option>)}</select></div>
      <div className="dsh-campo"><label>Inscritos mínimos</label><Segmento valor={min} onCambio={setMin} op={[['1', 'Todas'], ['20', '20 o más'], ['50', '50 o más'], ['100', '100 o más']]} /></div>
      <div className="dsh-campo"><label>Buscar asignatura o código</label><input className="dsh-texto" value={q} onChange={e => setQ(e.target.value)} placeholder="Ej. Cálculo" /></div>
    </div></div>
    <div className="dsh-kpis">
      <Kpi ic="malla" color="#677d29" lab="Asignaturas" val={nf(filas.length)} />
      <Kpi ic="doc" color="#2ba6cb" lab="Matrículas de estudiantes" val={nf(tot)} />
      <Kpi ic="circulo" color={COLOR[2]} lab="Con riesgo alto" val={nf(alto)} pie={pc(tot ? alto / tot * 100 : null)} />
      <Kpi ic="circulo" color={COLOR[1]} lab="Con riesgo medio" val={nf(medio)} pie={pc(tot ? medio / tot * 100 : null)} />
    </div>
    <div className="dsh-card" style={{ marginBottom: '1.1rem' }}>
      <div className="dsh-card-h"><h2>Las 20 asignaturas con más estudiantes en riesgo alto o medio</h2></div>
      <div className="dsh-cuerpo">{top.length ? <Grafico opcion={opcion} alto={520} onClick={p => { const a = top.find(x => x[1] === p.name); if (a) setSel(a); }} /> : <p className="dsh-vacio">Sin datos.</p>}</div>
      <p className="dsh-ayuda">Un estudiante cuenta una vez por cada asignatura en la que está inscrito.</p></div>
    <div className="dsh-card" style={{ marginBottom: '1.1rem' }}><div className="dsh-card-h"><h2>Detalle por asignatura</h2></div>
      <Tabla cols={cols} filas={filas} orden0={{ k: 5, d: -1 }} onFila={setSel} nombreCsv="riesgo_por_asignatura" /></div>
    {sel && <DetalleAsignatura sel={sel} cerrar={() => setSel(null)} abrir={abrir} />}
  </>;
}

/* ------------------------------------------------------------ asignaturas con pérdida mayor que 70 */
function ModuloRiesgoAsig({ abrir }) {
  const [sel, setSel] = useState(null);
  const filas = useMemo(() => RIESGO.filter(a => a[13] > 70 && a[12] >= 20), []);
  const nh = filas.filter(a => a[7] > 70).length, nv = filas.filter(a => a[13] > 70).length;
  const alto = filas.reduce((s, a) => s + (a[14] || 0), 0), medio = filas.reduce((s, a) => s + (a[15] || 0), 0);
  const top = useMemo(() => [...filas].sort((a, b) => Math.max(a[7] || 0, a[13] || 0) - Math.max(b[7] || 0, b[13] || 0)), [filas]);
  const opcion = useMemo(() => ({
    grid: { left: 250, right: 40, top: 10, bottom: 92 }, tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: v => v == null ? 'Sin dato' : nf(v, 1) },
    legend: { bottom: 4, left: 'center', itemWidth: 10, itemHeight: 10 },
    xAxis: { type: 'value', max: 100, name: 'Porcentaje', nameLocation: 'middle', nameGap: 30 },
    yAxis: { type: 'category', data: top.map(a => a[1]), axisLabel: { width: 235, overflow: 'truncate', fontSize: 11 } },
    series: [{ name: 'Pérdida histórica', type: 'bar', itemStyle: { color: COLOR[2] }, data: top.map(a => a[7]),
      markLine: { symbol: 'none', silent: true, lineStyle: { color: '#4e5254', type: 'dashed' }, label: { formatter: '70' }, data: [{ xAxis: 70 }] } },
      { name: 'Parcial bajo 3,0', type: 'bar', itemStyle: { color: '#2ba6cb' }, data: top.map(a => a[13]) }]
  }), [top]);
  const mapa = useMemo(() => {
    const cods = new Set(filas.map(f => f[0]));
    const pct = x => x && x[0] > 0 ? x[1] / x[0] * 100 : null;
    const lista = PARC.filas.filter(f => cods.has(f[0]))
      .sort((a, b) => Math.max(...b[3].map(x => pct(x) || 0)) - Math.max(...a[3].map(x => pct(x) || 0)));
    let ult = 0; lista.forEach(f => f[3].forEach((x, k) => { if (pct(x) != null) ult = Math.max(ult, k + 1); }));
    const ejeX = PARC.parciales.slice(0, Math.max(ult, 1)), ejeY = lista.map(f => f[1]).reverse();
    const datos = [];
    lista.forEach((f, r) => f[3].slice(0, ejeX.length).forEach((x, k) => {
      const v = pct(x); if (v == null) return;
      const c = v > 70 ? COLOR[2] : v > 40 ? '#f0d78a' : '#bfe3d0';
      datos.push({ value: [k, lista.length - 1 - r, +v.toFixed(1), x[0], x[1]], itemStyle: { color: c, borderColor: '#fff', borderWidth: 2 }, label: { color: v > 70 ? '#fff' : '#242627' } });
    }));
    return { n: lista.length, opcion: {
      grid: { left: 250, right: 20, top: 34, bottom: 8 },
      tooltip: { formatter: p => p.value ? p.name + '<br/>' + ejeX[p.value[0]] + ': ' + nf(p.value[2], 1) + ' de porcentaje con nota bajo 3,0 (' + p.value[4] + ' de ' + p.value[3] + ' calificados)' : '' },
      xAxis: { type: 'category', position: 'top', data: ejeX, splitArea: { show: false }, axisLine: { show: false }, axisTick: { show: false } },
      yAxis: { type: 'category', data: ejeY, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { width: 235, overflow: 'truncate', fontSize: 11 } },
      series: [{ type: 'heatmap', data: datos.map(d => ({ ...d, name: ejeY[d.value[1]] })), label: { show: true, formatter: p => nf(p.value[2], 0), fontSize: 11 } }] } };
  }, [filas]);
  const cols = [
    { t: 'Código', w: 110, v: a => a[0], izq: true }, { t: 'Asignatura', f: 30, v: a => a[1], izq: true }, { t: 'Unidad académica básica', f: 30, v: a => a[2], izq: true },
    { t: 'Estudiantes 2024-2S a 2025-2S', w: 120, v: a => a[5] }, { t: 'Perdieron', w: 90, v: a => a[6] },
    { t: 'Porcentaje de pérdida histórica', w: 120, v: a => a[7], r: a => pc(a[7]) },
    { t: 'Inscritos 2026-2S', w: 100, v: a => a[11] }, { t: 'Con parcial calificado', w: 110, v: a => a[12] },
    { t: 'Porcentaje bajo 3,0 (avance)', w: 120, v: a => a[13], r: a => pc(a[13]) },
    { t: 'Riesgo alto', w: 90, v: a => a[14] }, { t: 'Riesgo medio', w: 90, v: a => a[15] }];
  return <>
    <div className="dsh-definicion"><h2 className="dsh-tit">Asignaturas con más de 70 de porcentaje de pérdida</h2></div>
    <div className="dsh-kpis">
      <Kpi ic="malla" color="#677d29" lab="Asignaturas" val={nf(filas.length)} />
      <Kpi ic="circulo" color={COLOR[2]} lab="Estudiantes inscritos con riesgo alto" val={nf(alto)} />
      <Kpi ic="circulo" color={COLOR[1]} lab="Estudiantes inscritos con riesgo medio" val={nf(medio)} />
    </div>
    <div className="dsh-card" style={{ marginBottom: '1.1rem' }}>
      <div className="dsh-card-h"><h2>Asignaturas con mayor porcentaje de pérdida</h2></div>
      <div className="dsh-cuerpo">{top.length ? <Grafico opcion={opcion} alto={Math.max(300, top.length * 34 + 130)} onClick={p => { const a = top.find(x => x[1] === p.name); if (a) setSel(a); }} /> : <p className="dsh-vacio">Sin asignaturas con los filtros actuales.</p>}</div></div>
    <div className="dsh-card" style={{ marginBottom: '1.1rem' }}>
      <div className="dsh-card-h"><h2>Porcentaje con nota bajo 3,0 en cada parcial, al corte del {META.corte}</h2></div>
      <div className="dsh-cuerpo">{mapa.n ? <Grafico opcion={mapa.opcion} alto={mapa.n * 30 + 60} /> : <p className="dsh-vacio">Ninguna asignatura supera 70 en algún parcial con los filtros actuales.</p>}</div>
      <div className="dsh-niveles" style={{ marginTop: '.9rem' }}>
        <b>Porcentaje de estudiantes calificados con nota bajo 3,0</b>
        <span><i style={{ background: '#bfe3d0' }} />Hasta 40</span><span><i style={{ background: '#f0d78a' }} />De 40 a 70</span><span><i style={{ background: COLOR[2] }} />Más de 70</span></div>
      <p className="dsh-ayuda">Se muestran las asignaturas con más de 70 en al menos un parcial, con el mínimo de estudiantes calificados elegido arriba, hasta 25.</p></div>
    <div className="dsh-card" style={{ marginBottom: '1.1rem' }}><div className="dsh-card-h"><h2>Detalle por asignatura</h2></div>
      <Tabla cols={cols} filas={filas} orden0={{ k: 5, d: -1 }} onFila={setSel} nombreCsv="asignaturas_perdida_mayor_70" /></div>
    {sel && <DetalleAsignatura sel={sel} cerrar={() => setSel(null)} abrir={abrir} />}
  </>;
}

/* ------------------------------------------------------------ información del estudiante (archivo de matrícula) */
function ModuloFicha({ doc, setDoc, irRiesgo }) {
  const idx = doc == null ? -1 : EST.findIndex(e => e[0] === doc), e = idx >= 0 ? EST[idx] : null;
  const fila = idx >= 0 ? FICHA.filas[idx] : null;
  const valor = i => { const d = FICHA.campos[i][2], v = fila[i]; return d ? (v >= 0 ? d[v] : null) : v; };
  const Dato = ({ et, v }) => <div className="ficha-dato"><span className="ficha-et">{et}</span><span className={'ficha-val' + (v == null || v === '' ? ' vacio' : '')}>{v == null || v === '' ? 'Sin información' : v}</span></div>;
  return <>
    <Buscador onElegir={setDoc} />
    {!e ? <div className="dsh-card"><p className="dsh-vacio">Busque un estudiante para ver toda su información del archivo de matrícula de {META.periodo}.</p></div> : <>
      <div className="dsh-card ficha-cab"><div><h2>{e[1]}</h2><p>Documento {e[0]} · {META.progs[e[2]]} · {META.facs[e[3]]}</p></div>
        <div className="dsh-acc"><Nivel n={e[4]} /><button className="dsh-btn" onClick={irRiesgo}>Ver consulta de riesgo</button></div></div>
      {FICHA.grupos.map((g, gi) => {
        const campos = FICHA.campos.map((c, i) => [c, i]).filter(([c]) => c[0] === gi);
        const extra = g === 'Riesgo en el periodo' ? [
          ['Nivel de riesgo', NIV[e[4]]], ['Probabilidad de pérdida ajustada', pc(e[5])], ['Probabilidad de pérdida base', pc(e[6])],
          ['Señales de riesgo', e[11].length ? e[11].map(i => META.senales[i]).join('; ') : null]] : [];
        return <div className="dsh-card" style={{ marginBottom: '1.1rem' }} key={gi}><div className="dsh-card-h"><h2>{g}</h2></div>
          <div className="ficha-grid">{extra.map(([et, v]) => <Dato key={et} et={et} v={v} />)}{campos.map(([c, i]) => <Dato key={i} et={c[1]} v={valor(i)} />)}</div></div>;
      })}</>}
  </>;
}

/* ------------------------------------------------------------ módulo 3 */
function ModuloIndividual({ doc, setDoc, irFicha }) {
  const idx = doc == null ? -1 : EST.findIndex(e => e[0] === doc), e = idx >= 0 ? EST[idx] : null;
  const asig = e ? (NOTAS_POR_EST[idx] || []).map(n => ({ n })) : [];
  return <>
    <Buscador onElegir={setDoc} />
    {!e ? <div className="dsh-card"><p className="dsh-vacio">Busque un estudiante para ver su nivel de riesgo, las señales que lo explican y su avance en cada asignatura.</p></div> : <>
      <div className="dsh-mosaico dsh-mosaico-2">
        <div className="dsh-card ind-id"><h2>{e[1]}</h2>
          <p>Documento {e[0]}</p><p>{META.progs[e[2]]}</p><p>{META.facs[e[3]]}</p>
          <p>{e[10] != null ? e[10] + ' años · ' : ''}{e[7] != null ? nf(e[7]) + ' matrículas' : ''}</p>
          <button className="dsh-btn" style={{ marginTop: '.7rem' }} onClick={irFicha}>Ver información del estudiante</button></div>
        <div className="dsh-card"><div className="dsh-card-h"><h2>Nivel de riesgo · {META.periodo}</h2><Nivel n={e[4]} /></div>
          <div className="ind-medidor">
            <div className="ind-dato"><span className="ind-valor" style={{ color: COLOR[e[4]] }}>{pc(e[5])}</span><span className="ind-lab">Probabilidad de pérdida ajustada</span></div>
            <div className="ind-dato"><span className="ind-valor sec">{pc(e[6])}</span><span className="ind-lab">Probabilidad de pérdida base, sin parciales</span></div>
          </div>
          <div className="ind-barra"><div className="ind-marca" style={{ left: Math.min(e[5], 100) + '%' }} /></div>
          <div className="ind-escala" style={{ position: 'relative', height: 16 }}><span style={{ position: 'absolute', left: 0 }}>0</span><span style={{ position: 'absolute', left: '5%', transform: 'translateX(-50%)' }}>5</span><span style={{ position: 'absolute', left: '15%', transform: 'translateX(-50%)' }}>15</span><span style={{ position: 'absolute', right: 0 }}>100</span></div>
          <p className="dsh-ayuda">Probabilidad de pérdida de la calidad de estudiante por razones académicas al cierre del periodo.</p></div>
        <div className="dsh-card"><div className="dsh-card-h"><h2>Señales de riesgo</h2></div>
          {e[11].length ? <div className="dsh-fichas-s">{e[11].map(i => <span key={i}>{META.senales[i]}</span>)}</div> : <p className="dsh-vacio" style={{ padding: '.5rem' }}>Sin señales registradas.</p>}</div>
        <div className="dsh-card"><div className="dsh-card-h"><h2>Avance de parciales</h2></div>
          <p style={{ margin: 0, fontSize: '.88rem' }}><b>{e[9]}</b> de <b>{e[8]}</b> asignaturas con al menos un parcial calificado al {META.corte}.</p></div></div>
      <div className="dsh-card"><div className="dsh-card-h"><h2>Asignaturas inscritas</h2></div>
        <Tabla filas={asig} orden0={{ k: 3, d: 1 }} tope={100} vacio="El estudiante no aparece en el reporte de notas parciales."
          cols={[{ t: 'Código', w: 110, v: x => acodDe(x.n[1]), izq: true }, { t: 'Asignatura', f: 40, v: x => nomAsig(x.n[1]), izq: true }, { t: 'Grupo', w: 80, v: x => x.n[2] },
            { t: 'Prom. ponderado', w: 120, v: x => x.n[3], r: x => nf(x.n[3], 2) }, { t: 'Mediana del grupo', w: 110, v: x => x.n[4], r: x => nf(x.n[4], 2) },
            { t: 'Parciales calificados', w: 130, v: x => x.n[6] },
            { t: 'Cuarto inferior del grupo', w: 130, v: x => x.n[8] ? 'Sí' : 'No', r: x => x.n[8] ? <b style={{ color: COLOR[2] }}>Sí</b> : 'No' }]} /></div></>}
  </>;
}
/* El índice de asignatura en NOTAS es la posición en la lista ordenada de códigos del ETL. */
const CODIGOS = ASIG.map(a => a[0]);
function acodDe(i) { return CODIGOS[i]; }
function nomAsig(i) { return ASIG[i] ? ASIG[i][1] : ''; }

/* ------------------------------------------------------------ aplicación */
function App() {
  const [usuario, setUsuario] = useState(null);   // siempre se inicia en la pantalla de ingreso
  const [mod, setMod] = useState(0), [doc, setDoc] = useState(null);
  const entrar = u => setUsuario(u);
  const salir = () => { setUsuario(null); setMod(0); setDoc(null); };
  if (!usuario) return <Ingreso onEntrar={entrar} />;
  const abrir = d => { setDoc(d); setMod(3); window.scrollTo(0, 0); };
  const tabs = ['Nivel de riesgo por estudiante', 'Nivel de riesgo por asignatura', 'Asignaturas en riesgo por pérdida', 'Consulta individual', 'Información del estudiante'];
  return <div className="dsh">
    <div className="dsh-barra">
      <div><h1>Alertas tempranas de bloqueo</h1></div>
      <div className="dsh-usuario"><span className="dsh-avatar">{usuario[0].toUpperCase()}</span><span><b>{usuario}</b>{usuario}@unal.edu.co</span>
        <button className="dsh-btn" onClick={salir}><Icono n="logout" />Cerrar sesión</button></div></div>
    <div className="dsh-tabs" role="tablist">{tabs.map((t, i) => <button key={i} role="tab" className="dsh-tab" aria-selected={mod === i} onClick={() => setMod(i)}>{t}</button>)}</div>
    {mod === 0 && <ModuloEstudiantes abrir={abrir} />}
    {mod === 1 && <ModuloAsignaturas abrir={abrir} />}
    {mod === 2 && <ModuloRiesgoAsig abrir={abrir} />}
    {mod === 3 && <ModuloIndividual doc={doc} setDoc={setDoc} irFicha={() => setMod(4)} />}
    {mod === 4 && <ModuloFicha doc={doc} setDoc={setDoc} irRiesgo={() => setMod(3)} />}
    <div className="dsh-niveles" aria-label="Niveles de riesgo">
      <b>Niveles de riesgo según la probabilidad de pérdida de calidad de estudiante</b>
      <span><i style={{ background: COLOR[0] }} />Bajo: menor que 5</span>
      <span><i style={{ background: COLOR[1] }} />Medio: de 5 a menos de 15</span>
      <span><i style={{ background: COLOR[2] }} />Alto: 15 o más</span>
    </div>
  </div>;
}
ReactDOM.createRoot(document.getElementById('root')).render(<App />);
