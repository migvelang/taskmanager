/*
 * Revisa los casos de cada cuenta en Firestore y manda un aviso push por los
 * que lleven 2 días o más sin movimiento. Lo ejecuta GitHub Actions según el
 * horario de .github/workflows/avisos.yml — no hace falta servidor propio.
 *
 * Necesita una cuenta de servicio porque, con las reglas de seguridad puestas,
 * los paneles solo los puede leer su dueño o una credencial de administrador.
 */
const webpush = require('web-push');
const { GoogleAuth } = require('google-auth-library');

const PROYECTO = 'taskmanager-8f795';
const DIAS_ALERTA = 2;
const { VAPID_PUBLIC, VAPID_PRIVATE, VAPID_CONTACTO, GCP_SA_KEY } = process.env;

const faltan = Object.entries({ VAPID_PUBLIC, VAPID_PRIVATE, GCP_SA_KEY })
  .filter(([, v]) => !v).map(([k]) => k);
if (faltan.length) {
  console.error('❌ Faltan estos secretos en GitHub: ' + faltan.join(', '));
  console.error('   Settings → Secrets and variables → Actions → New repository secret');
  process.exit(1);
}

let credenciales;
try { credenciales = JSON.parse(GCP_SA_KEY); }
catch (e) {
  console.error('❌ GCP_SA_KEY no es un JSON válido. Pega el archivo completo de la cuenta de servicio, incluidas las llaves { }.');
  process.exit(1);
}

webpush.setVapidDetails(VAPID_CONTACTO || 'mailto:taskmanager@example.com', VAPID_PUBLIC, VAPID_PRIVATE);

const RAIZ = `https://firestore.googleapis.com/v1/projects/${PROYECTO}/databases/(default)/documents`;

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
  const auth = new GoogleAuth({ credentials: credenciales, scopes: ['https://www.googleapis.com/auth/datastore'] });
  const token = (await (await auth.getClient()).getAccessToken()).token;
  const get = async url => {
    const r = await fetch(url, { headers: { Authorization: 'Bearer ' + token } });
    if (!r.ok) { console.error(`   ⚠️  ${r.status} al leer ${url.replace(RAIZ, '')}`); return null; }
    return r.json();
  };

  const lista = await get(`${RAIZ}/paneles?pageSize=300`);
  if (!lista) { console.error('❌ No pude leer los paneles. Revisa que la cuenta de servicio tenga permiso de Firestore.'); process.exit(1); }
  const paneles = lista.documents || [];
  console.log(`📋 ${paneles.length} panel(es) en total.`);

  let enviados = 0, sinDispositivos = 0;

  for (const panel of paneles) {
    const uid = panel.name.split('/').pop();
    const casos = conv((panel.fields || {}).casos) || [];
    const detenidos = casos.filter(c => c && c.estado !== 'EN ESPERA' && diasSin(c.act) >= DIAS_ALERTA);
    if (!detenidos.length) { console.log(`   ${uid.slice(0, 8)}… sin casos detenidos.`); continue; }

    const subsDoc = await get(`${RAIZ}/paneles/${uid}/push`);
    const subs = ((subsDoc && subsDoc.documents) || []).map(d => ({
      nombre: d.name,
      sub: conv({ mapValue: { fields: d.fields } })
    })).filter(x => x.sub && x.sub.endpoint);

    if (!subs.length) { sinDispositivos++; console.log(`   ${uid.slice(0, 8)}… ${detenidos.length} detenido(s), pero sin dispositivos suscritos.`); continue; }

    const cuerpo = detenidos.length === 1
      ? `${detenidos[0].id} — ${detenidos[0].desc} (${diasSin(detenidos[0].act)} días sin movimiento)`
      : detenidos.slice(0, 4).map(c => `• ${c.id} (${diasSin(c.act)}d)`).join('\n') +
        (detenidos.length > 4 ? `\n…y ${detenidos.length - 4} más` : '');
    const payload = JSON.stringify({
      title: detenidos.length === 1 ? '🚨 Caso detenido' : `🚨 ${detenidos.length} casos detenidos`,
      body: cuerpo,
      tag: 'casos-detenidos'
    });

    for (const { nombre, sub } of subs) {
      try {
        await webpush.sendNotification(sub, payload);
        enviados++;
        console.log(`   ✅ aviso enviado (${uid.slice(0, 8)}…, ${detenidos.length} caso(s))`);
      } catch (e) {
        console.error(`   ⚠️  falló el envío: ${e.statusCode || e.message}`);
        // 404 y 410 = el dispositivo ya no acepta avisos; se limpia la suscripción.
        if (e.statusCode === 404 || e.statusCode === 410) {
          await fetch(`https://firestore.googleapis.com/v1/${nombre}`, {
            method: 'DELETE', headers: { Authorization: 'Bearer ' + token }
          }).catch(() => {});
          console.log('   🧹 suscripción vencida eliminada.');
        }
      }
    }
  }

  console.log(`\n🔔 ${enviados} aviso(s) enviado(s).`);
  if (sinDispositivos) console.log(`ℹ️  ${sinDispositivos} panel(es) con casos detenidos pero sin ningún dispositivo suscrito: abre la app y toca la campana.`);
}

main().catch(e => { console.error('❌', e); process.exit(1); });
