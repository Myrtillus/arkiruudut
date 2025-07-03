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

Suorita skripti. Oletuksena käytetään `squadrats.kml`-tiedostoa:

```bash
python tiling.py
```

Voit myös antaa KML-tiedoston parametrina:

```bash
python tiling.py squadrats-2025-07-03.kml
```

Karttatiedostot löytyvät `output`-hakemistosta:

`tiles-big-20250703.img`

`tiles-small-20250703.img`

Vie tiedostot Garminiin. Apua löytyy esimerkiksi [Tero Hiironniemen ohjeistuksesta](https://www.youtube.com/watch?v=kHZTVT0tEVI). 

## MacOS

```bash
brew update
brew upgrade
brew install gpsbabel
brew install openjdk
```

```bash
echo 'export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile
```

Lataa mkgmap ja luo skripti sen ajamiseen:

```bash
nano ~/bin/mkgmap
```

Tiedoston sisältö. Tallenna mkgmap-paketti haluamaasi paikkaan ja muokkaa polkua vastaavasti:

```bash
#!/bin/bash
java -jar /Users/USERNAME/bin/mkgmap-r4923/mkgmap.jar "$@"
```

Tässä mkgmap-paketti on sijoitettu `bin`-hakemistoon.

Päivitetään vielä polku:

```bash
chmod +x ~/bin/mkgmap
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zprofile
source ~/.zprofile
```




