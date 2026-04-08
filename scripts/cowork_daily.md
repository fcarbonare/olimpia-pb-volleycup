# Task: Aggiornamento giornaliero Olimpia PB

## Quando eseguire
Ogni giorno, preferibilmente la mattina (08:00 ora italiana).

## Passi

1. Apri il terminale nel repository `olimpia-pb-volleycup`.
2. Esegui: `python scripts/fetch_data.py`
3. Controlla l'output: se ci sono errori, annotali e ferma il task.
4. Esegui: `python scripts/update_classifica.py`
5. Esegui: `python scripts/build_site.py`
6. Fai commit e push dei file modificati:
   ```
   git add data/ site/ logs/
   git commit -m "data: aggiornamento automatico $(date '+%Y-%m-%d')"
   git push
   ```
7. Verifica che GitHub Pages pubblichi correttamente (attendi 1-2 minuti).

## In caso di errore
- Se lo scraping fallisce (timeout, sito non raggiungibile), non fare commit.
- Se i dati sembrano anomali (es. classifica vuota, 0 partite), non sovrascrivere.
- Annota l'errore nel file `logs/ultimo_aggiornamento.log`.
