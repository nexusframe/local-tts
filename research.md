# Lokalny TTS na CPU dla polskiego asystenta AI

Oct 7, 2026 · @Leto

## 1. Executive summary

Rekomendacja: **Pocket TTS (Kyutai) z polskim modelem społecznościowym `shefowl/pocket-tts-polish-6l`** jako główny silnik oraz **Piper (`piper1-gpl`)** jako backend awaryjny w tym samym demonie. Wybór jest warunkowy — zależy od lokalnego benchmarku z sekcji 17.

Pocket TTS to jedyny znaleziony kandydat, który na CPU łączy naraz neuronową jakość polskiej mowy, streaming (\~200 ms do pierwszego fragmentu według autorów silnika), klonowanie głosu i małe zużycie pamięci. Polski model deklaruje RTF 0,21 (fp32) i 0,11 (int8) oraz 125–341 MB wag w RAM. Ryzyko: to model jednej osoby, opublikowany 17.09.2026, bez niezależnej weryfikacji i bez badania MOS.

Piper jest najbezpieczniejszy: dojrzały, bardzo szybki, 9 polskich głosów (5 oficjalnych + 4 społecznościowe WG Głos), gotowe API Python i HTTP. Jakość jest jednak „średnia neuronowa”, a otwarte zgłoszenie #267 opisuje błędną wymowę liczebników we wszystkich polskich głosach.

Trzecie miejsce zajmuje **Supertonic 3**: najlepszy udokumentowany WER dla polskiego wśród szybkich modeli i RTF 0,172 na CPU. Repozytorium jest jednak zarchiwizowane, licencja modelu to OpenRAIL-M, a lokalnego klonowania brak.

Duże modele z oficjalnym polskim (XTTS-v2, Chatterbox Multilingual V3, VoxCPM2, OmniVoice) działają na CPU, ale zbyt wolno do rozmowy (RTF ≈ 1–11). Nadają się co najwyżej do generowania offline.

## 2. Wnioski w skrócie

- **Na CPU realnie działają tylko małe modele (≤ \~110M parametrów lub klasyczne VITS/HTS).** Wszystko powyżej 0,5B parametrów ma na CPU RTF bliski 1 lub wyższy, więc nie nadaje się do asystenta.
- **Polski jako język „pierwszej klasy”** mają: Piper (oficjalne głosy), RHVoice (moduł językowy PL), Supertonic 3, XTTS-v2, Chatterbox Multilingual, VoxCPM2. Pocket TTS ma polski **tylko jako model społecznościowy**, ale wytrenowany na 425 h polskiej mowy.
- **Klonowanie głosu praktyczne na CPU** ma wyłącznie Pocket TTS (zero-shot z 6–9 s nagrania, deklarowane podobieństwo 0,946 cos). XTTS-v2 klonuje na CPU, ale z RTF \~1,7–2 (raport społeczności).
- **Streaming z niskim TTFA** zapewniają Pocket TTS (natywny streaming fragmentów) i Piper (generator po zdaniach; krótkie zdanie syntetyzuje się w ułamek sekundy).
- **Normalizacja tekstu (liczby, daty, skróty) to słaby punkt wszystkich kandydatów.** Demon musi mieć własny polski normalizator przed TTS — niezależnie od wybranego silnika.
- **Licencje:** najczystsze są Piper-głosy CC0/Apache/MIT (kod GPL-3.0), Pocket TTS (MIT + CC-BY-4.0), VoxCPM2 (Apache-2.0), Chatterbox (MIT). Problematyczne: XTTS-v2 (CPML, niekomercyjna; firmy Coqui już nie ma), Supertonic 3 (OpenRAIL-M z ograniczeniami użycia), RHVoice Magda/Natan (CC-BY-NC-ND), MMS-TTS (CC-BY-NC).

## 3. Kryteria i ograniczenia

**Twarde ograniczenia:** wyłącznie CPU (bez CUDA/ROCm/chmury), Linux, praktyczna używalność na lokalnej maszynie, priorytet dla pl-PL.

**Kolejność wag (od użytkownika):** jakość polskiego → wydajność CPU → latency → RAM → streaming → voice cloning → integracja → kondycja projektu → licencje.

**Próg praktyczności dla asystenta (moje założenie):** RTF ≤ 0,5 na typowym laptopie (8 rdzeni) i TTFA ≤ 500 ms dla krótkiego zdania. Kandydat z RTF > 1 na CPU nie może mówić płynnie bez buforowania całej odpowiedzi.

**Klasyfikacja dowodów** (stosowana w całym dokumencie):

| Etykieta | Znaczenie |
| --- | --- |
| **Zweryfikowane** | Sprawdzone bezpośrednio w repozytorium, kodzie, karcie modelu, API GitHub/Hugging Face (stan na 07.10.2026) |
| **Deklaracja autora** | Liczba lub cecha podana przez twórców, bez niezależnego potwierdzenia |
| **Raport społeczności** | Zgłoszenia GitHub, dyskusje, blogi użytkowników |
| **Szacunek własny** | Moja ekstrapolacja z architektury/rozmiaru; do potwierdzenia benchmarkiem |
| **Niezweryfikowane** | Brak wiarygodnych danych |

**Uwaga metodyczna:** nie uruchamiałem żadnego modelu lokalnie. Wszystkie liczby RTF/RAM pochodzą ze źródeł lub są oznaczone jako szacunek. Polskich nagrań nie oceniałem odsłuchowo — oceny jakości opierają się na metrykach autorów (WER), zgłoszeniach użytkowników i architekturze.

## 4. Lista kandydatów

Analizuję 8 kandydatów; 3 z nich (C1–C3) są realnymi opcjami dla asystenta, 2 (C4, C5) to opcje niszowe, a 3 (C6–C8) to duże modele, które zawodzą na CPU w trybie interaktywnym. Dane repozytoriów z API GitHub, stan na 07.10.2026.

| # | Kandydat | Model(e) PL | Typ | Repozytorium | Gwiazdki / ostatni push |
| --- | --- | --- | --- | --- | --- |
| C1 | [Pocket TTS](https://github.com/kyutai-labs/pocket-tts) + model PL | `shefowl/pocket-tts-polish-6l` (109,5M) | LM audio + Mimi codec, streaming | kyutai-labs/pocket-tts | 9,8k / 07.10.2026 |
| C2 | [Piper](https://github.com/OHF-Voice/piper1-gpl) | 5 oficjalnych + 4 WG Głos | VITS (ONNX) | OHF-Voice/piper1-gpl | 5,8k / 06.10.2026 |
| C3 | [Supertonic 3](https://github.com/supertone-inc/supertonic) | `supertonic-3` (31 języków, \~99M) | flow matching (ONNX) | supertone-inc/supertonic (**zarchiwizowane**) | 13,8k / 09.09.2026 |
| C4 | [RHVoice](https://github.com/RHVoice/RHVoice) | Alicja, Cezary, Magda, Michał, Natan | HTS (parametryczny) | RHVoice/RHVoice | 1,8k / 28.09.2026 |
| C5 | [XTTS-v2](https://huggingface.co/coqui/XTTS-v2) (coqui-tts, fork Idiap) | `XTTS-v2` (17 języków) | GPT + HiFi-GAN | idiap/coqui-ai-TTS | 2,3k / 02.10.2026 |
| C6 | [Chatterbox Multilingual V3](https://github.com/resemble-ai/chatterbox) | 0,5B, 23 języki | LM + flow decoder | resemble-ai/chatterbox | 26,8k / 21.07.2026 |
| C7 | [VoxCPM2](https://github.com/OpenBMB/VoxCPM) | 2B, 30 języków | tokenizer-free LM + diffusion | OpenBMB/VoxCPM | 38,4k / 30.09.2026 |
| C8 | [OmniVoice](https://github.com/k2-fsa/OmniVoice) | 600+ języków | diffusion LM | k2-fsa/OmniVoice | 14,3k / 06.10.2026 |

**Warstwa uruchomieniowa (nie kandydat-model):** [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (Apache-2.0, 15,2k gwiazdek, push 05.10.2026) uruchamia na CPU wszystkie 8 polskich głosów Piper oraz `supertonic-3-pl`, z API w C/C++/Python/Go/Rust i callbackiem zwracającym audio w trakcie generacji (gotowego serwera HTTP dla TTS nie weryfikowałem). To ważna opcja integracyjna dla C2 i C3.

**Odrzucone (z powodem):**

- **Kokoro-82M, Kitten TTS, MeloTTS, NeuTTS (Air/Nano), Qwen3-TTS** — brak języka polskiego (Zweryfikowane w README; Qwen3-TTS: 10 języków, NeuTTS: en/es/de/fr).
- **Pocket TTS oficjalny** — brak PL (en, fr, de, pt, it, es, nl); zgłoszenie #196 „Polish language” zamknięte odesłaniem do kodu treningowego. Dlatego C1 opiera się na modelu społecznościowym.
- **Fish Audio S2 Pro** — PL obsługiwany, ale FISH AUDIO RESEARCH LICENSE i rozmiar modelu wykluczają go z lokalnego CPU.
- **F5-TTS** — brak oficjalnego PL, architektura diffusion ciężka na CPU.
- **OuteTTS 1.0 0.6B** — PL na liście języków, Apache-2.0, backend llama.cpp; ale brak jakichkolwiek ocen polskiego, repozytorium bez push od 23.03.2026, a upstream `llama-tts` nie obsługuje wersji 1.0. Do obserwacji, nie do testu.
- **MMS-TTS (`facebook/mms-tts-pol`)** — szybki VITS, ale CC-BY-NC-4.0 i jeden głos z nagrań religijnych; jakość poniżej Pipera (Szacunek własny).
- **eSpeak NG** — polski działa, ale brzmienie formantowe/robotyczne. Zostaje jako fonemizator wewnątrz Pipera i ostateczny fallback, nie jako kandydat.
- **Mimic 3** — porzucony.

## 5. Szczegółowa analiza każdego kandydata

### C1. Pocket TTS + `pocket-tts-polish-6l`

Najlepiej rokujący kandydat dla polskiego asystenta na CPU, ale oparty na świeżym modelu jednej osoby.

- **Projekt:** silnik [kyutai-labs/pocket-tts](https://github.com/kyutai-labs/pocket-tts) — kod MIT, wagi bazowe CC-BY-4.0, 100M parametrów, PyTorch; kod treningowy opublikowany w sierpniu 2026 (Zweryfikowane). Polski model: [shefowl/pocket-tts-polish-6l](https://huggingface.co/shefowl/pocket-tts-polish-6l), CC-BY-4.0, plik `model.safetensors` 438 MB, utworzony 17.09.2026, 2 polubienia; wpisany do README Pocket TTS przez PR #315 (Zweryfikowane).
- **Polski:** model destylowany z 24 do 6 warstw, własny polski tokenizer sentencepiece (4000 tokenów), trening na 425,1 h polskiej mowy od 1248 mówców, w tym 2,3 h danych „number-focused”. Autor podaje WER 8,5% na 1339 wypowiedziach, 98,4% poprawnie przeczytanych nazwisk i 99,0% częstych słów (Deklaracja autora, z opisaną metodyką dwóch rozpoznawaczy ASR).
- **Czego autor nie zmierzył:** naturalności (brak MOS), długich wypowiedzi (max \~10 s), prozodii poza pauzami. Pauza po przecinku ma medianę 0,40 s wobec 0,12–0,23 s w mowie konwersacyjnej — może brzmieć „lektorsko”.
- **CPU:** RTF 0,21 (fp32) i 0,11 (int8, `quantize=True`), ładowanie 0,6–0,8 s, na „desktop CPU” bez podanego modelu (Deklaracja autora). Silnik bazowy: \~6× szybciej niż real-time na MacBook Air M4, 2 rdzenie; na VM x86 z 4 vCPU — 2,3–2,5× szybciej niż real-time (Deklaracja autora silnika).
- **RAM:** wagi w pamięci 341 MB (fp32) / 125 MB (int8) (Deklaracja autora). Cały proces z PyTorch: \~0,8–1,5 GB (Szacunek własny).
- **Streaming:** natywny, \~200 ms do pierwszego fragmentu audio (Deklaracja autora silnika); generacja autoregresywna klatkami Mimi, więc można przerwać w trakcie.
- **Voice cloning:** zero-shot z klipu referencyjnego 6–9 s, podobieństwo mówcy 0,946 przy suficie 0,958 (Deklaracja autora). Uwaga autora: **tempo nagrania referencyjnego zmienia WER nawet 3×** (8,9% vs 25,9%) — referencję trzeba dobrać testem. Stan głosu można policzyć raz (`get_state_for_audio_prompt`) i trzymać w pamięci.
- **Integracja:** Python API (`TTSModel.load_model(config="hf://...")`), CLI `generate` i `serve`; społecznościowe serwery zgodne z OpenAI API ze streamingiem, port C++ (PocketTTS.cpp, ONNX Runtime) i wsparcie w sherpa-onnx dla modeli bazowych. Czy porty ONNX obsłużą polski tokenizer — Niezweryfikowane.
- **Ryzyka:** pojedynczy autor, 0 pobrań w statystyce HF, brak niezależnych testów; licencja danych treningowych (m.in. „PWR AZON research recordings”) nieopisana. Łagodzi to licencja CC-BY-4.0 (można zachować kopię wag) i publiczny kod treningowy.

### C2. Piper (`piper1-gpl`)

Najbardziej dojrzały i przewidywalny wybór; jakość polskiego poprawna, ale wyraźnie „syntetyczna”.

- **Projekt:** [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl), GPL-3.0 (osadza espeak-ng), 5,8k gwiazdek, 142 otwarte zgłoszenia, wydania co 2–4 tygodnie (v1.5.0 17.07.2026 → v1.8.0 04.09.2026). Stare repozytorium `rhasspy/piper` (MIT) jest zarchiwizowane. Open Home Foundation szuka maintainerów (Zweryfikowane).
- **Polskie głosy oficjalne** ([voices.json](https://huggingface.co/rhasspy/piper-voices)): `bass-high` (114 MB, Apache-2.0, fine-tune z en\_US-lessac-high na \~10 000 segmentów), `darkman-medium`, `gosia-medium`, `mc_speech-medium` (po 63 MB, zbiory CC0), `mls_6892-low` (63 MB, 16 kHz, CC BY 4.0). Społecznościowe: `jarvis/justyna/meski/zenski_wg_glos-medium` (MIT, 1600–2000 próbek każdy) — użytkownik w sherpa-onnx #2402 ocenia je wyżej niż darkman/gosia (Raport społeczności).
- **Znane problemy PL:** otwarte [#267](https://github.com/OHF-Voice/piper1-gpl/issues/267) (08.2026) — liczebniki wymawiane błędnie („trzy” → „czy”) we wszystkich 6 testowanych polskich głosach (Raport społeczności). Wszystkie oficjalne głosy PL to fine-tune’y z angielskiego checkpointu, więc prozodia bywa płaska (Szacunek własny).
- **CPU:** RTF \~0,15–0,2 na laptopowym CPU (artykuł arXiv 2512.08006: 0,153 na i7-1255U dla głosu perskiego; Raport społeczności/badanie). Real-time na Raspberry Pi 4 (powszechny raport). Głos `high` jest wolniejszy od `medium` (Szacunek własny: \~2×).
- **RAM:** model 63–114 MB; proces \~150–300 MB (Szacunek własny).
- **Streaming:** `PiperVoice.synthesize()` zwraca generator `AudioChunk` — w praktyce po zdaniu (Zweryfikowane w docs/API\_PYTHON.md). Brak streamingu wewnątrz zdania, ale zdanie generuje się w dziesiątkach-setkach ms.
- **Voice cloning:** brak. Tylko fine-tuning nowego głosu (wymaga danych i praktycznie GPU do treningu).
- **Integracja:** `pip install piper-tts`, Python API, CLI (stdin → WAV/raw), serwer HTTP `python3 -m piper.http_server` (`/synthesize` → WAV, `/voices`, `/info`), protokół Wyoming (Home Assistant), sherpa-onnx.

### C3. Supertonic 3

Technicznie świetny i szybki, ale martwy projekt z restrykcyjną licencją modelu.

- **Projekt:** wydany 29.04.2026; repozytorium zarchiwizowane (komunikat z 23.07.2026: „no further development or official support”). Wagi w `supertone-oss-archive/supertonic-3`: ONNX \~400 MB (vector\_estimator 257 MB, vocoder 101 MB, text\_encoder 36 MB, duration 4 MB), 10 stałych stylów głosu F1–F5, M1–M5 (Zweryfikowane).
- **Polski:** język oficjalny wśród 31. WER 1,63% na Minimax-MLS-test, wobec 1,30 (VoxCPM2) i 0,64 (OmniVoice) (Deklaracja autora). Brak niezależnych ocen odsłuchowych PL (Niezweryfikowane).
- **Znany błąd:** w sherpa-onnx (C++) znaki prekomponowane, m.in. `ą`, były gubione z audio; naprawione w PR #3750 (07.2026). Implementacja Python robi NFKD poprawnie (Zweryfikowane).
- **CPU / RAM:** średni RTF 0,172 na CPU, szczyt pamięci 2,0 GiB (Deklaracja autora, wykres bez nazwy CPU). Blog: „1200+ znaków/s” (Raport społeczności).
- **Streaming:** brak natywnego; model nieautoregresywny generuje całą wypowiedź — streaming tylko przez dzielenie na zdania (Szacunek własny na podstawie architektury).
- **Voice cloning:** brak lokalnie. Voice Builder (usługa tworząca styl z nagrania) wyłączony po 31.08.2026.
- **Integracja:** przykłady ONNX w Python, C++, Go, Rust i in.; `supertonic-3-pl` w sherpa-onnx.

### C4. RHVoice

Najlżejszy polski syntezator „klasy czytnika ekranu” — zrozumiały, ale nienaturalny.

- **Projekt:** [RHVoice/RHVoice](https://github.com/RHVoice/RHVoice), silnik GPL-2.0, wydanie 1.18.4 (31.03.2026), aktywna praca nad modułem PL („Polish 1.21”, 04.2026). Synteza parametryczna HTS (Zweryfikowane).
- **Polski:** głosy Alicja, Cezary, Magda, Michał, Natan. Własny moduł językowy z regułami tekstu (liczby, skróty) (Zweryfikowane: moduł `data/languages/Polish`; jakość reguł Niezweryfikowana). Sam projekt przyznaje „brak naturalności typowy dla syntezatorów sklejających” (opis F-Droid).
- **CPU/RAM:** HTS działa nawet na słabych telefonach; RTF ≪ 0,05, RAM dziesiątki MB (Szacunek własny — brak opublikowanych liczb).
- **Licencje głosów:** Magda i Natan CC-BY-NC-ND-4.0; Alicja CC-BY-SA-4.0 (1.16.5) → CC-BY-4.0 (1.18.4) wg paczek Arch Linux. Debian umieszcza głosy w non-free.
- **Integracja:** speech-dispatcher, CLI `RHVoice-test`, biblioteka C++. Brak streamingu w sensie neuronowym, ale synteza jest praktycznie natychmiastowa. Brak klonowania.

### C5. XTTS-v2 (coqui-tts)

Polski pierwszej klasy i klonowanie, ale na CPU za wolny do rozmowy, a licencja blokuje użycie komercyjne.

- **Projekt:** kod utrzymywany w forku [idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS) (MPL-2.0, push 02.10.2026, PyPI `coqui-tts`). Wagi `coqui/XTTS-v2` bez zmian od 12.2023, licencja CPML (niekomercyjna). Firma Coqui została zamknięta, więc licencji komercyjnej nie da się kupić (Zweryfikowane: licencja na HF; status firmy — Raport społeczności).
- **CPU:** RTF \~2,05 na CPU (dyskusja coqui-ai/TTS #3695), \~1,7 (Raport społeczności), \~30 s opóźnienia na odpowiedź asystenta (idiap #507). Na Apple M5 Max RTF 0,34 i \~4,5 GB RAM (blog Contra Collective; nie jest jasne, czy tylko CPU).
- **Voice cloning:** zero-shot z \~6 s nagrania, działa na CPU, ale z tym samym RTF > 1.
- **Streaming:** `inference_stream` istnieje; przy RTF > 1 bufor i tak się wyczerpie.

### C6. Chatterbox Multilingual V3

Oficjalny polski i licencja MIT, ale złe raporty dla polskiego i brak danych CPU.

- **Projekt:** 0,5B parametrów, 23 języki z PL, MIT (Zweryfikowane). Wariant Nano (110M, 3× real-time na 8 rdzeniach CPU) jest **tylko angielski**.
- **Polski:** otwarte #286 „Polish Language is Very BAD”, #311 „strong English accent”, #256 problemy z ś, ń, ż, ą, ę (Raport społeczności, wersja V2). V3 deklaruje mniej halucynacji i lepszy akcent — dla PL Niezweryfikowane.
- **CPU:** brak oficjalnych liczb; otwarte błędy ładowania na CPU (#472, #533). Szacunek własny: RTF > 1 na typowym laptopie.

### C7. VoxCPM2

Prawdopodobnie najwyższa jakość polskiego z otwartych licencji, ale 2B parametrów to za dużo dla CPU w czasie rzeczywistym.

- **Projekt:** Apache-2.0 (kod i wagi), 30 języków z PL, 48 kHz, klonowanie i „voice design”, API streamingowe (Zweryfikowane).
- **Polski:** WER 1,90% w wewnętrznym teście autorów; 1,30 na Minimax-MLS wg tabeli Supertone (Deklaracja autorów).
- **CPU:** ścieżki GGUF (llama.cpp-omni, VoxCPM.cpp), ONNX (społeczność). Jedyna liczba: RTF \~1,76 (Q8\_0) na Apple M4 Pro z Metal, czyli z GPU. **Rozbieżność źródeł:** autorzy podają RTF \~0,3 na RTX 4090, Supertone zmierzył 1,04 na A100.

### C8. OmniVoice

Najszersze pokrycie języków i najlepszy WER PL w tabeli Supertone (0,64), ale na CPU RTF 10,98 i 8,3 GiB RAM (pomiar Supertone, czyli konkurenta — traktować ostrożnie). Apache-2.0. Do asystenta na CPU nieprzydatny.

## 6. Tabela porównawcza

Oznaczenia: \[A\] deklaracja autora, \[S\] raport społeczności, \[W\] szacunek własny, \[Z\] zweryfikowane. Ocena końcowa 1–10 to moja synteza dla scenariusza „polski asystent na CPU”.

| Kandydat | Polski | Jakość głosu | CPU | RAM | RTF / szybkość (CPU) | TTFA / latency | Streaming | Voice cloning | Integracja | Licencja | Aktywność projektu | Ocena |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 Pocket TTS + PL 6L | model społecznościowy, 425 h PL; WER 8,5% \[A\] | neuronowa, wysoka; MOS brak | x86-64/ARM, 2 rdzenie wystarczą \[A\] | 125 MB (int8) / 341 MB wagi \[A\]; proces \~1 GB \[W\] | 0,11 int8 / 0,21 fp32 \[A\] | \~200 ms do 1. fragmentu \[A, silnik\] | tak, natywny | tak, zero-shot 6–9 s, na CPU \[A\] | Python API, CLI, `serve`; porty C++/ONNX | MIT + CC-BY-4.0 | silnik bardzo aktywny; model PL 1 autor, 09.2026 | **8** |
| C2 Piper | oficjalny, 5+4 głosy \[Z\]; błąd liczebników #267 \[S\] | neuronowa, średnia | dowolny x86-64/ARM | model 63–114 MB \[Z\]; proces \~200 MB \[W\] | \~0,15–0,2 \[S\] | krótkie zdanie < 200 ms \[W\] | po zdaniach \[Z\] | brak | Python, CLI, HTTP, Wyoming, sherpa-onnx | GPL-3.0 (kod); głosy CC0/Apache/MIT/CC-BY | aktywny, wydania co 2–4 tyg. | **7,5** |
| C3 Supertonic 3 | oficjalny, WER 1,63% \[A\] | neuronowa, dobra \[A\]; odsłuch PL brak | x86-64/ARM | szczyt 2,0 GiB \[A\] | 0,172 \[A\] | całe zdanie; < 0,5 s dla krótkiego \[W\] | nie (dzielenie na zdania) | brak lokalnie | ONNX w wielu językach, sherpa-onnx | MIT + OpenRAIL-M | **zarchiwizowany** | **6,5** |
| C4 RHVoice | oficjalny moduł PL, 5 głosów \[Z\] | parametryczna, niska naturalność | minimalne | dziesiątki MB \[W\] | ≪ 0,05 \[W\] | natychmiast \[W\] | n/d (synteza natychmiastowa) | brak | speech-dispatcher, CLI, C++ | GPL-2.0; głosy częściowo NC-ND | aktywny | **5** |
| C5 XTTS-v2 | oficjalny (17 jęz.) | neuronowa, wysoka | AVX2, wiele rdzeni | \~2–4,5 GB \[S/W\] | \~1,7–2,05 \[S\] | sekundy; \~30 s/odpowiedź \[S\] | tak (`inference_stream`) | tak, 6 s; na CPU wolno | Python (coqui-tts) | MPL-2.0 + **CPML (NC)** | kod aktywny (Idiap), wagi z 2023 | **4** |
| C6 Chatterbox ML V3 | oficjalny; skargi na akcent \[S\] | neuronowa, wysoka (EN) | wiele rdzeni | ≥ 6 GB \[S\] | brak danych; > 1 \[W\] | sekundy \[W\] | brak oficjalnego | tak, \~10 s | Python | MIT | aktywny, błędy CPU otwarte | **3,5** |
| C7 VoxCPM2 | oficjalny, WER 1,9% \[A\] | neuronowa, bardzo wysoka \[A\] | wysokie | 4–8 GB \[W\] | brak danych CPU; 1,76 na M4 Pro Metal \[A\] | sekundy \[W\] | tak (API) | tak + voice design | Python, GGUF, ONNX (społ.) | Apache-2.0 | bardzo aktywny | **4** |
| C8 OmniVoice | 600+ jęz., WER 0,64 \[A, Supertone\] | neuronowa, bardzo wysoka | wysokie | 8,3 GiB \[A, Supertone\] | 10,98 \[A, Supertone\] | dziesiątki sekund \[W\] | nie | tak | Python | Apache-2.0 | bardzo aktywny | **2** |

## 7. Analiza języka polskiego

Najlepiej udokumentowaną polską jakość wśród modeli szybkich na CPU ma Pocket TTS PL (szczegółowa ewaluacja autora), a wśród modeli wielkich — VoxCPM2 i OmniVoice. Żaden kandydat nie ma niezależnego badania MOS dla polskiego.

| Aspekt | Pocket TTS PL | Piper | Supertonic 3 | RHVoice | XTTS / Chatterbox / VoxCPM2 |
| --- | --- | --- | --- | --- | --- |
| Status PL | społecznościowy, dedykowany | oficjalny, fine-tune z EN | oficjalny (1 z 31) | oficjalny moduł | oficjalny (multilingual) |
| Dane treningowe PL | 425 h, 1248 mówców \[A\] | \~1,6–10 tys. próbek na głos \[Z\] | brak danych | brak danych | brak danych |
| Wymowa | 98,4% nazwisk, 99% częstych słów \[A\] | błędy liczebników (#267) \[S\] | WER 1,63% \[A\] | zrozumiała, mechaniczna | Chatterbox: akcent angielski \[S\] |
| Prozodia | pauzy po przecinku długie (0,40 s) \[A\] | płaska \[W\] | brak danych | mechaniczna | XTTS: dobra \[S\] |
| Diakrytyki | własny tokenizer PL (ł, ę, ś, ż jako tokeny) \[A\] | przez espeak-ng; OK na Linux \[W\] | wymaga NFKD; błąd w sherpa-onnx naprawiony 07.2026 \[Z\] | OK | Chatterbox: #256 \[S\] |
| Liczby, daty, skróty | brak normalizatora; 2,3 h danych liczbowych \[A\] | espeak-ng rozwija cyfry; jakość wątpliwa \[S\] | brak normalizatora \[W\] | reguły w module PL \[Z\] | XTTS: wewnętrzna normalizacja num2words \[W\] |

**Wnioski dla PL:**

1. **Normalizacja tekstu musi być w demonie, nie w modelu.** Rozwijanie „15.08.2026”, „3,5 mln zł”, „dr”, „ns.”, „ul.” oraz odmiana liczebników („o 15:30” → „o piętnastej trzydzieści”) jest niezależna od silnika. `num2words(lang="pl")` daje formę mianownika, odmiana przez przypadki wymaga reguł kontekstowych.
2. **Problem #267 Pipera może dotyczyć fonemizacji izolowanych słów.** Trzeba go sprawdzić w benchmarku zdaniami z liczebnikami (sekcja 17).
3. **Pomiar WER autorów nie jest porównywalny między kandydatami.** Pocket PL (8,5%) mierzono na trudnym zestawie z nazwiskami i pojedynczymi słowami; Supertonic (1,63%) na Minimax-MLS-test. Dlatego benchmark używa jednego zestawu zdań i jednego ASR dla wszystkich.
4. **Uwaga autora Pocket PL o ASR:** model `stt_pl_fastconformer` zaniża ocenę nazwisk o 15 p.p. („głuchy na zbitki spółgłoskowe”). Do oceny wymowy użyć dwóch ASR lub odsłuchu.

## 8. Analiza wydajności CPU i RAM

Na CPU granica przebiega przy \~100M parametrów: Piper, Pocket TTS i Supertonic mają RTF 0,1–0,2, a modele ≥ 0,5B mają RTF ≈ 1–11. Żadna z liczb RTF nie pochodzi z tego samego sprzętu, więc ranking szybkości jest przybliżony do czasu benchmarku.

**Optymalizacje CPU:**

| Kandydat | Runtime | Kwantyzacja | Wątki |
| --- | --- | --- | --- |
| Pocket TTS PL | PyTorch; porty ONNX Runtime/C++ | int8 dynamiczna (`quantize=True`): 1,8× szybciej, 2,7× mniej pamięci, ≤ 0,7 p.p. utraty dokładności \[A\] | 2 rdzenie \[A\]; skaluje słabo, bo batch=1 |
| Piper | ONNX Runtime | brak oficjalnej; int8 ONNX możliwe w sherpa-onnx \[W\] | ustawiane w onnxruntime |
| Supertonic 3 | ONNX Runtime | OnnxSlim (wersja 2) \[Z\] | ustawiane w onnxruntime |
| RHVoice | natywny C++ | n/d | 1 |
| XTTS-v2 | PyTorch | brak praktycznej | wiele |
| VoxCPM2 | PyTorch / GGUF / ONNX | Q8\_0 GGUF \[Z\] | wiele |

**Klasy sprzętu** (Szacunek własny na podstawie RTF z sekcji 6; do potwierdzenia benchmarkiem):

- Low-end: mini PC / laptop klasy Intel N100 (4C/4T), 8 GB RAM.
- Typowy: laptop/desktop 6–8 rdzeni (np. Ryzen 5 7640U, Core i5-13500H), 16–32 GB RAM.
- High-end: desktop 16+ rdzeni (np. Ryzen 9 7950X, Core i9-14900K), 64 GB RAM.

| Kandydat | Low-end | Typowy | High-end |
| --- | --- | --- | --- |
| C1 Pocket TTS PL (int8) | Używalny z kompromisami (RTF \~0,3–0,6, poza streamingiem słaba rezerwa) | Komfortowy | Komfortowy |
| C2 Piper (medium) | Komfortowy | Komfortowy | Komfortowy |
| C3 Supertonic 3 | Używalny z kompromisami (2 GiB RAM, brak streamingu) | Komfortowy | Komfortowy |
| C4 RHVoice | Komfortowy | Komfortowy | Komfortowy |
| C5 XTTS-v2 | Niepraktyczny | Ledwo używalny (tylko offline) | Używalny z kompromisami (RTF \~1 lub niżej, wymaga buforowania) |
| C6 Chatterbox ML V3 | Niepraktyczny | Ledwo używalny (offline) | Ledwo używalny |
| C7 VoxCPM2 | Niepraktyczny | Niepraktyczny | Ledwo używalny (GGUF Q8, offline) |
| C8 OmniVoice | Niepraktyczny | Niepraktyczny | Niepraktyczny (RTF \~11 \[A, Supertone\]) |

**RAM:** RHVoice (dziesiątki MB) < Piper (\~0,2 GB) < Pocket TTS PL int8 (0,125 GB wagi + PyTorch) < Supertonic 3 (2,0 GiB szczyt) < XTTS-v2 (\~2–4,5 GB) < Chatterbox (≥ 6 GB wg dokumentacji społeczności) < OmniVoice (8,3 GiB). Sam import PyTorch na CPU kosztuje kilkaset MB, co sprawia, że Pocket TTS w Pythonie zużyje więcej niż same wagi (Szacunek własny).

## 9. Analiza latency i streamingu

O odczuwalnym opóźnieniu asystenta decyduje TTFA pierwszego zdania, a nie RTF całej odpowiedzi. Dlatego liczy się: (a) czy silnik zwraca audio przed końcem zdania, (b) ile trwa synteza pierwszego krótkiego zdania, (c) czy da się przerwać generację.

| Kandydat | Granulacja | TTFA krótkiego zdania (CPU) | Przerwanie | Uwagi |
| --- | --- | --- | --- | --- |
| Pocket TTS PL | fragmenty audio w trakcie zdania (autoregresja klatek) | \~200 ms \[A, silnik\] | tak, między klatkami | najlepszy profil dla rozmowy; długi tekst „nieskończony” wg README |
| Piper | zdanie (`synthesize()` → `AudioChunk`) | dziesiątki–setki ms \[W\] | tak, między zdaniami | zdanie generuje się szybciej niż trwa jego odtworzenie, więc pipeline zdaniowy wystarcza |
| Supertonic 3 | cała wypowiedź (nieautoregresywny) | \~RTF × długość zdania, np. \~0,5 s dla 3 s audio \[W\] | między zdaniami | wymaga dzielenia tekstu na zdania |
| RHVoice | ciągła | natychmiast \[W\] | tak | — |
| XTTS-v2 | fragmenty (`inference_stream`) | sekundy \[S\] | tak | przy RTF > 1 odtwarzanie się zatrzymuje |
| Chatterbox / VoxCPM2 / OmniVoice | VoxCPM2: fragmenty; pozostali: całość | sekundy–dziesiątki sekund \[W\] | różnie | nie do rozmowy na CPU |

**Wzorzec dla asystenta (wszyscy kandydaci):** LLM streamuje tokeny → demon tnie tekst na zdania (lub frazy po przecinku dla pierwszego zdania) → normalizacja PL → synteza → kolejka PCM → odtwarzacz. Pierwsze zdanie warto skrócić (np. do pierwszego przecinka), by obniżyć TTFA modeli nieautoregresywnych.

**Przerwanie (barge-in):** demon musi umieć natychmiast: wyczyścić kolejkę PCM, anulować bieżącą generację (token anulowania sprawdzany między fragmentami/zdaniami) i zatrzymać odtwarzanie. Dla Pocket TTS i Pipera jest to proste, bo oba zwracają generatory.

## 10. Analiza voice cloning

Praktyczne klonowanie polskiego głosu na CPU w czasie rzeczywistym oferuje tylko Pocket TTS PL. Pozostałe modele z klonowaniem działają na CPU wyłącznie offline.

| Kandydat | Typ | Min. nagranie | Na CPU | Jakość PL klonu | Interaktywne? | Osobne narzędzie? |
| --- | --- | --- | --- | --- | --- | --- |
| Pocket TTS PL | zero-shot | 6–9 s (testowane) \[A\] | tak, ten sam RTF 0,11–0,21 | cos 0,946 (sufit 0,958) \[A\]; silnie zależy od tempa referencji | tak | nie; stan głosu liczony raz i trzymany w RAM |
| XTTS-v2 | zero-shot | \~6 s | tak, RTF \~1,7–2 \[S\] | dobra wg społeczności \[S\] | nie | nie |
| Chatterbox ML V3 | zero-shot | \~10 s | wolno; błędy ładowania \[S\] | akcent EN w V2 \[S\] | nie | nie |
| VoxCPM2 | zero-shot + voice design | kilka s \[A\] | bardzo wolno \[W\] | brak danych | nie | nie |
| OmniVoice | zero-shot | kilka s \[A\] | RTF \~11 \[A, Supertone\] | brak danych | nie | nie |
| Piper | adaptacja (fine-tuning) | godziny nagrań, w praktyce GPU do treningu | synteza tak, trening nie | zależy od danych | synteza tak | tak (piper train) |
| Supertonic 3, RHVoice | stałe głosy | — | — | — | — | Voice Builder wyłączony 31.08.2026 |

**Ważne zastrzeżenia:**

- Klonowanie w Pocket TTS bazowym jest za bramką HF (`kyutai/pocket-tts` gated=auto; istnieje osobny `pocket-tts-without-voice-cloning`). Model PL nie ma bramki (Zweryfikowane).
- Autorzy Pocket TTS i modelu PL proszą o niekorzystanie z klonowania bez wyraźnej, legalnej zgody osoby i o nieprzedstawianie audio jako autentycznych nagrań. Dla asystenta: klonować tylko własny głos lub głos z licencją.
- Praktyczna procedura dla Pocket PL: nagrać 3–5 kandydatów referencji 6–9 s w tempie \~2 słowa/s, wygenerować po 12 zdań testowych, wybrać referencję z najniższym WER (procedura zalecana przez autora).

## 11. Analiza integracji z `local-tts-daemon`

Najlepiej przygotowany do roli backendu demona jest Piper (stabilne API, serwer HTTP, Wyoming, małe zależności); Pocket TTS jest drugi i wymaga cienkiej warstwy własnej. Wszyscy kandydaci C1–C3 pozwalają trzymać model w RAM w jednym procesie.

| Cecha | Pocket TTS PL | Piper | Supertonic 3 (Python/sherpa-onnx) | RHVoice |
| --- | --- | --- | --- | --- |
| Python API | tak (`TTSModel`, `generate_audio`, streaming) | tak (`PiperVoice.synthesize` generator) | tak (ONNX, przykład `example_onnx.py`) / sherpa-onnx | brak oficjalnego; ctypes/CLI |
| CLI | `pocket-tts generate`, `serve` | `piper` (stdin → WAV/raw PCM) | przykłady | `RHVoice-test` |
| HTTP / WebSocket | `serve` + społeczne serwery OpenAI-compatible ze streamingiem \[S\] | `piper.http_server` (`/synthesize` → WAV) \[Z\] | brak oficjalnego | speech-dispatcher |
| Format wyjścia | tensor float → PCM 24 kHz (Mimi) \[W\] | int16 PCM 22,05 kHz (medium/high), 16 kHz (low) \[Z\] | float PCM \[W\] | PCM |
| Start procesu | ładowanie modelu 0,6–0,8 s \[A\] + import PyTorch (kilka s) \[W\] | < 1 s \[W\] | kilka s (400 MB ONNX) \[W\] | natychmiast |
| Współbieżność | batch=1; równoległe żądania = osobne wątki/instancje \[W\] | instancje dzielone między wątkami ONNX Runtime \[W\] | jak Piper \[W\] | proces na żądanie |
| Zależności | PyTorch CPU (instalować z indeksu `whl/cpu`, inaczej pobiera CUDA) \[Z\] | onnxruntime, espeak-ng (wbudowany) | onnxruntime | C++ |

**Wniosek architektoniczny:** demon powinien mieć własny interfejs backendu (`synthesize_stream(text, voice) → iterator[PCM]` + `cancel()`), własną normalizację PL i własny serwer (Unix socket/HTTP + WebSocket), a silniki traktować jako biblioteki w tym samym procesie. Nie warto opierać się na serwerach HTTP dostarczanych z silnikami — Piper zwraca cały WAV, a serwery Pocket TTS są społecznościowe. Resampling do jednej częstotliwości (np. 24 kHz lub 48 kHz dla PipeWire) robi demon.

## 12. Analiza licencji

Do użytku osobistego wszyscy kandydaci C1–C4 są bezpieczni. Do użytku komercyjnego bez zastrzeżeń nadają się Pocket TTS PL (z atrybucją), VoxCPM2, Chatterbox i Piper z wybranymi głosami; XTTS-v2 odpada.

| Kandydat | Kod | Wagi / głosy | Komercyjnie | Redystrybucja | Flagi |
| --- | --- | --- | --- | --- | --- |
| Pocket TTS PL | MIT | CC-BY-4.0 \[Z\] | tak, z atrybucją | tak, z atrybucją | prośba o zgodę na klonowanie; licencja części danych treningowych PL nieopisana \[Niezweryfikowane\] |
| Piper | GPL-3.0 (`piper1-gpl`) \[Z\] | darkman/gosia/mc\_speech: zbiory CC0; bass-high: Apache-2.0; mls\_6892: CC BY 4.0; WG Głos: MIT \[Z\] | tak | GPL-3.0 = copyleft przy dystrybucji binarki z Piperem | oficjalne głosy PL są fine-tune’ami z `en_US-lessac`; licencja danych lessac może mieć własne ograniczenia \[Niezweryfikowane\]; użycie przez sieć/lokalnie nie wyzwala GPL |
| Supertonic 3 | MIT | OpenRAIL-M \[Z\] | tak, z ograniczeniami użycia (Załącznik A) | tylko z przeniesieniem ograniczeń | licencjodawca zastrzega prawo ograniczeń „runtime” (pkt 7); projekt martwy |
| RHVoice | GPL-2.0 | Alicja CC-BY-4.0 (1.18.4); Magda, Natan CC-BY-NC-ND-4.0 \[S, paczki Arch\] | tylko Alicja (i ew. inne, do sprawdzenia) | Debian: non-free | niejednolite licencje głosów (zgłoszenie #885) |
| XTTS-v2 | MPL-2.0 | CPML (niekomercyjna) \[Z\] | **nie** | ograniczona | firmy Coqui nie ma — licencji komercyjnej nie da się nabyć |
| Chatterbox ML V3 | MIT | MIT \[Z\] | tak | tak | wbudowany watermark Perth (wg dokumentacji Resemble) \[W\] |
| VoxCPM2 | Apache-2.0 | Apache-2.0 \[Z\] | tak | tak | — |
| OmniVoice | Apache-2.0 | brak pola licencji w karcie HF \[Z\] | do wyjaśnienia | do wyjaśnienia | — |

**Zależności:** espeak-ng (GPL-3.0) jest powodem licencji GPL Pipera; PyTorch (BSD-3), ONNX Runtime (MIT), sherpa-onnx (Apache-2.0) nie wprowadzają ograniczeń.

## 13. Ranking

Pocket TTS PL wygrywa w 5 z 8 kategorii (wśród rozwiązań praktycznych na CPU), RHVoice w 2 (szybkość, RAM), Piper w 1 (backend demona) i jest drugi w 4 kolejnych. Rankingi zakładają deklaracje autorów do czasu benchmarku.

| Kategoria | 1. miejsce | 2. miejsce | 3. miejsce | Uzasadnienie |
| --- | --- | --- | --- | --- |
| Najlepszy ogólnie | Pocket TTS PL | Piper | Supertonic 3 | Pocket łączy neuronową jakość PL, RTF 0,11–0,21, streaming i klonowanie; Piper jest pewniejszy, ale słabszy brzmieniowo; Supertonic traci przez archiwizację i licencję |
| Najlepszy dla polskiego | VoxCPM2 / OmniVoice (jakość bez względu na CPU) → wśród praktycznych: Pocket TTS PL | Supertonic 3 | Piper (WG Głos, bass-high) | Pocket ma dedykowany polski korpus 425 h i tokenizer; Supertonic ma niski WER, ale brak odsłuchu; Piper ma błąd liczebników |
| Najszybszy na CPU | RHVoice | Piper | Pocket TTS PL int8 ≈ Supertonic 3 | HTS jest o rząd wielkości lżejszy \[W\]; Piper RTF \~0,15–0,2 \[S\]; Pocket int8 0,11 i Supertonic 0,172 \[A\] na różnym sprzęcie |
| Najniższe zużycie RAM | RHVoice | Piper | Pocket TTS PL int8 | dziesiątki MB vs \~0,2 GB vs 125 MB wag + PyTorch |
| Najlepszy voice cloning na CPU | Pocket TTS PL | XTTS-v2 | Chatterbox ML V3 | Pocket jako jedyny klonuje szybciej niż real-time; XTTS działa, ale RTF \~2 i licencja NC |
| Najlepszy do interaktywnego asystenta | Pocket TTS PL | Piper | Supertonic 3 | TTFA \~200 ms i przerywalność w trakcie zdania; Piper niemal równie szybki dzięki pipeline’owi zdaniowemu |
| Najlepszy do `local-tts-daemon` | Piper | Pocket TTS PL | Supertonic 3 (przez sherpa-onnx) | Piper: stabilne API, wydania, Wyoming, małe zależności; Pocket: dobre API, ale ciężki PyTorch i model jednej osoby |
| Kompromis jakość/CPU/RAM/latency | Pocket TTS PL int8 | Piper (`*_wg_glos-medium`) | Supertonic 3 | int8 kosztuje ≤ 0,7 p.p. dokładności przy 1,8× szybszej pracy \[A\] |

## 14. Top 3

Do dalszych testów: **Pocket TTS PL**, **Piper**, **Supertonic 3**. XTTS-v2 nie wchodzi mimo dobrego polskiego: RTF \~2 na CPU i licencja CPML.

|  | 1. Pocket TTS + `pocket-tts-polish-6l` | 2. Piper (`piper1-gpl`) | 3. Supertonic 3 |
| --- | --- | --- | --- |
| Dlaczego na liście | jedyny szybki model z dedykowanym polskim korpusem, streamingiem i klonowaniem | sprawdzony, najprostszy w utrzymaniu, 9 głosów PL | najniższy deklarowany WER PL wśród szybkich modeli |
| Główne zalety | RTF 0,11 (int8), TTFA \~200 ms, 125 MB wag, klonowanie z 6–9 s | RTF \~0,2, \~0,2 GB RAM, HTTP/Wyoming/sherpa-onnx, aktywne wydania | RTF 0,172, 31 języków w jednym modelu, ONNX bez PyTorch |
| Główne słabości | model jednej osoby, brak MOS i testów długich tekstów, długie pauzy po przecinkach, PyTorch | jakość „syntetyczna”, błąd liczebników #267, brak klonowania | zarchiwizowany, OpenRAIL-M, 2,0 GiB RAM, brak streamingu i klonowania |
| Oczekiwane CPU/RAM | 2 rdzenie; \~1 GB procesu \[W\] | 1–2 rdzenie; \~0,2 GB \[W\] | 2–4 rdzenie; 2,0 GiB \[A\] |
| Jakość PL | wysoka (deklarowana) | średnia; najlepsze: WG Głos, bass-high \[S\] | dobra wg WER, nieocenione odsłuchowo |
| Oczekiwana latency | TTFA \~200–400 ms \[A/W\] | TTFA \~100–300 ms dla krótkiego zdania \[W\] | \~0,3–0,8 s dla krótkiego zdania \[W\] |
| Voice cloning | tak, na CPU | nie (tylko fine-tuning) | nie |
| Złożoność integracji | średnia (PyTorch CPU, streaming tensorów) | niska | średnia (własny pipeline ONNX lub sherpa-onnx) |
| Licencje | MIT + CC-BY-4.0, atrybucja | GPL-3.0 kod; głosy CC0/Apache/MIT | MIT + OpenRAIL-M z ograniczeniami |
| Co niepewne | rzeczywista naturalność, długie teksty, liczby, wydajność na N100, stabilność w czasie | czy #267 dotyczy liczb w zdaniach, jak brzmi dłuższy tekst | jakość odsłuchowa PL, RAM na słabym sprzęcie, przyszłość wag |

## 15. Jedna rekomendacja

**Pocket TTS z modelem `shefowl/pocket-tts-polish-6l` w trybie int8** — pod warunkiem, że przejdzie benchmark z sekcji 17 z wynikiem ≥ Piper w kategorii jakości PL.

Uzasadnienie według priorytetów użytkownika:

1. **Jakość polskiego:** jedyny szybki model dostrojony (fine-tune angielskiego Pocket TTS 24L, potem destylacja do 6 warstw) na 425 h polskiej mowy, z polskim tokenizerem i udokumentowaną, uczciwą ewaluacją (autor raportuje też to, czego nie zmierzył).
2. **CPU:** RTF 0,11 (int8) daje \~9× zapasu względem real-time na desktopie; nawet 3–4× wolniejszy CPU zostaje poniżej RTF 0,5.
3. **Latency:** natywny streaming, \~200 ms do pierwszego audio.
4. **RAM:** 125 MB wag (int8).
5. **Streaming i przerwania:** autoregresja klatkowa = naturalne punkty anulowania.
6. **Voice cloning:** jako jedyny praktyczny na CPU.
7. **Kondycja:** silnik Kyutai aktywny (push 07.10.2026, kod treningowy publiczny). Ryzyko porzucenia modelu PL jest realne, ale CC-BY-4.0 pozwala zachować wagi, a kod treningowy pozwala wytrenować własny model (autor: 2,4 h na 1×H100 + 62 min na Radeon 7900 XTX).
8. **Licencja:** MIT + CC-BY-4.0, bez ograniczeń komercyjnych.

**Dlaczego nie Piper jako główny:** wygrywa dojrzałością, ale przegrywa w kryterium nr 1 (jakość PL) i nie ma klonowania. Zostaje **obowiązkowym backendem awaryjnym** w demonie: start < 1 s, minimalne zależności, działa na każdym sprzęcie.

**Warunek odwrotu:** jeśli Pocket PL w benchmarku uzyska niższą ocenę odsłuchową niż Piper WG Głos lub RTF > 0,5 na docelowym CPU, głównym silnikiem zostaje Piper, a Pocket PL — opcją dla klonowanego głosu.

## 16. Ryzyka i niewiadome

| Ryzyko / niewiadoma | Dotyczy | Prawdopodobieństwo | Wpływ | Mitygacja |
| --- | --- | --- | --- | --- |
| Deklaracje modelu PL (WER, RTF) nie powtórzą się na naszym sprzęcie | Pocket PL | średnie | wysoki | benchmark z sekcji 17 przed decyzją |
| Model PL porzucony lub usunięty z HF | Pocket PL | średnie | średni | lokalna kopia wag (CC-BY-4.0), przypięta rewizja `@a8630f2a...`, kod treningowy jako plan B |
| Prozodia „lektorska” (długie pauzy) męczy w rozmowie | Pocket PL | średnie | średni | test odsłuchowy; dobór referencji; skracanie przecinków w normalizatorze |
| Niestabilność na długich tekstach (nie testowano > 10 s) | Pocket PL | średnie | średni | dzielenie na zdania w demonie |
| Błędna wymowa liczebników (#267) | Piper | wysokie (zgłoszone) | średni | test; normalizacja PL; ewentualnie podmiana fonemizatora |
| Brak poprawek bezpieczeństwa i rozwoju | Supertonic 3 | pewne | średni | traktować jako zamrożony artefakt; uruchamiać przez sherpa-onnx |
| Licencja danych treningowych modeli | Pocket PL, głosy Piper (lessac) | niskie–średnie | wysoki przy komercji | przed użyciem komercyjnym zapytać autorów / wybrać głosy na CC0 |
| Nadużycie klonowania głosu | Pocket PL, XTTS | — | prawny/etyczny | klonować tylko głosy z udokumentowaną zgodą |
| PyTorch CPU ciągnie CUDA przy złej instalacji | Pocket PL | wysokie bez uwagi | niski | instalacja z indeksu `download.pytorch.org/whl/cpu` |

**Nadal niezweryfikowane:** rzeczywiste RTF na x86 klasy N100 dla wszystkich kandydatów; zużycie RAM całego procesu (nie tylko wag); jakość odsłuchowa Supertonic 3 dla PL; czy porty ONNX Pocket TTS (sherpa-onnx, PocketTTS.cpp) obsłużą polski tokenizer; licencje głosów RHVoice Cezary i Michał.

## 17. Plan benchmarku

Cel: w jeden dzień roboczy rozstrzygnąć Pocket TTS PL vs Piper vs Supertonic 3 na tym samym sprzęcie, tymi samymi zdaniami i tymi samymi metrykami.

### 17.1. Środowisko (zapisać w raporcie)

- Sprzęt: model CPU (`lscpu`), liczba rdzeni/wątków, RAM (`free -h`), governor (`cpupower frequency-info`), zasilanie sieciowe.
- System: dystrybucja i jądro (`uname -a`, `/etc/os-release`).
- Runtime: Python 3.12 (osobny `venv` na kandydata), wersje `piper-tts`, `pocket-tts`, `onnxruntime`, `torch` (`pip freeze > freeze.txt`).
- Modele (przypięte): `pl_PL-zenski_wg_glos-medium`, `pl_PL-bass-high`, `pl_PL-gosia-medium` (Piper); `shefowl/pocket-tts-polish-6l@a8630f2a39055d3e5a91acb7922e31bd0c506cfe` (fp32 i int8); `supertone-oss-archive/supertonic-3` (styl F1 i M1, `lang="pl"`).
- Najlepiej powtórzyć na dwóch klasach sprzętu: typowy laptop i low-end (np. N100).

### 17.2. Instalacja

```bash
# Piper
python3.12 -m venv ~/bench/piper && ~/bench/piper/bin/pip install piper-tts psutil
~/bench/piper/bin/python -m piper.download_voices pl_PL-gosia-medium pl_PL-bass-high

# Pocket TTS (PyTorch tylko CPU!)
python3.12 -m venv ~/bench/pocket && ~/bench/pocket/bin/pip install pocket-tts soundfile psutil \
  --extra-index-url https://download.pytorch.org/whl/cpu

# Supertonic 3 (archiwum)
git clone https://github.com/supertone-oss-archive/supertonic ~/bench/supertonic-src
# dalej wg py/README: pobranie assets z HF supertone-oss-archive/supertonic-3
```

### 17.3. Zdania testowe

| ID | Kategoria | Tekst |
| --- | --- | --- |
| S1 | krótkie, konwersacyjne | Jasne, już sprawdzam. |
| S2 | krótkie, pytanie | Czy mam włączyć światło w kuchni? |
| M1 | liczby | Na koncie zostało trzy tysiące dwieście piętnaście złotych i czterdzieści dwa grosze. |
| M2 | liczby w cyfrach | Temperatura spadnie do -3°C, a wiatr osiągnie 45 km/h. |
| M3 | daty i godziny | Spotkanie przeniesiono na 15.11.2026 r. o godz. 14:30. |
| M4 | skróty i nazwy | Dr hab. Krzysztof Wiśniewski z ul. Żwirki i Wigury przyjmuje m.in. we wtorki. |
| M5 | nazwiska, zbitki | Pani Agnieszka Brzezińska i pan Grzegorz Chmielewski przyjechali ze Szczebrzeszyna. |
| M6 | interpunkcja | Uwaga! To nie jest test — to prawdziwy alarm; proszę zachować spokój… i wyjść. |
| M7 | diakrytyki | Zażółć gęślą jaźń, a potem włącz radio. |
| M8 | liczebniki izolowane (#267) | Jeden, dwa, trzy, cztery, pięć, sześć. |
| L1 | długi tekst (\~60 s) | akapit \~150 słów odpowiedzi asystenta (np. opis pogody, przepis, instrukcja) |

Każde zdanie w dwóch wariantach: surowe (test silnika) i po normalizacji (test pipeline’u), np. M3 → „piętnastego listopada dwa tysiące dwudziestego szóstego roku o godzinie czternastej trzydzieści”.

### 17.4. Testy

1. **Cold start:** czas od uruchomienia procesu do pierwszej próbki audio dla S1 (`/usr/bin/time -v`, wraz z importem bibliotek).
2. **Warm model:** model załadowany; 3 przebiegi rozgrzewające, potem 10 pomiarów na zdanie; raportować medianę i p95.
3. **TTFA:** czas od wywołania do pierwszego fragmentu audio z generatora (Pocket: pierwszy chunk; Piper: pierwszy `AudioChunk`; Supertonic: koniec syntezy pierwszego zdania).
4. **Total + RTF:** RTF = czas generacji / długość audio.
5. **Long-form (L1):** RTF, czy pojawiają się błędy (pominięcia, powtórzenia, „czytanie referencji”).
6. **Powtarzalność:** 100 kolejnych syntez M1–M8 — dryf czasu i RAM (wycieki).
7. **Streaming:** czy odtwarzanie przez `pw-play` ruszając od pierwszego fragmentu nie ma przerw (underrun) przy L1.
8. **Wątki:** powtórzyć 2 i 4 z `taskset -c 0-1`, `0-3`, wszystkie rdzenie; `OMP_NUM_THREADS`/`torch.set_num_threads` zgodnie z maskami.
9. **RAM:** szczytowy RSS procesu (`psutil` co 50 ms lub `/usr/bin/time -v` → „Maximum resident set size”).
10. **CPU:** `pidstat -u -p <PID> 1` w trakcie L1 — średnie % CPU.

### 17.5. Szkielet pomiaru (Python)

```python
import time, threading, psutil, os

def measure(stream_fn, text, sr):
    proc = psutil.Process(os.getpid()); peak = [proc.memory_info().rss]; stop = False
    def sampler():
        while not stop:
            peak[0] = max(peak[0], proc.memory_info().rss); time.sleep(0.05)
    th = threading.Thread(target=sampler); th.start()
    t0 = time.perf_counter(); ttfa = None; samples = 0
    for pcm in stream_fn(text):          # iterator fragmentów PCM (numpy / bytes)
        if ttfa is None: ttfa = time.perf_counter() - t0
        samples += len(pcm)
    total = time.perf_counter() - t0; stop = True; th.join()
    dur = samples / sr
    return dict(ttfa=ttfa, total=total, audio_s=dur, rtf=total / dur, peak_rss_mb=peak[0] / 2**20)
```

Adaptery `stream_fn`: Piper — `(np.frombuffer(c.audio_int16_bytes, dtype=np.int16) for c in voice.synthesize(text))`; Pocket — streamingowa metoda generacji z dokumentacji Python API (lub `generate_audio` jako wariant bez streamingu); Supertonic — jeden fragment na zdanie.

### 17.6. Ocena jakości

- **Obiektywna:** WER/CER przez dwa ASR (np. `parakeet-tdt-0.6b-v3` i Whisper large-v3 — mogą działać na CPU offline). Osobno liczyć poprawność liczebników (M1, M2, M8) i nazwisk (M5).
- **Subiektywna:** ślepy odsłuch (pliki z losowymi nazwami), ≥3 słuchaczy natywnych, skala MOS 1–5 osobno dla: naturalności, wymowy, prozodii. Dołączyć 1 nagranie ludzkie jako kotwicę.

### 17.7. Punktacja

| Kryterium | Waga | Sposób punktowania (0–10) |
| --- | --- | --- |
| Jakość PL (MOS naturalność + wymowa) | 35% | MOS × 2 |
| Poprawność treści (WER, liczby, nazwiska) | 10% | 10 − WER\[%\] (min 0) |
| TTFA krótkiego zdania (warm) | 15% | 10 przy ≤ 200 ms, 0 przy ≥ 2000 ms, liniowo |
| RTF (typowy CPU, warm) | 15% | 10 przy ≤ 0,1, 0 przy ≥ 1,0, liniowo |
| Szczytowy RSS | 10% | 10 przy ≤ 300 MB, 0 przy ≥ 4 GB, liniowo |
| Streaming / przerywalność | 5% | 10 wewnątrz zdania, 6 po zdaniach, 0 brak |
| Voice cloning na CPU | 5% | 10 RTF < 0,5, 5 offline, 0 brak |
| Integracja + licencja + kondycja | 5% | ocena ekspercka wg sekcji 11–12 |

**Kryteria dyskwalifikujące:** RTF > 0,8 na typowym CPU, błędy treści (pominięcia/halucynacje) w > 5% zdań, underrun w teście streamingu.

## 18. Plan prototypu

`local-tts-daemon`: jeden proces Pythona (asyncio) jako usługa systemd użytkownika, model trzymany w RAM, wymienne backendy (Pocket TTS PL → Piper jako fallback), własna normalizacja PL i streaming PCM.

### 18.1. Przepływ żądania

1. Klient (asystent/LLM) wysyła tekst przyrostowo przez WebSocket lub Unix socket: `{"id", "text_delta", "voice", "final"}`.
2. **Segmenter** składa zdania z delt; pierwsze zdanie może być wypuszczone już na pierwszym przecinku (niższe TTFA).
3. **Normalizator PL**: liczby (`num2words(lang="pl")` + reguły przypadków dla „o 14:30”, „z 3 osób”), daty, jednostki (km/h, °C, zł), słownik skrótów (dr, hab., ul., m.in., np., tzn.), emotikony/markdown/URL usuwane.
4. **Backend** `synthesize_stream(text, voice) → AsyncIterator[np.int16]` uruchamiany w puli wątków; sprawdza `cancel_event` między fragmentami.
5. **Resampler** do 48 kHz mono int16 (lub natywne 24/22,05 kHz, jeśli odtwarzacz to obsłuży).
6. **Wyjście:** (a) odtwarzanie lokalne przez PipeWire (`sounddevice` lub `pw-cat`), (b) strumień PCM/WAV/Opus z powrotem do klienta.
7. **Sterowanie:** `cancel(id)` czyści kolejkę i przerywa generację w ≤ 50 ms; `pause`, `resume`, `status`.

### 18.2. API

| Endpoint | Opis |
| --- | --- |
| `WS /v1/stream` | przyrostowy tekst → binarne ramki PCM + zdarzenia JSON (`segment_start`, `segment_end`, `done`) |
| `POST /v1/speak` | cały tekst → odtworzenie lokalne, zwraca `id` |
| `POST /v1/synthesize` | cały tekst → WAV/Opus (zgodność z narzędziami) |
| `POST /v1/cancel/{id}` | przerwanie (barge-in) |
| `GET /v1/voices`, `GET /healthz` | lista głosów/backendów, stan, załadowane modele, RSS |

### 18.3. Kamienie milowe

- [ ] M0 (1 dzień): benchmark z sekcji 17; decyzja Pocket PL vs Piper.
- [ ] M1 (2–3 dni): szkielet demona, backend Piper, odtwarzanie PipeWire, `cancel`.
- [ ] M2 (2–3 dni): normalizator PL z testami jednostkowymi na zdaniach M1–M8 + 100 przykładach z logów asystenta.
- [ ] M3 (2 dni): backend Pocket TTS PL (int8, stan głosu w cache, `torch.set_num_threads(2)`), streaming fragmentów.
- [ ] M4 (1 dzień): WebSocket z przyrostowym tekstem z LLM; pomiar TTFA end-to-end (od pierwszego tokenu LLM do pierwszego dźwięku).
- [ ] M5 (1 dzień): fallback automatyczny (błąd/timeout Pocket → Piper), usługa `systemd --user`, logi i metryki.
- [ ] M6 (opcjonalnie): klonowany głos własny (procedura z sekcji 10), backend Supertonic 3 przez sherpa-onnx.

**Cel akceptacyjny prototypu:** TTFA end-to-end ≤ 400 ms dla krótkiej odpowiedzi na typowym laptopie, brak przerw przy odpowiedzi 60 s, przerwanie ≤ 100 ms, RSS demona ≤ 1,5 GB.

## 19. Źródła

Dane repozytoriów i modeli odczytane przez API GitHub i Hugging Face 07.10.2026.

**Repozytoria i dokumentacja**

- [kyutai-labs/pocket-tts](https://github.com/kyutai-labs/pocket-tts) — README, sekcja „Running on GPU”, modele społeczności; [PR #315](https://github.com/kyutai-labs/pocket-tts/pull/315), [issue #196](https://github.com/kyutai-labs/pocket-tts/issues/196)
- [shefowl/pocket-tts-polish-6l](https://huggingface.co/shefowl/pocket-tts-polish-6l) — karta modelu (ewaluacja, szybkość, licencja)
- [OHF-Voice/piper1-gpl](https://github.com/OHF-Voice/piper1-gpl) — [API\_PYTHON.md](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md), [API\_HTTP.md](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_HTTP.md), [issue #267](https://github.com/OHF-Voice/piper1-gpl/issues/267)
- [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) — voices.json i MODEL\_CARD polskich głosów
- [csukuangfj/vits-piper-pl\_PL-zenski\_wg\_glos-medium](https://huggingface.co/csukuangfj/vits-piper-pl_PL-zenski_wg_glos-medium), [sherpa-onnx #2402](https://github.com/k2-fsa/sherpa-onnx/issues/2402) — głosy WG Głos
- [supertone-inc/supertonic](https://github.com/supertone-inc/supertonic) — README, tabela WER, wykres „CPU vs GPU Runtime Footprint”; [supertone-oss-archive/supertonic-3](https://huggingface.co/supertone-oss-archive/supertonic-3) — pliki i licencja OpenRAIL-M
- [k2-fsa/sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx), [lista polskich modeli TTS](https://k2-fsa.github.io/sherpa/onnx/tts/all/Polish/index.html), [PR #3750](https://github.com/k2-fsa/sherpa-onnx/pull/3750)
- [RHVoice/RHVoice](https://github.com/RHVoice/RHVoice), [PR #1044 „Polish 1.21”](https://github.com/RHVoice/RHVoice/pull/1044); paczki Arch: [alicja](https://archlinux.org/packages/extra-testing/x86_64/rhvoice-voice-alicja/), [magda](https://archlinux.org/packages/extra-testing/x86_64/rhvoice-voice-magda/), [natan](https://archlinux.org/packages/extra/x86_64/rhvoice-voice-natan/); [Debian copyright](https://metadata.ftp-master.debian.org/changelogs/non-free/r/rhvoice/testing_copyright); [F-Droid](https://f-droid.org/pl/packages/com.github.olga_yakovleva.rhvoice.android)
- [idiap/coqui-ai-TTS](https://github.com/idiap/coqui-ai-TTS), [coqui/XTTS-v2](https://huggingface.co/coqui/XTTS-v2)
- [resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox) — README; zgłoszenia [#286](https://github.com/resemble-ai/chatterbox/issues/286), [#311](https://github.com/resemble-ai/chatterbox/issues/311), [#256](https://github.com/resemble-ai/chatterbox/issues/256), [#472](https://github.com/resemble-ai/chatterbox/issues/472), [#533](https://github.com/resemble-ai/chatterbox/issues/533)
- [OpenBMB/VoxCPM](https://github.com/OpenBMB/VoxCPM) — README; [issue #254 (ONNX CPU)](https://github.com/OpenBMB/VoxCPM/issues/254)
- [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice)
- [edwko/OuteTTS](https://github.com/edwko/OuteTTS), [OuteAI/OuteTTS-1.0-0.6B](https://huggingface.co/OuteAI/OuteTTS-1.0-0.6B)
- [facebook/mms-tts-pol](https://huggingface.co/facebook/mms-tts-pol)
- README odrzuconych: [QwenLM/Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS), [neuphonic/neutts-air](https://github.com/neuphonic/neutts-air), [fishaudio/fish-speech](https://github.com/fishaudio/fish-speech), [hexgrad/kokoro](https://github.com/hexgrad/kokoro)

**Raporty społeczności i pomiary zewnętrzne**

- [coqui-ai/TTS dyskusja #3695 — XTTS speed](https://github.com/coqui-ai/TTS/discussions/3695)
- [idiap/coqui-ai-TTS dyskusja #507 — XTTS na CPU](https://github.com/idiap/coqui-ai-TTS/discussions/507)
- [Contra Collective — Kokoro vs Piper vs XTTS v2 (M5 Max)](https://contracollective.com/blog/kokoro-vs-piper-vs-xtts-local-text-to-speech-m5-max-2026)
- [arXiv 2512.08006 — fonemizacja dla TTS w czasie rzeczywistym (RTF Pipera)](https://arxiv.org/pdf/2512.08006)
- [mer.vin — Supertonic 3, 1200+ znaków/s](https://mer.vin/medium/supertonic-3-99m-on-device-tts-with-onnx-31-languages-and-1200-chars-sec-medium/)
