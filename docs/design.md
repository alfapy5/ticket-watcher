# Ticket Watcher: diseño

Fecha: 2026-11-13

> **Cambios tras la investigación de las webs (2026-11-13, ver `docs/sources.md`):** las páginas de partidos y anuncios de Maizetix son públicas, sin iniciar sesión. Por eso se eliminaron la sesión guardada, el respaldo en el portátil y la frecuencia de 30 min: Maizetix se revisa cada 15 min. StubHub y Vivid Seats quedan fuera porque bloquean con anti-bot. SeatGeek queda pendiente de un `client_id`. El calendario sale de Maizetix.

## Intención

Estudiante de la University of Michigan en Ann Arbor. Quiere ir a partidos de Michigan pagando lo mínimo posible por una entrada de reventa. El sistema vigila los precios y le avisa al móvil cuando aparece una entrada barata. La compra la hace el usuario a mano.

## Objetivos

- Vigilar **todos los partidos en casa** de Michigan **masculino**: basket, hockey y fútbol americano.
- Buscar siempre **1 entrada**.
- Enviar una notificación push al móvil cuando:
  1. Aparece un **nuevo mínimo**: una entrada más barata que la más barata vista hasta ahora para ese partido, contando todas las fuentes.
  2. Una entrada baja del **precio máximo** que el usuario ha puesto para ese partido. El máximo es opcional.
- Comparar siempre el **precio final con comisiones** (all-in).
- Cada aviso incluye el partido, la fuente, el precio final y un enlace directo al anuncio.

## No objetivos

- No compra nada ni toca pagos o cuentas para comprar.
- No busca más de 1 entrada ni asientos juntos.
- No vigila deportes femeninos ni partidos fuera de casa.
- No ofrece interfaz web: la configuración es un archivo en GitHub.

## Anti-objetivos (fracaso aunque funcione)

- Spam: avisos repetidos de la misma entrada o avisos que no son ofertas reales.
- Poner en riesgo la cuenta de UMich del usuario: logins automáticos, guardar su contraseña o un patrón de uso que provoque un bloqueo.
- Saltarse CAPTCHAs o protecciones anti-bot. Si una web bloquea al sistema, esa web se queda fuera.
- Fallar en silencio: si una fuente deja de funcionar o la sesión de Maizetix caduca, el usuario tiene que enterarse.

## Fuentes

| Fuente | Acceso | Notas |
|---|---|---|
| SeatGeek | API oficial (client_id gratuito) | La más estable. Hay que comprobar si la API da el precio con comisiones o hay que estimarlo. |
| StubHub | Web pública | Tiene anti-bot. Entra solo si se puede leer sin saltarse protecciones. |
| Vivid Seats | Web pública | Igual que StubHub. |
| Maizetix | Requiere sesión UMich (Weblogin + Duo) | Mercado entre estudiantes. Probablemente la fuente más barata. |

## Dónde corre (opción elegida: B con A de respaldo)

Consideramos tres opciones:

- **A. Mixto:** las webs públicas en la nube y Maizetix en el portátil. Es fiable, pero Maizetix no se vigila con el portátil cerrado.
- **B. Todo en la nube:** Maizetix con una sesión guardada. Cubre más horas, pero la sesión puede caducar o ser bloqueada.
- **C. Todo en el portátil:** lo más simple, pero no vigila nada con el portátil cerrado, y el portátil del usuario suele estar cerrado.

**Elegida: B con A de respaldo.**

- **Nube (GitHub Actions, cron cada 10–15 min, gratis):** revisa todas las fuentes, incluida Maizetix con la sesión guardada.
- **Sesión de Maizetix:** el usuario inicia sesión a mano en su portátil, con su navegador y su Duo. Un script local exporta la sesión (cookies) a un GitHub Secret. La contraseña nunca se guarda.
- **Si la sesión falla** (caduca o la bloquean), la nube manda un aviso: "sesión de Maizetix caducada, vuelve a iniciar sesión". Desde ese momento el portátil vigila Maizetix cuando esté abierto, y nada más abrirlo hace una revisión inmediata.
- **Objetivo secundario:** medir cuánto dura de verdad la sesión en la nube. Si casi nunca aguanta, nos quedamos con A.

## Configuración

Un archivo en el repo de GitHub que el usuario edita desde el navegador del móvil, con una línea por partido y su precio máximo opcional. La lista de partidos en casa se genera automáticamente. El archivo solo sirve para poner máximos o silenciar un partido.

## Notificaciones

App **ntfy**: gratis, iOS y Android, sin cuenta. El tema (topic) tiene un nombre aleatorio largo, guardado como secret.

## Estado

El sistema guarda el mínimo visto por partido y los IDs de anuncios ya avisados, para no repetir avisos. Al ser GitHub Actions sin servidor, el estado tiene que persistir entre ejecuciones; cómo se hace lo decide quien lo construya.

## Detalle de los avisos

- "Nuevo mínimo" significa más barato que la entrada más barata **a la venta ahora mismo** para ese partido, no que el mínimo histórico. Si se vende la entrada barata, el mínimo de referencia sube.
- La primera ejecución de cada partido es silenciosa: solo registra precios. (Decisión de Claude)
- Se avisa con cualquier bajada de al menos $1. (Decisión de Claude)

## Portátil (respaldo)

- Windows. Una tarea del Programador de tareas se lanza al iniciar sesión o desbloquear el equipo, y después cada 15 min mientras esté encendido. (Decisión de Claude)
- El portátil lee el estado "sesión caída" del `state.json` público del repo, sin token porque el repo es público. Guarda su propio estado de Maizetix en local. (Decisión de Claude)

## Repo

- **Público** (decisión del usuario): GitHub Actions gratis sin límite de minutos.
- Secrets cifrados: cookies de Maizetix, topic de ntfy, client_id de SeatGeek.
- El estado guardado en el repo contiene solo el precio mínimo por partido e IDs de anuncios hasheados. Nunca datos de vendedores ni detalles de anuncios de Maizetix, que es un mercado cerrado a estudiantes. (Decisión de Claude)

## Decisiones tomadas por Claude (no por el usuario)

- Maizetix se revisa desde la nube con menos frecuencia que el resto (cada 30 min), para reducir el riesgo de bloqueo de la cuenta UMich.

- Lenguaje: Python.
- ntfy para las notificaciones.
- GitHub Actions como nube.
- Comparar con comisiones incluidas.
- No repetir avisos de la misma entrada.

## Lo que queda a quien construya

- Cómo sacar el calendario de partidos en casa (por ejemplo, de mgoblue.com o de los eventos de SeatGeek).
- Cómo emparejar el mismo partido entre fuentes distintas.
- Cómo persistir el estado entre ejecuciones de GitHub Actions.
- Cómo hacer scraping de cada web, respetando los anti-objetivos.
- Formato exacto del archivo de configuración.
