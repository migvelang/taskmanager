/*
 * Revisa los casos en Firestore y manda un aviso push por cada uno que lleve
 * 2 días o más sin movimiento. Lo ejecuta GitHub Actions según el horario
 * definido en .github/workflows/avisos.yml — no necesita servidor propio.
 */
const webpush = require('web-push');

const PROYECTO = 'taskmanager-8f795';
const CLAVE = process.env.DTM_CLAVE;
const { VAPID_PUBLIC, VAPID_PRIVATE, VAPID_CONTACTO } = process.env;
const DIAS_ALERTA = 2;

if (!CLAVE || !VAPID_PUBLIC || !VAPID_PRIVATE) {
  console.error('Faltan secretos: DTM_CLAVE, VAPID_PUBLIC o VAPID_PRIVATE.');
  process.exit(1);
}

webpush.setVapidDetails(VAPID_CONTACTO || 'mailto:miguel@example.com', VAPID_PUBLIC, VAPID_PRIVATE);

const BASE = `https://firestore.googleapis.com/v1/projects/${PROYECTO}/databases/(default)/documents/paneles/${encodeURIComponent(CLAVE)}`;

// Firestore REST devuelve los valores etiquetados por tipo; esto los aplana.
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

const hoy = () => new Date().toISOString().slice(0, 10);
const diasSin = act => act ? Math.floor((new Date(hoy()) - new Date(act)) / 86400000) : 0;

async function main() {
  const rDoc = await fetch(BASE);
  if (!rDoc.ok) { console.error('No pude leer el panel:', rDoc.status); process.exit(1); }
  const doc = await rDoc.json();
  const casos = conv((doc.fields || {}).casos) || [];

  const detenidos = casos.filter(c => c.estado !== 'EN ESPERA' && diasSin(c.act) >= DIAS_ALERTA);
  console.log(`${casos.length} casos en total, ${detenidos.length} detenidos ${DIAS_ALERTA}+ días.`);
  if (!detenidos.length) return;

  const rSubs = await fetch(`${BASE}/push`);
  if (!rSubs.ok) { console.error('No pude leer las suscripciones:', rSubs.status); process.exit(1); }
  const subs = ((await rSubs.json()).documents || []).map(d => ({ nombre: d.name, sub: conv({ mapValue: { fields: d.fields } }) }));
  if (!subs.length) { console.log('No hay dispositivos suscritos todavía.'); return; }

  const cuerpo = detenidos.length === 1
    ? `${detenidos[0].id} — ${detenidos[0].desc} (${diasSin(detenidos[0].act)} días sin movimiento)`
    : detenidos.slice(0, 4).map(c => `• ${c.id} (${diasSin(c.act)}d)`).join('\n') + (detenidos.length > 4 ? `\n…y ${detenidos.length - 4} más` : '');

  const payload = JSON.stringify({
    title: detenidos.length === 1 ? '🚨 Caso detenido' : `🚨 ${detenidos.length} casos detenidos`,
    body: cuerpo,
    tag: 'casos-detenidos'
  });

  for (const { nombre, sub } of subs) {
    if (!sub || !sub.endpoint) continue;
    try {
      await webpush.sendNotification(sub, payload);
      console.log('Aviso enviado a', sub.endpoint.slice(0, 48) + '…');
    } catch (e) {
      console.error('Falló el envío:', e.statusCode || e.message);
      // 404 y 410 significan que el dispositivo ya no acepta avisos: se limpia.
      if (e.statusCode === 404 || e.statusCode === 410) {
        await fetch(`https://firestore.googleapis.com/v1/${nombre}`, { method: 'DELETE' }).catch(() => {});
        console.log('Suscripción vencida eliminada.');
      }
    }
  }
}
main().catch(e => { console.error(e); process.exit(1); });
