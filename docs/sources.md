# Fuentes (recon 2026-11-13)

## Maizetix — SE QUEDA (fuente principal y calendario)
- `GET https://www.maizetix.com/games`: público, sin login. Lleva JSON-LD (`application/ld+json`) con un `SportsEvent` por partido en casa: `startDate` (ISO con zona horaria), `location.name` y `url` (`/games/{id}`).
- Deporte según el estadio: Michigan Stadium → football, Crisler Center → basketball, Yost Ice Arena → hockey.
- `GET https://www.maizetix.com/games/{id}`: público. En la tabla `games-table` hay una fila `<tr>` por anuncio, con el precio `<td>$68.00</td>` (incluye comisiones, según la web) y el ID del anuncio en `copyLinkAndNotify('www.maizetix.com/tickets/{ticket_id}')`.
- Enlace directo al anuncio: `https://www.maizetix.com/tickets/{ticket_id}`. Para comprar sí hace falta iniciar sesión, pero eso lo hace el usuario.
- Los anuncios se pausan el día antes del partido a las 17:30.

## SeatGeek — PENDIENTE
- La API devuelve 403 sin `client_id`. El usuario tiene que conseguir uno en seatgeek.com/account/develop.

## StubHub — FUERA
- 403 con página de CAPTCHA (anti-bot).

## Vivid Seats — FUERA
- Página "Challenge Validation" (anti-bot por JavaScript).

### SeatGeek, actualización 2026-11-13
La API responde con `client_id` (probadas 2 claves) y lista bien los partidos (slugs `michigan-wolverines-mens-hockey`, `-mens-basketball`, `-football`). Pero `stats` llega vacío (`{}`) en todos los eventos, también en `/2/events/{id}`, así que no da precios. **No sirve para avisos de precio.**
