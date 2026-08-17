# vinted-watch

Finder nye bogopslag på vinted.dk der matcher `titler.txt` / `forfattere.txt`, og favoriserer dem.

## Kør

```bash
source .venv/bin/activate
python -m vinted_watch.cli --config config.yaml --favorite --csv matches.csv
```

Rediger `titler.txt`, `forfattere.txt` og `config.yaml` direkte for at ændre søgninger/pris/kategori.

## Ryd favoritter

```bash
python -m vinted_watch.clear_favourites --yes
```

Rører kun bøger scriptet selv har fundet (sporet i `vinted_watch.db`) - ikke tøj eller andet du selv har favoriseret manuelt. Tilføj `--all-favourites` for at fjerne alt.

## Hvis `.env` skal opdateres (cookie/token udløbet)

1. Log ind på vinted.dk → DevTools (F12) → Network → Fetch/XHR
2. Favoritisér et vilkårligt opslag → find requestet til `user_favourites/toggle`
3. Kopiér `cookie`-header ind i `VINTED_COOKIE` i `.env`
4. Kopiér `x-csrf-token`-header ind i `VINTED_CSRF_TOKEN` i `.env`

## Kør periodisk

```cron
*/15 * * * * cd /Users/kmeyer/Github/vinted-scraper && .venv/bin/python -m vinted_watch.cli --config config.yaml --favorite --csv matches.csv >> run.log 2>&1
```
