"""Utilitas EAN-13: digit cek, validasi, dan pola batang.

Barcode di MedDrop adalah EAN-13 DUMMY berawalan 2. Awalan 20-29 dicadangkan
GS1 untuk penggunaan internal (restricted circulation), jadi tidak akan bentrok
dengan GTIN produk asli (produk Indonesia umumnya berawalan 899).
"""

# Pola 7 modul per digit (1 = batang hitam). Lihat spesifikasi GS1 EAN-13.
L_CODES = ("0001101", "0011001", "0010011", "0111101", "0100011",
           "0110001", "0101111", "0111011", "0110111", "0001011")
G_CODES = ("0100111", "0110011", "0011011", "0100001", "0011101",
           "0111001", "0000101", "0010001", "0001001", "0010111")
R_CODES = ("1110010", "1100110", "1101100", "1000010", "1011100",
           "1001110", "1010000", "1000100", "1001000", "1110100")
# Digit pertama tidak digambar sebagai batang; ia menentukan pola L/G enam digit kiri.
LEFT_PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
               "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")
DUMMY_PREFIX = "2"


def check_digit(first12: str) -> str:
    """Digit cek untuk 12 digit pertama."""
    if len(first12) != 12 or not first12.isdigit():
        raise ValueError(f"Butuh 12 digit, bukan {first12!r}")
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(first12))
    return str((10 - total % 10) % 10)


def is_valid(code: str) -> bool:
    """True bila `code` berisi 13 digit dengan digit cek yang benar."""
    return (isinstance(code, str) and len(code) == 13 and code.isdigit()
            and check_digit(code[:12]) == code[12])


def is_dummy(code: str) -> bool:
    """True bila `code` EAN-13 valid berawalan 2 (kode internal, bukan GTIN asli)."""
    return is_valid(code) and code.startswith(DUMMY_PREFIX)


def bar_pattern(code: str) -> str:
    """Pola 95 modul ('1' = batang) untuk EAN-13 yang valid."""
    if not is_valid(code):
        raise ValueError(f"Bukan EAN-13 valid: {code!r}")
    parity = LEFT_PARITY[int(code[0])]
    left = "".join((L_CODES if p == "L" else G_CODES)[int(d)] for p, d in zip(parity, code[1:7]))
    right = "".join(R_CODES[int(d)] for d in code[7:])
    return "101" + left + "01010" + right + "101"
