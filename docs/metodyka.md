# Metodyka — FalaNMT

Dokument równoważny rozdziałowi metodycznemu pracy inżynierskiej. Opisuje, **co** jest liczone, **dlaczego** tak, i **gdzie** model nie ma prawa być użyty.

## 1. Problem

Działka ewidencyjna leży w dolinie. Użytkownik ma NMT i chce w minutach, nie tygodniach, zobaczyć zasięg wody przy kilku stanach w korycie oraz liczby: procent powierzchni, głębokość, najniższy piksel.

Oficjalna ścieżka (dyrektywa 2007/60/WE, Prawo wodne, MZP/MRP) idzie inaczej:

1. hydrologia → przepływy o zadanym prawdopodobieństwie (Q 10%, Q 1%, Q 0,2%),
2. model hydrauliczny 1D / 2D / 1D–2D → rzędne zwierciadła i prędkości,
3. przecięcie zwierciadła z NMT → zasięg.

FalaNMT **pomija (1) i (2)**. Zostaje sam teren. To screening topograficzny, nie ocena ryzyka w sensie ISOK.

## 2. Dane

### 2.1 NMT a NMPT

NMT (DEM) = grunt. NMPT (DSM) = grunt + budynki + drzewa + mosty. Wejściem musi być NMT. Heurystyka chropowatości (σ w oknie 5×5) ostrzega, gdy raster wygląda na NMPT.

Polski zasób GUGiK: siatka 1 m (ALS, RMSE wysokości rzędu 0,1–0,2 m) i 5 m (~0,5 m). Układy wysokości **PL-KRON86-NH** i **PL-EVRF2007-NH nie wolno mieszać**. Układ poziomy pilotażu: EPSG:2180.

### 2.2 Wycinek pilotażowy

Kłodzko, Nysa Kłodzka. BBOX PL-1992 w przybliżeniu
`(332431, 287204, 334482, 289142)`, komórka 1 m, ~3,97 km², wysokości 281,4–365,3 m n.p.m. Źródło: WCS
`PZGIK/NMT/GRID1/WCS/DigitalTerrainModelFormatTIFF`, pokrycie `DTM_PL-KRON86-NH_TIFF`.

Na wycinku maksymalna akumulacja spływu wynosi ~2,6 km² — **ułamek** prawdziwej zlewni Nysy Kłodzkiej powyżej Kłodzka. Próg cieku jest parametrem lokalnym.

### 2.3 Działki

Geometrie z ULDK (`GetParcelByXY`) na siatce punktów w oknie NMT. Identyfikator TERYT, obręb, numer. Procent zalania liczony jest z pikseli NMT, nie z pola w KW.

## 3. Łańcuch obliczeń

```
NMT → walidacja → wypełnienie depresji → D8 + akumulacja
    → sieć drenażu → HAND
    → scenariusz h → głębokość → klasy ISOK
    → (opcjonalnie) działki, niepewność ±RMSE
```

### 3.1 Uwarunkowanie hydrologiczne

`pyflwdir.from_dem` / `fill_depressions` — Wang & Liu (2006), rodzina Priority-Flood (Barnes et al. 2014). Depresje wypełniane do najniższego przelewu, spływ wyprowadzany na krawędź rastra. To **nie** jest model retencji mis; to warunek konieczny, by D8 nie kończył się w dziurze.

### 3.2 Sieć drenażu

Komórka należy do cieku, gdy akumulacja ≥ `stream_km2` (domyślnie 0,30 km²). Jeśli próg przekracza maksimum na wycinku, algorytm obniża go do 12% maksimum. Za mały próg → HAND „źródłuje” z suchych wciosów na stoku. Za duży → gubi Nysę.

### 3.3 HAND

Height Above Nearest Drainage (Nobre et al., *Hydrol. Process.* 2011, 2016):

\[
\mathrm{HAND}(i) = z(i) - z(d(i))
\]

gdzie \(d(i)\) jest najbliższą komórką sieci wzdłuż ścieżki D8. Zalanie przy stanie \(h\):

\[
\mathrm{depth}(i) = \max\bigl(0,\, h - \mathrm{HAND}(i)\bigr)
\]

dla komórek z \(\mathrm{HAND} \le h\).

HAND jest proxy zasięgu fluwialnego. Nie zna cofki, nie zna dwóch rzek naraz (każda komórka ma jeden „najbliższy” ciek), nie zna obiektów inżynierskich poza tym, co widać w NMT.

### 3.4 Wanna połączona

Zwierciadło płaskie:

\[
H = \mathrm{median}(z_{\mathrm{ciek}}) + h
\]

Zalane są komórki z \(z \le H\) **osiągalne** 8-sąsiedztwem z sieci cieku. BFS, \(O(n)\).

Różnica wobec naiwnej wanny \(z < H\): zamknięta misa za garbem pozostaje sucha, dopóki \(H\) nie przewyższy siodła. Test syntetyczny w `tests/test_inundation.py` to wymusza.

Różnica wobec HAND: HAND może „zalać” misę, jeśli po wypełnieniu depresji ścieżka D8 łączy ją z ciekiem i różnica wysokości jest mała — nawet gdy woda fizycznie nie przeleje siodła przy danym \(H\). Dlatego w interfejsie są **obie** metody.

### 3.5 Klasy głębokości

Jak warstwy głębokości MZP (metodyka aMZPiMRP): &lt;0,5 m; 0,5–2 m; 2–4 m; &gt;4 m. Kolorystyka celowo zbliżona, **etykieta produktu jest inna**.

### 3.6 Działka

Rasteryzacja poligonów do siatki identyfikatorów (raz), potem `bincount` na masce zalewu. Metryki: pole zalane, %, średnia / max / p90 głębokości, min \(z\) na działce, suma powierzchni w klasach ISOK.

### 3.7 Niepewność

NMT 1 m ALS: RMSE ≈ 0,20 m. Dla każdego \(h\) liczone są trzy realizacje \(h-\varepsilon, h, h+\varepsilon\). Mapa zgodności: rdzeń (mokre we wszystkich) vs brzeg (tylko pesymistyczna). Na tarasie zalewowej 20 cm to nie kosmetyka.

## 4. Czego model świadomie nie robi

- Nie przypisuje \(h\) do Q₁ czy „powodzi stuletniej”.
- Nie liczy Manninga, wektora prędkości, czasu.
- Nie niszczy wału (scenariusz WZ z MZP).
- Nie robi hydro-enforcementu mostów i przepustów.
- Nie jest Fill–Spill–Merge dla deszczu (pluwialnie: tylko misy widoczne jako HAND/wanny, bez objętości opadu).
- Nie jest HEC-RAS / TELEMAC / LISFLOOD-FP.

## 5. Weryfikacja

1. Testy syntetyczne: garb odcina misę; siodło ją wpuszcza; HAND = 0 na cieku; monotoniczność zasięgu.
2. Wizualna kontrola sieci na ortofoto Kłodzka (musi iść doliną Nysy, nie stokiem Twierdzy).
3. Porównanie *jakościowe* z Hydroportalem (Q 1%) — IoU nie jest celem v1, bo brak Q. Różnica jest cechą, nie błędem, o ile jest opisana.

## 6. Literatura (wybór)

- Nobre, A.D. et al. (2011). Height Above the Nearest Drainage — a hydrologically relevant new terrain model. *J. Hydrol.*
- Nobre, A.D. et al. (2016). HAND contour: a new proxy predictor of inundation extent. *Hydrol. Process.* 30.
- Barnes, R., Lehman, C., Mulla, D. (2014). Priority-flood: An optimal depression-filling algorithm. *Computers & Geosciences* 62.
- Wang, L., Liu, H. (2006). An efficient method for identifying and filling surface depressions in DEMs. *IJGIS*.
- PGW WP — metodyka opracowania MZP i MRP (II cykl).
- GUGiK — NMT 1 m / 5 m, geoportal.gov.pl.

## 7. Rekomendacja użycia wyniku

Drukuj `raport.html` razem z tym rozdziałem. Na pierwszej stronie jest zastrzeżenie. Jeśli ktoś pyta „czy działka jest na Q1%”, odpowiedzią jest Hydroportal, nie ta mapa.
