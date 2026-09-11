# FalaNMT

Narzędzie inżynierskie do **szybkiego screeningu zasięgu zalewu** z numerycznego modelu terenu. Po wczytaniu NMT (GeoTIFF / ASC) liczy sieć drenażu, raster HAND i mapy głębokości dla zadanych stanów w korycie, a następnie ocenia **konkretne działki ewidencyjne**.

Pilotaż: **Nysa Kłodzka w Kłodzku** — NMT 1 m GUGiK oraz rzeczywiste geometrie ULDK.

To **nie** jest mapa zagrożenia powodziowego ISOK i **nie** zastępuje modelu hydraulicznego 1D/2D.

## Po co to jest

Oficjalne MZP (Hydroportal) powstają z przepływów Q₁₀ / Q₁ / Q₀,₂ i modelu hydraulicznego. FalaNMT odpowiada na inne pytanie:

> *Przy stanie h metrów ponad ciek odczytany z NMT — które piksele i które działki są pod wodą, jak głęboko, i jak bardzo wynik zależy od ±20 cm błędu wysokości?*

Zastosowanie: wstępna ocena działki, materiał do rozmowy z hydrologiem, porównanie wariantu HAND z wanną połączoną, ćwiczenie inżynierskie. Nie: pozwolenie wodnoprawne, MPZP, ubezpieczenie.

## Metody

| Metoda | Zasada | Kiedy kłamie |
|---|---|---|
| **HAND** (Nobre et al. 2011/2016) | `HAND ≤ h` wzdłuż ścieżki spływu D8 | ujścia, kilka rzek, misy „podłączone” tylko przez fill |
| **Wanna połączona** | płaskie H, BFS od cieku, garb odcina | brak cofki, brak prędkości, płaskie zwierciadło |

Płaska wanna `z < H` **nie jest** dostępna jako wynik — zalewałaby odłączone zagłębienia. Jest w testach jako kontrprzykład.

Klasy głębokości jak na MZP: &lt;0,5 / 0,5–2 / 2–4 / &gt;4 m.

## Pilotaż — dlaczego Nysa Kłodzka

Dolina jest ciasna, deniwelacje na wycinku to ~80 m, koryto czytelne w NMT 1 m. Kłodzko ma historię powodzi 1997 i 2024, więc temat nie jest abstrakcyjny. Nysa, nie Odra: na Odrze pod Wrocławiem płaska terasa i wały sprawiają, że sam NMT bez hydro-enforcementu daje fałszywe korytarze; tu dolina sama niesie spływ.

Wycinek: ok. 2,05 × 1,94 km, EPSG:2180, wysokości PL-KRON86-NH, komórka 1 m.

## Uruchomienie

Python 3.11+ z GDAL (rasterio). W tym repozytorium:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Aplikacja:

```bash
PYTHONPATH=src streamlit run app/streamlit_app.py --server.port 8765 --server.address 0.0.0.0
```

CLI — pilotaż Kłodzka:

```bash
floodnmt demo --out outputs/nysa_klodzka --method hand --stages 0.5,1,2,3
```

Własny NMT:

```bash
floodnmt analyze sciezka/nmt.tif --parcels dzialki.geojson --method hand --stages 0.5,1,2 --out outputs/run
```

Porównanie metod na dolinie syntetycznej (test wanny vs HAND):

```bash
floodnmt synthetic --out outputs/synthetic
pytest
```

Wyniki: `raport.html`, `raport.json`, GeoTIFF głębokości, GeoJSON zasięgu i działek, figury PNG.

## Wejście / wyjście

**Wejście:** NMT (lepiej 1 m, grunt a nie NMPT), opcjonalnie poligony działek, lista stanów w korycie [m], próg akumulacji cieku [km²].

**Wyjście:** głębokość, klasy ISOK, objętość, metryki działki (% powierzchni, max/śr. głębokość, najniższy piksel), pas niepewności H±RMSE.

Na małym wycinku próg cieku dotyczy **lokalnej** akumulacji (tu max ≈ 2,6 km²), nie rzeczywistej zlewni Nysy.

## Ograniczenia — czytaj zanim zaufasz mapie

- Brak Q, braku chropowatości, braku czasu i prędkości.
- Mosty w NMT mogą zatkać koryto; wały mogą być dziurawe o piksel.
- HAND źródłuje wodę z najbliższego cieku.
- Mieszanie PL-KRON86-NH z EVRF2007-NH psuje rzędne o decymetry.
- 0,2 m RMSE na płaskiej terasie przesuwa brzeg zalewu o dziesiątki metrów — dlatego raport ma mapę zgodności trzech realizacji.

Szczegóły: [`docs/metodyka.md`](docs/metodyka.md).

## Stack

Python · Rasterio/GDAL · NumPy · SciPy · pyflwdir · GeoPandas · Matplotlib · Streamlit · Folium.

## Licencja danych pilotażowych

NMT: GUGiK / geoportal.gov.pl, dane bezpłatne. Działki: usługa ULDK. Wynik FalaNMT nie jest produktem Wód Polskich ani ISOK.
