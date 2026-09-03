/*
 * Arma el resumen del día con lo que hay en Firestore y lo manda a Teams
 * y/o al correo. Lo ejecuta GitHub Actions según .github/workflows/resumen.yml.
 *
 * Teams: los conectores "Incoming Webhook" de Office 365 se apagaron en mayo
 * de 2026, así que la dirección tiene que salir de la app Workflows (Power
 * Automate), plantilla "Post to a channel when a webhook request is received".
 * Esa dirección recibe tarjetas adaptables, que es lo que se envía aquí.
 *
 * Correo: SMTP directo, sin dependencias, hablando el protocolo por TLS.
 * Con Gmail hay que usar una contraseña de aplicación, no la del correo.
 */
const { GoogleAuth } = require('google-auth-library');
const tls = require('tls');

const PROYECTO = 'taskmanager-8f795';
const FUSO = 'America/Santiago';
const DIAS_ALERTA = 2;
const {
  GCP_SA_KEY, TEAMS_WEBHOOK,
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_PARA
} = process.env;

if (!GCP_SA_KEY) {
  console.error('❌ Falta el secreto GCP_SA_KEY en GitHub.');
  console.error('   Settings → Secrets and variables → Actions → New repository secret');
  process.exit(1);
}
if (!TEAMS_WEBHOOK && !SMTP_HOST) {
  console.error('❌ No hay a dónde mandar el resumen: define TEAMS_WEBHOOK o los secretos SMTP_*.');
  process.exit(1);
}

/* El secreto puede venir como el JSON tal cual o codificado en base64,
   porque pegar un JSON de varias líneas se presta para errores. El
   diagnóstico dice qué llegó sin mostrar nada del contenido. */
function leerCredenciales(txt) {
  const bruto = String(txt || '').trim();
  const intentos = [bruto];
  if (/^[A-Za-z0-9+/=\s]+$/.test(bruto) && bruto.length > 100) {
    try { intentos.push(Buffer.from(bruto, 'base64').toString('utf8')); } catch (e) {}
  }
  for (const t of intentos) {
    try {
      const j = JSON.parse(t);
      if (j && j.client_email && j.private_key) return j;
      console.error('❌ GCP_SA_KEY es un JSON válido pero no es una cuenta de servicio: le faltan client_email o private_key.');
      process.exit(1);
    } catch (e) {}
  }
  console.error('❌ GCP_SA_KEY no se pudo leer como JSON.');
  console.error(`   Recibí ${bruto.length} caracteres y empiezan por "${bruto.slice(0, 1) || '(vacío)'}".`);
  console.error('   Tiene que ser el archivo .json completo de la cuenta de servicio, desde la primera { hasta la última }.');
  console.error('   Consola de Firebase → Configuración del proyecto → Cuentas de servicio → Generar nueva clave privada.');
  process.exit(1);
}
const credenciales = leerCredenciales(GCP_SA_KEY);

const RAIZ = `https://firestore.googleapis.com/v1/projects/${PROYECTO}/databases/(default)/documents`;

/* Firestore REST devuelve los valores etiquetados por tipo; esto los aplana. */
function conv(v) {
  if (v == null) return null;
  if (v.stringValue !== undefined) return v.stringValue;
  if (v.integerValue !== undefined) return Number(v.integerValue);
  if (v.doubleValue !== undefined) return v.doubleValue;
  if (v.booleanValue !== undefined) return v.booleanValue;
  if (v.nullValue !== undefined) return null;
  if (v.arrayValue) return (v.arrayValue.values || []).map(conv);
  if (v.mapValue) return Object.fromEntries(Object.entries(v.mapValue.fields || {}).map(([k, x]) => [k, conv(x)]));
  return null;
}

/* La fecha se mira siempre en Chile: en UTC, desde las 21:00 locales ya es
   el día siguiente y los días sin movimiento salen inflados en uno. */
function enChile(d = new Date()) {
  const p = new Intl.DateTimeFormat('en-CA', {
    timeZone: FUSO, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23'
  }).formatToParts(d).reduce((a, x) => (a[x.type] = x.value, a), {});
  return { fecha: `${p.year}-${p.month}-${p.day}`, hora: Number(p.hour) };
}
const hoy = () => enChile().fecha;
const diasSin = act => act ? Math.max(0, Math.round((new Date(hoy()) - new Date(act)) / 86400000)) : 0;

const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
               'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
function fechaLarga(ds) {
  const [y, m, d] = ds.split('-').map(Number);
  const f = new Date(y, m - 1, d);
  return DIAS[f.getDay()] + ' ' + d + ' de ' + MESES[m - 1];
}

/* ── lo que se cuenta ──────────────────────────────────────────── */
function armarResumen(panel) {
  const f = panel.fields || {};
  const tareas = (conv(f.tareas) || []).filter(Boolean);
  const casos = (conv(f.casos) || []).filter(Boolean);
  const agenda = (conv(f.agenda) || []).filter(Boolean);
  const h = hoy();

  const pendientes = tareas.filter(t => !t.done);
  const urgentes = pendientes.filter(t => t.cat === 'urgente');
  const vencen = pendientes.filter(t => t.venc && t.venc <= h);
  const detenidos = casos.filter(c => c.estado !== 'EN ESPERA' && diasSin(c.act) >= DIAS_ALERTA)
                         .sort((a, b) => diasSin(b.act) - diasSin(a.act));
  const eventos = agenda.filter(e => e.d === h)
                        .sort((a, b) => String(a.hora || '').localeCompare(String(b.hora || '')));

  return { h, pendientes, urgentes, vencen, detenidos, eventos, casos };
}

function lineasTexto(r) {
  const l = [];
  l.push(`Resumen del ${fechaLarga(r.h)}`);
  l.push('');
  l.push(`${r.pendientes.length} tareas pendientes · ${r.urgentes.length} urgentes · ${r.casos.length} casos abiertos`);
  l.push('');
  if (r.eventos.length) {
    l.push('AGENDA DE HOY');
    r.eventos.forEach(e => l.push(`  ${e.hora || 'todo el día'}  ${e.t}`));
    l.push('');
  }
  if (r.vencen.length) {
    l.push('VENCEN HOY');
    r.vencen.slice(0, 8).forEach(t => l.push(`  • ${t.text}`));
    l.push('');
  }
  if (r.urgentes.length) {
    l.push('URGENTES');
    r.urgentes.slice(0, 8).forEach(t => l.push(`  • ${t.text}`));
    l.push('');
  }
  if (r.detenidos.length) {
    l.push(`CASOS DETENIDOS (${DIAS_ALERTA}+ días sin movimiento)`);
    r.detenidos.slice(0, 10).forEach(c => l.push(`  • ${c.id} — ${c.desc} (${diasSin(c.act)} días)`));
    l.push('');
  }
  if (!r.eventos.length && !r.vencen.length && !r.urgentes.length && !r.detenidos.length)
    l.push('Nada urgente para hoy. Buen momento para adelantar algo.');
  return l;
}

/* ── Teams ─────────────────────────────────────────────────────── */
function tarjetaTeams(r) {
  const cuerpo = [
    { type: 'TextBlock', size: 'Large', weight: 'Bolder', text: 'Resumen del día' },
    { type: 'TextBlock', spacing: 'None', isSubtle: true, text: fechaLarga(r.h) },
    { type: 'FactSet', facts: [
      { title: 'Pendientes', value: String(r.pendientes.length) },
      { title: 'Urgentes', value: String(r.urgentes.length) },
      { title: 'Vencen hoy', value: String(r.vencen.length) },
      { title: 'Casos abiertos', value: String(r.casos.length) },
      { title: 'Casos detenidos', value: String(r.detenidos.length) }
    ]}
  ];
  const seccion = (titulo, lineas, color) => {
    if (!lineas.length) return;
    cuerpo.push({ type: 'TextBlock', weight: 'Bolder', spacing: 'Medium', text: titulo, color: color || 'Default' });
    cuerpo.push({ type: 'TextBlock', wrap: true, text: lineas.join('\n\n') });
  };
  seccion('Agenda de hoy', r.eventos.slice(0, 8).map(e => `**${e.hora || 'todo el día'}** · ${e.t}`));
  seccion('Vencen hoy', r.vencen.slice(0, 8).map(t => `• ${t.text}`), 'Warning');
  seccion('Urgentes', r.urgentes.slice(0, 8).map(t => `• ${t.text}`), 'Attention');
  seccion(`Casos detenidos (${DIAS_ALERTA}+ días)`,
          r.detenidos.slice(0, 10).map(c => `• **${c.id}** ${c.desc} — ${diasSin(c.act)} días`), 'Attention');
  if (cuerpo.length === 3) cuerpo.push({ type: 'TextBlock', wrap: true, text: 'Nada urgente para hoy.' });

  return {
    type: 'message',
    attachments: [{
      contentType: 'application/vnd.microsoft.card.adaptive',
      content: { type: 'AdaptiveCard', $schema: 'http://adaptivecards.io/schemas/adaptive-card.json',
                 version: '1.4', body: cuerpo }
    }]
  };
}
async function enviarTeams(r) {
  const res = await fetch(TEAMS_WEBHOOK, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(tarjetaTeams(r))
  });
  if (!res.ok) throw new Error(`Teams respondió ${res.status}: ${(await res.text()).slice(0, 200)}`);
  console.log('✅ Resumen enviado a Teams.');
}

/* ── correo ────────────────────────────────────────────────────── */
/* Cliente SMTP mínimo: conecta por TLS, se identifica, autentica y envía. */
function smtpEnviar({ host, port, user, pass, de, para, asunto, texto }) {
  const b64 = t => Buffer.from(t, 'utf8').toString('base64');
  const mensaje = [
    `From: Daily Task Manager <${de}>`,
    `To: ${para}`,
    `Subject: =?UTF-8?B?${b64(asunto)}?=`,
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'Content-Transfer-Encoding: base64',
    '',
    // en base64 ninguna línea empieza con punto, así que no hace falta escaparlo
    b64(texto).replace(/(.{76})/g, '$1\r\n'),
    '.'
  ].join('\r\n');

  // [código que se espera del servidor, lo que se le manda al recibirlo]
  const guion = [
    [220, `EHLO ${host}`],
    [250, 'AUTH LOGIN'],
    [334, b64(user)],
    [334, b64(pass)],
    [235, `MAIL FROM:<${de}>`],
    [250, `RCPT TO:<${para}>`],
    [250, 'DATA'],
    [354, mensaje],
    [250, 'QUIT']
  ];

  return new Promise((resolve, reject) => {
    const s = tls.connect({ host, port, servername: host });
    let buffer = '', i = 0, listo = false;
    const fallar = m => { if (listo) return; listo = true; try { s.destroy(); } catch (e) {} reject(new Error(m)); };
    s.setTimeout(25000, () => fallar('el servidor SMTP no respondió a tiempo'));
    s.on('error', e => fallar('SMTP: ' + e.message));
    s.on('data', d => {
      if (listo) return;         // el 221 de despedida llega después del QUIT
      buffer += d.toString();
      // una respuesta puede venir en varias líneas; termina en "250 " y no "250-"
      const lineas = buffer.split('\r\n').filter(Boolean);
      const ultima = lineas[lineas.length - 1] || '';
      if (!/^\d{3} /.test(ultima)) return;
      buffer = '';
      const [esperado, enviar] = guion[i];
      if (Number(ultima.slice(0, 3)) !== esperado)
        return fallar(`SMTP esperaba ${esperado} y recibió: ${ultima}`);
      i++;
      s.write(enviar + '\r\n');
      if (i >= guion.length) { listo = true; s.end(); resolve(); }
    });
  });
}
async function enviarCorreo(r) {
  const para = SMTP_PARA || SMTP_USER;
  await smtpEnviar({
    host: SMTP_HOST, port: Number(SMTP_PORT || 465),
    user: SMTP_USER, pass: SMTP_PASS, de: SMTP_USER, para,
    asunto: `Resumen del día · ${r.pendientes.length} pendientes, ${r.detenidos.length} casos detenidos`,
    texto: lineasTexto(r).join('\n')
  });
  console.log(`✅ Resumen enviado por correo a ${para}.`);
}

/* ── principal ─────────────────────────────────────────────────── */
async function main() {
  const { hora } = enChile();
  console.log(`🕐 En Chile son las ${String(hora).padStart(2, '0')}:00. Armo el resumen del ${hoy()}.`);

  const auth = new GoogleAuth({ credentials: credenciales, scopes: ['https://www.googleapis.com/auth/datastore'] });
  const token = (await (await auth.getClient()).getAccessToken()).token;
  const res = await fetch(`${RAIZ}/paneles?pageSize=300`, { headers: { Authorization: 'Bearer ' + token } });
  if (!res.ok) {
    console.error(`❌ No pude leer los paneles (${res.status}). Revisa el permiso de Firestore de la cuenta de servicio.`);
    process.exit(1);
  }
  const paneles = (await res.json()).documents || [];
  console.log(`📋 ${paneles.length} panel(es).`);

  let enviados = 0;
  for (const panel of paneles) {
    const r = armarResumen(panel);
    // un panel sin nada abierto no merece un correo cada mañana
    if (!r.pendientes.length && !r.casos.length && !r.eventos.length) {
      console.log(`   ${panel.name.split('/').pop().slice(0, 8)}… vacío, lo salto.`);
      continue;
    }
    console.log(lineasTexto(r).map(l => '   ' + l).join('\n'));
    if (TEAMS_WEBHOOK) { try { await enviarTeams(r); enviados++; } catch (e) { console.error('   ⚠️  ' + e.message); } }
    if (SMTP_HOST)     { try { await enviarCorreo(r); enviados++; } catch (e) { console.error('   ⚠️  ' + e.message); } }
  }
  console.log(`\n📨 ${enviados} envío(s) realizados.`);
}

if (require.main === module) main().catch(e => { console.error('❌', e); process.exit(1); });
else module.exports = { main, smtpEnviar, armarResumen, lineasTexto, tarjetaTeams, enChile, diasSin };
