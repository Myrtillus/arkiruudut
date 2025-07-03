# Arkiruudut

Luo Garmin-yhteensopivan kartan puuttuvista ruuduista. Tukee sekä suuria ruutuja (tiles, squadrats) että pieniä ruutuleita (squadratinhos).

Hae KML-tiedosto [squadrats.com-palvelusta](https://squadrats.com/map): Download KML.


## Asennus

Luo virtuaaliympäristö ja aktivoi se:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Päivitä `pip` ja asenna riippuvuudet:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Suorita skripti:

Skripti käyttää oletuksena `squadrats.kml`-tiedostoa:

```bash
python tiling.py
```

Voit myös antaa KML-tiedoston parametrina:

```bash
python tiling.py squadrats-2025-07-03.kml
```

