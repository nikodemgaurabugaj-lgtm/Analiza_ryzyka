# FalaNMT — wyjaśnienie jak dla człowieka, nie hydrologa

Ten plik jest po to, żebyś **w środę wiedział, o czym mówisz**, nawet jeśli nie pamiętasz wzorów.

---

## Co to w ogóle jest?

Wyobraź sobie mapę wysokości terenu (jak relief z liczbami).  
Program patrzy na tę mapę i mówi:

> „Jak woda w rzece podniesie się o 1 metr / 2 metry / 3 metry — które miejsca będą mokre i jak głęboko?”

Potem nakłada to na **działki** i liczy: ile % działki jest zalane.

Nazywa się to **FalaNMT**.

---

## Czego to NIE jest? (powiedz to na początku prezentacji)

To **nie** jest oficjalna mapa powodziowa ISOK / Hydroportal.

Oficjalne mapy liczą prawdziwy przepływ rzeki (Q10, Q100…) i robią ciężką hydraulikę.  
My bierzemy **tylko kształt terenu** i robimy szybki screening.

**Dobre porównanie:**  
ISOK = pełne badanie lekarskie.  
FalaNMT = termometr + szybkie spojrzenie: „tu jest nisko, tu wysoko”.

---

## Słowniczek (zapamiętaj 6 słów)

| Słowo | Co to znaczy po ludzku |
|---|---|
| **NMT** | Numeryczny Model Terenu = mapa wysokości **gruntu** (bez drzew i dachów) |
| **NMPT** | Model z budynkami i drzewami — **nie używamy** go do zalewu |
| **Ciek** | Rzeka / rów, który program „wyczytał” z terenu |
| **Stan w korycie** | O ile metrów „podnosisz wodę” suwakiem (+0,5, +1, +2…) |
| **HAND** | Ile metrów w górę jesteś nad najbliższym ciekiem |
| **Działka ULDK** | Prawdziwa działka ewidencyjna z państwowej usługi lokalizacji |

---

## Jak działa w 5 krokach

```
1. Wczytaj NMT (wysokości)
2. Znajdź, gdzie spływa woda → narysuj ciek
3. Policz HAND = wysokość nad ciekiem
4. Suwak +h metrów → wszystko z HAND ≤ h = woda
5. Policz % zalania na każdej działce
```

### HAND na jednym zdaniu

Jeśli stoję 0,4 m nad rzeką, a Ty ustawiasz wodę +1 m — jestem pod wodą na ok. 0,6 m.  
Jeśli stoję 8 m nad rzeką — jestem suchy.

### Wanna połączona (druga metoda)

Woda stoi „równo jak w wannie”, ale **nie przechodzi przez wzgórze**.  
Jeśli za garbem jest dziura, naiwny model ją zaleje. Nasz połączony — nie, dopóki woda nie przeleje siodła.

---

## Co znaczą suwaki w aplikacji?

### 1) „Jak liczyć zalew?”
- **HAND** — domyślne, dobre do pokazania na prezentacji.
- **Wanna połączona** — pokaż, że nie zalewamy dziur za wzgórzem.

### 2) „Jak gruba ma być rzeka?” (próg cieku)
- Mała wartość (np. 0,1) → program widzi też małe rowy.
- Duża (np. 1,0) → tylko grubsza dolina.
- Na Kłodzku startuj od **~0,3**.

### 3) „Ile metrów wody ponad koryto?”
To **nie** jest „powódź 100-letnia”.  
To po prostu eksperyment: +0,5 / +1 / +2 / +3 m.

**Na demo:** pokaż 0,5 m (mało niebieskiego) i 3 m (dużo niebieskiego w dolinie). Twierdza zostaje wysoko/sucha — to dobry moment na „patrzcie, relief działa”.

---

## Co zobaczysz na mapie?

- **Niebieski** = woda (ciemniejszy = głębszy)
- **Czerwona działka** = mocno zalana (≥50%)
- **Pomarańczowa** = średnio (10–50%)
- **Zielona** = lekko (1–10%)
- **Szara** = sucha

Karty na górze:
- **Zalane teraz** — ile km² jest niebieskich
- **Głębokość średnia / max** — jak głęboko
- **Objętość** — ile „kubików” wody w tej symulacji
- **Rzędna cieku** — typowa wysokość dna rzeki z NMT

---

## Pilotaż: dlaczego Kłodzko / Nysa?

Bo dolina jest wąska i widać koryto.  
Łatwiej pokazać, że woda idzie **doliną**, a nie „wszędzie na mapie”.

Na Odrze na płaskim terenie bez wałów w modelu łatwo o fałszywe zalania — dlatego nie startowaliśmy Odry.

Dane:
- NMT 1 m z GUGiK (państwowy model terenu)
- 61 działek z ULDK (prawdziwe geometrie)

---

## Liczby, które warto powiedzieć na głos

Przy metodzie HAND na wycinku Kłodzka:

| Suwak | Zalane | Średnia głębokość |
|---|---|---|
| +0,5 m | ok. 0,31 km² | 0,36 m |
| +1 m | ok. 0,41 km² | 0,71 m |
| +2 m | ok. 0,58 km² | 1,37 m |
| +3 m | ok. 0,73 km² | 1,99 m |

Przy +2 m: mniej więcej **23 z 61** działek ma >1% powierzchni w zalewie.  
Najbardziej narażone w pilotażu: m.in. Zacisze i Centrum blisko doliny.

---

## Jak odpalić (Windows → najlepiej WSL)

```bash
# w katalogu projektu
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

PYTHONPATH=src streamlit run app/streamlit_app.py --server.port 8765
```

Otwórz w przeglądarce: `http://127.0.0.1:8765`

Albo bez klikania — raport z linii komend:

```bash
floodnmt demo --method hand --stages 0.5,1,2,3
```

Wynik: folder `outputs/nysa_klodzka/` → plik `raport.html`.

---

## Scenariusz prezentacji (5–7 minut)

1. **Problem:** ludzie chcą szybko sprawdzić działkę, a ISOK to ciężka robota.  
2. **Rozwiązanie:** z NMT robimy mapę zasięgu przy +0,5…+3 m i liczby na działkach.  
3. **Demo:** suwak 0,5 → 3 m, pokaż niebieski w dolinie.  
4. **Działki:** tabela od najbardziej narażonych.  
5. **Ograniczenie (powiedz sam!):** to nie Q100, nie prędkość, nie czas, nie decyzja urzędowa.  
6. **Wartość:** szybki screening + materiał do rozmowy z hydrologiem / do pracy inżynierskiej.

---

## Pytania, które padną — gotowe odpowiedzi

**„Czy to mapa ISOK?”**  
Nie. ISOK = hydraulika + przepływy. My = sam teren.

**„Skąd bierzesz poziom wody?”**  
Z suwaka. To scenariusz użytkownika w metrach, nie woda stuletnia.

**„Dlaczego nie HEC-RAS?”**  
Bo cel to szybkie narzędzie z NMT (Python, Rasterio, NumPy). HEC-RAS to następny, cięższy etap.

**„Jak wiesz, że działa?”**  
Testy: garb odcina misę; sieć idzie doliną; Twierdza zostaje wysoko. Pełne porównanie z MZP to kolejny krok.

**„Czemu Nysa, nie Odra?”**  
Bo tu relief sam pokazuje historię wody. Na płaskiej Odrze bez wałów w modelu wynik łatwo skłamać.

---

## Jedna ściąga na kartkę

> NMT → znajdź rzekę → HAND (metry nad rzeką) → suwak +h → niebieski zalew → % działki  
> Kłodzko / Nysa / 1 m GUGiK / 61 działek  
> +2 m ≈ 0,58 km²  
> **To screening, nie ISOK.**

Powodzenia w środę.
