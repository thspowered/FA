# Nástroj Stego

Python nástroj na steganografiu v BMP pomocou LSB podľa zadania.

Hlavička uložená na začiatku obrázka (LSB modrej z prvých 579 pixelov):
- typ: 1 bit (0 = text, 1 = súbor)
- metóda: 2 bity (0 = všetky pixely, 1 = párne, 2 = nepárne, 3 = okrajové pixely)
- názov súboru: 64 bajtov (UTF‑8, doplnené NUL)
- pozícia prvého bitu s informáciou: 32 bitov
- pozícia posledného bitu s informáciou: 32 bitov

Použitie:

1) Vytvor virtuálne prostredie a nainštaluj závislosti:
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

2) Spustenie CLI:
```
python -m stego.cli hide-text input.bmp output.bmp "tajny text" --method 0
python -m stego.cli hide-file input.bmp output.bmp secret.pdf --method 3
python -m stego.cli extract output.bmp --out recovered.txt
```

Poznámky:
- Funguje s BMP; iné formáty môžu byť automaticky skonvertované na RGB.
- Kapacita závisí od veľkosti obrázka a zvolenej metódy. Nástroj to pred zápisom kontroluje.