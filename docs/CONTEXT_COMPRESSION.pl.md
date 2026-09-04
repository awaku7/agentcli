# Kompresja kontekstu i ograniczony kontekst modelu

uag wykorzystuje kilka warstw, aby utrzymać aktywny kontekst modelu w określonych granicach. Celem jest ograniczenie zbędnych tokenów wejściowych bez usuwania plików, wyników narzędzi lub danych sesji, które mogą być nadal potrzebne użytkownikowi.

Niniejszy dokument opisuje aktualną implementację. Wyróżnia również zachowanie deterministyczne od zachowania specyficznego dla dostawcy lub wspomaganego przez LLM.

## 1. Dynamiczna powierzchnia narzędzi

Nie każda definicja narzędzia musi być wysyłana do modelu w każdej rundzie.

- `tool_catalog` przeszukuje dostępne możliwości.
- `tool_load` włącza tylko narzędzia wymagane do bieżącego zadania.
- `tool_catalog`, `tool_load` i `unload_tool` pozostają dostępne jako narzędzia do zarządzania.
- Przepływy Responses API zgodne z GPT-5.4 mogą korzystać z natywnego Tool Search po stronie serwera.
- Starszy tryb Tool Search zawęża specyfikacje narzędzi za pomocą `tool_catalog` po stronie klienta.

Zmniejsza to liczbę tokenów wejściowych wykorzystywanych przez schematy narzędzi, zwłaszcza w instalacjach z dużą liczbą narzędzi.

## 2. Duże tekstowe wyniki narzędzi stają się artefaktami

Gdy tekstowy wynik narzędzia przekracza próg Artifact, uag przechowuje kompletny wynik jako Artifact i wysyła do modelu ograniczone odniesienie oraz podgląd zamiast pełnego tekstu.

Domyślne limity to:

```text
UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS=100000
UAGENT_TOOL_RESULT_MAX_CHARS=12000
```

Reprezentacja widoczna dla modelu zawiera nazwę narzędzia, pierwotną długość, odwołanie `artifact://`, ścieżkę przechowywania oraz ograniczony podgląd. Pełny wynik pozostaje dostępny za pośrednictwem magazynu Artifact.

Próg można zmienić za pomocą `UAGENT_TOOL_RESULT_ARTIFACT_THRESHOLD_CHARS`. Wartość `0` wyłącza promowanie Artifact. `UAGENT_TOOL_RESULT_MAX_CHARS` kontroluje standardową politykę ograniczonych wyników; `0` wyłącza ten standardowy limit.

## 3. Pobieranie ograniczonego pliku `Artifact`

Narzędzie infrastruktury `artifact_read` pobiera tylko żądaną część pliku `Artifact`:

- `start_line` wybiera pierwszy wiersz.
- `max_lines` jest ograniczone do 500.
- `max_chars` jest ograniczone do 50 000 znaków.
- Można używać zarówno identyfikatora Artifact, jak i URI `artifact://`.

Umożliwia to sprawdzenie niewielkiego, istotnego zakresu zamiast ponownego wprowadzania całego pliku lub wyniku polecenia do kolejnej iteracji modelu.

Nowe artefakty są przechowywane poniżej:

```text
~/.uag/artifacts/
```

Istniejące starsze ścieżki Artifact pozostają czytelne ze względu na kompatybilność.

## 4. Izolacja ładunku binarnego

Dane binarne zawarte w tekście nie są wysyłane jako tekstowy wynik narzędzia do kolejnej iteracji modelu. Pola o kształcie Base64 są zastępowane krótkim znacznikiem, takim jak:

```text
[dane binarne pominięte z kontekstu LLM]
```

Interfejs użytkownika i klienci zdalni nadal mogą odbierać załączniki przechowywane w pamięci, a zapisane pliki pozostają dostępne poprzez ich ścieżki lub odwołania Artifact. Zapobiega to nadmiernemu rozrostowi tekstowego kontekstu modelu przez obrazy, pliki audio, zrzuty ekranu i inne dane binarne.

Ta sama klasa danych binarnych jest oczyszczana przed zapisaniem w SQLite i JSONL, co zapobiega ich ponownemu pojawieniu się jako dużych danych po ponownym załadowaniu sesji.

## 5. Automatyczna kompresja historii

uag może kompresować starszą historię rozmów, gdy liczba wiadomości lub szacowana liczba tokenów osiągnie skonfigurowany limit.

Zasady kompresji uwzględniają:

- liczbę wiadomości niesystemowych;
- rozstrzygnięte okno kontekstowe modelu, jeśli jest dostępne;
- `UAGENT_SHRINK_KEEP_LAST` (domyślnie 20);
- `UAGENT_SHRINK_MAX_TOKENS` lub nadpisanie specyficzne dla modelu;
- `UAGENT_SHRINK_CNT`; oraz
- `UAGENT_SHRINK_RATIO` (domyślnie 0,5, gdy okno kontekstowe jest znane).

Limit specyficzny dla modelu można podać w następujący sposób:

```text
UAGENT_SHRINK_MAX_TOKENS_<MODEL_NAME>
```

Poprzednie podsumowanie nie jest generowane na nowo przy każdej turze. Histereza wymaga zgromadzenia wystarczającej ilości nowych danych historycznych lub kolejnego przepełnienia budżetu tokenów, zanim kompresja zostanie uruchomiona ponownie.

## 6. Podsumowania historii wspomagane przez LLM

Gdy automatyczna kompresja wykorzystuje LLM, starsze komunikaty użytkownika, asystenta i narzędzi są podsumowywane w postaci kroczącego komunikatu systemowego, podczas gdy najnowsza część historii jest zachowywana.

Długie historie mogą być podsumowywane w fragmentach. Odpowiednie opcje to:

```text
UAGENT_SHRINK_CHUNK_SIZE=100
UAGENT_SHRINK_SINGLE_SHOT=1
```

Podsumowanie jest przesuwane do przodu, zamiast tworzyć nieograniczoną sekwencję komunikatów podsumowujących. Jest to operacja wspomagana przez LLM i może wymagać dodatkowych żądań do dostawcy.

## 7. Deterministyczna kompresja awaryjna

Jeśli podsumowanie LLM jest niedostępne, uag może zachować początkowe komunikaty systemowe oraz tylko najnowsze komunikaty. Granice wywołań narzędzi są naprawiane tak, aby wynikowa historia nie zaczynała się ani nie kończyła osieroconym wywołaniem narzędzia.

Moduł ładujący i moduł oczyszczający usuwają również wpisy nieistotne dla modelu lub nieprawidłowe, w tym komunikaty dotyczące wyłącznie interfejsu użytkownika, wewnętrzne komunikaty kontrolne, uszkodzone wiersze dziennika, nieobsługiwane role, osierocone wyniki narzędzi oraz niekompletne bloki wywołań narzędzi.

Po ponownym załadowaniu sesji przywracany jest bieżący monit systemowy, a zachowywane są wyłącznie istotne wstrzyknięte komunikaty systemowe, takie jak kontekst umiejętności lub haka.

## 8. Odzyskiwanie po przepełnieniu kontekstu

Jeśli dostawca zgłasza przekroczenie okna kontekstowego, uag identyfikuje dużą, niedawną wiadomość z historii i cofa tę wiadomość oraz następującą po niej historię przed ponowną próbą. Jest to reaktywne rozwiązanie awaryjne, a nie zamiennik normalnego zarządzania zasobami.

## 9. Kontynuacja i kompakcja po stronie dostawcy

Tam, gdzie jest to obsługiwane, Responses API wykorzystuje `previous_response_id` do kontynuowania łańcucha odpowiedzi bez ponownego wysyłania z klienta całej historii odpowiedzi zarządzanej przez dostawcę.

Przepływy Responses API wysyłają również konfigurację kompresji po stronie dostawcy, wykorzystując ten sam lokalny próg kompresji. Dokładne zachowanie zależy od dostawcy; lokalne Artifact i zasady dotyczące historii pozostają zabezpieczeniami niezależnymi od dostawcy.

## 10. Efektywność zliczania tokenów

Liczby tokenów wykorzystywane do podejmowania decyzji dotyczących kompresji są buforowane i aktualizowane przyrostowo, gdy dodawane są wyłącznie nowe komunikaty. Nie zmniejsza to bezpośrednio kontekstu modelu, ale zmniejsza obciążenie procesora i opóźnienie związane z podejmowaniem decyzji o konieczności kompresji.

## Co nie stanowi jeszcze w pełni ujednoliconej warstwy

Obecna implementacja nie zapewnia jeszcze wszystkich poniższych elementów w ramach jednego menedżera niezależnego od dostawcy:

- ujednolicone `ContextManager` i `ContextBudget`;
- `ToolResultRecord` z metadanymi dotyczącymi ważności i usuwania;
- podsumowania semantyczne, które nie wymagają `LLM`;
- automatyczne pobieranie i ponowne wstrzykiwanie odpowiednich artefaktów;
- centralny menedżer wyników gwarantujący konwersję `Artifact` dla każdego narzędzia generującego pliki binarne; lub
- usuwanie z uwzględnieniem priorytetów we wszystkich kategoriach: systemowej, historycznej, schematu narzędzia oraz wyników.

Krótko mówiąc, uag łączy obecnie deterministyczne skracanie, odniesienia do Artifact, izolację plików binarnych, dynamiczny wybór narzędzi, streszczenia historii, kontynuację dostawcy oraz odzyskiwanie po przepełnieniu. Plan projektowy dotyczący ujednoliconej warstwy kontekstowej został udokumentowany w [UAG_CONTEXT_MANAGEMENT_DESIGN.md](UAG_CONTEXT_MANAGEMENT_DESIGN.md).
