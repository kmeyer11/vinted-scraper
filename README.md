# vinted-watch

Lille Python-CLI der søger på Vinted efter en liste af gemte søgninger
(f.eks. bestemte forfattere, bogtitler eller emner), og rapporterer nye
opslag den ikke har set før. Kan valgfrit forsøge at favoritisere dem
automatisk.

Bygger på det åbne, vedligeholdte bibliotek
[`vinted_scraper`](https://github.com/Giglium/vinted_scraper) til selve
søgningen (det håndterer Vinteds interne søge-API og cookie-håndtering).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
cp titler.example.txt titler.txt
cp forfattere.example.txt forfattere.txt
```

Søgeordene bor i to txt-filer, én linje pr. søgning:

- `titler.txt` - bogtitler du leder efter (f.eks. "Historien om salt")
- `forfattere.txt` - forfatternavne du leder efter (f.eks. "Ken Follett")

Ret dem til med hvad du selv leder efter - linjer der starter med `#`
ignoreres. Scriptet søger hver linje for sig og slår dem sammen til én
liste af fund.

`config.yaml` styrer de fælles indstillinger for alle søgninger: hvilket
Vinted-marked (`domain`), evt. kategori (`catalog_ids: 2312` er "Bøger" -
fjern feltet for at søge på tværs af alle kategorier), og evt. prisloft
(`price_to`).

## Kør det

.venv/bin/python -m vinted_watch.cli --config config.yaml --csv matches.csv

Favorite: .venv/bin/python -m vinted_watch.cli --config config.yaml --favorite

Første gang bliver alt hvad der findes markeret som "set" og skrevet ud.
Kør scriptet igen senere, og det rapporterer kun opslag der er kommet til
siden sidst (sporet i en lokal SQLite-fil, `vinted_watch.db`).

Gem alle fund løbende i en CSV-fil til overblik:

```bash
python -m vinted_watch.cli --config config.yaml --csv matches.csv
```

### Kør periodisk

Scriptet kører kun én gang pr. kald - sæt det op til at køre med jævne
mellemrum via cron (macOS/Linux) eller Kalenderstyret opgave (Windows).
Eksempel, hver 15. minut:

```cron
*/15 * * * * cd /Users/kmeyer/Github/vinted-scraper && .venv/bin/python -m vinted_watch.cli --config config.yaml --csv matches.csv >> run.log 2>&1
```

## Auto-favoritisering (valgfrit, "best effort")

Vinted har ingen officiel/dokumenteret API til at favoritisere opslag, og
kræver at man er logget ind. Du kan aktivere et forsøg på automatisk
favoritisering ved at:

1. Kopiere `.env.example` til `.env`.
2. Følge instruktionerne i filen for at hente din egen login-cookie fra
   browseren, og indsætte den som `VINTED_COOKIE`.
3. Køre med `--favorite`:

```bash
python -m vinted_watch.cli --config config.yaml --favorite
```

Da dette bruger et udokumenteret endpoint, kan det stoppe med at virke hvis
Vinted ændrer noget - scriptet fejler i så fald blidt (logger fejlen) og
fortsætter med at finde og logge nye matches som normalt. `.env` er git-
ignoreret; del aldrig cookien med nogen, den svarer til dit login.

## Vær en god borger

- Scriptet lægger en lille pause ind mellem hver søgning for ikke at
  spamme Vinted med requests.
- Kør det ikke oftere end nødvendigt (hvert 10.-15. minut er rigeligt til
  personligt brug).
- Dette er tænkt til personligt brug (find bøger du selv vil købe) - ikke
  til masseindsamling af data eller videresalg.
