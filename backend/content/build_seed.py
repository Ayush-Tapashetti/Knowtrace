"""Author the school-maths seed curriculum: `python content/build_seed.py` writes content/seed/*.json.

Concepts, prerequisites and lesson text are written by hand below. Practice questions come from small
parametric generators with fixed seeds, so every answer key is computed (never typed) and every wrong
choice is a classic mistake. Re-running produces byte-identical files, so the curriculum hash is stable.
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).parent / "seed"
Gen = Callable[[random.Random], tuple[str, str, list[str]]]


def fr(n: int, d: int) -> str:
    return f"{n}/{d}"


def ff(x: Fraction) -> str:
    return str(x.numerator) if x.denominator == 1 else fr(x.numerator, x.denominator)


def num(x: float) -> str:
    return f"{x:g}"


# ---- generators: (stem, correct, three wrong choices) --------------------------------------------
def g_counting(r: random.Random):
    n = r.randint(12, 89)
    return f"What number comes right after {n}?", str(n + 1), [str(n - 1), str(n + 2), str(n + 10)]


def g_place(r: random.Random):
    n = r.randint(1000, 9999)
    d = str(n)[1]
    return (
        f"In {n}, what is the value of the digit {d}?",
        str(int(d) * 100),
        [d, str(int(d) * 10), str(int(d) * 1000)],
    )


def g_add(r: random.Random):
    a, b = r.randint(120, 899), r.randint(120, 899)
    return f"{a} + {b} = ?", str(a + b), [str(a + b - 10), str(a + b + 100), str(a + b - 100)]


def g_sub(r: random.Random):
    a, b = r.randint(500, 999), r.randint(120, 480)
    return f"{a} − {b} = ?", str(a - b), [str(a + b), str(a - b + 10), str(a - b - 100)]


def g_mult_facts(r: random.Random):
    a, b = r.randint(6, 12), r.randint(6, 12)
    return f"{a} × {b} = ?", str(a * b), [str(a * b + a), str(a * b - b), str(a + b)]


def g_div_facts(r: random.Random):
    a, b = r.randint(6, 12), r.randint(4, 12)
    return f"{a * b} ÷ {b} = ?", str(a), [str(a + 1), str(a * b - b), str(b)]


def g_multi_mult(r: random.Random):
    a, b = r.randint(21, 49), r.randint(12, 29)
    return (
        f"{a} × {b} = ?",
        str(a * b),
        [str(a * b - 10 * a), str(a * b + 100), str(a * (b % 10) + a * (b // 10))],
    )


def g_long_div(r: random.Random):
    q, b = r.randint(12, 48), r.randint(3, 9)
    return f"{q * b} ÷ {b} = ?", str(q), [str(q + 10), str(q - 1), str(q * b // 10)]


def g_factors(r: random.Random):
    n = r.choice([12, 18, 20, 24, 30, 36])
    wrong_n = n + 1
    return f"Which number is a factor of {n}?", str(n // 2), [str(wrong_n), str(n * 2), str(n + 5)]


def g_primes(r: random.Random):
    p = r.choice([11, 13, 17, 19, 23, 29])
    comp = r.choice([21, 27, 33, 39, 51])
    return "Which of these numbers is prime?", str(p), [str(comp), str(comp + 6), str(p * 3)]


def g_order(r: random.Random):
    a, b, c = r.randint(2, 9), r.randint(2, 9), r.randint(2, 9)
    ans = a + b * c
    return f"{a} + {b} × {c} = ?", str(ans), [str((a + b) * c), str(a * b + c), str(ans + b)]


def g_neg(r: random.Random):
    a, b = r.randint(-9, -2), r.randint(-9, -2)
    while a == b:
        b = r.randint(-9, -2)
    big = max(a, b)
    return f"Which is greater: {a} or {b}?", str(big), [str(min(a, b)), "They are equal", "Cannot tell"]


def g_int_ops(r: random.Random):
    a, b = r.randint(2, 9), r.randint(2, 9)
    return f"(−{a}) × (−{b}) = ?", str(a * b), [str(-a * b), str(a - b), str(-(a + b))]


def g_frac_meaning(r: random.Random):
    d = r.randint(4, 9)
    n = r.randint(1, d - 1)
    return (
        f"A pizza is cut into {d} equal slices and you eat {n}. What fraction did you eat?",
        fr(n, d),
        [fr(d, n), fr(n, d + n), fr(d - n, d + 1)],
    )


def g_equiv(r: random.Random):
    n, d, k = r.randint(1, 4), r.randint(5, 9), r.randint(2, 5)
    return (
        f"Which fraction equals {fr(n, d)}?",
        fr(n * k, d * k),
        [fr(n + k, d + k), fr(n * k, d), fr(n, d * k)],
    )


def g_compare(r: random.Random):
    d1, d2 = r.choice([(3, 4), (2, 3), (4, 5), (5, 8), (3, 5)])
    a, b = Fraction(1, d1), Fraction(1, d2)
    big = max(a, b)
    return f"Which is larger: 1/{d1} or 1/{d2}?", ff(big), [ff(min(a, b)), "They are equal", fr(d1, d2)]


def g_add_like(r: random.Random):
    d = r.randint(5, 12)
    a, b = r.randint(1, 3), r.randint(1, 3)
    return f"{fr(a, d)} + {fr(b, d)} = ?", fr(a + b, d), [fr(a + b, 2 * d), fr(a * b, d), fr(a + b, d - 1)]


def g_add_unlike(r: random.Random):
    a, b = r.choice([(2, 3), (3, 4), (4, 5), (3, 5), (5, 6)])
    s = Fraction(1, a) + Fraction(1, b)
    return f"1/{a} + 1/{b} = ?", ff(s), [fr(2, a + b), fr(1, a + b), fr(1, a * b)]


def g_mixed(r: random.Random):
    d, w = r.randint(3, 6), r.randint(1, 4)
    n = r.randint(1, d - 1)
    return (
        f"Write {w} and {fr(n, d)} as an improper fraction.",
        fr(w * d + n, d),
        [fr(w + n, d), fr(w * n, d), fr(w * d, d + n)],
    )


def g_mult_frac(r: random.Random):
    a, b = r.choice([(2, 3), (3, 4), (2, 5), (3, 5)]), r.choice([(1, 2), (3, 4), (2, 7), (1, 3)])
    p = Fraction(*a) * Fraction(*b)
    return (
        f"{fr(*a)} × {fr(*b)} = ?",
        ff(p),
        [fr(a[0] + b[0], a[1] + b[1]), ff(Fraction(*a) + Fraction(*b)), fr(a[0] * b[1], a[1] * b[0])],
    )


def g_div_frac(r: random.Random):
    a, b = r.choice([(1, 2), (3, 4), (2, 3)]), r.choice([(1, 4), (1, 3), (2, 5)])
    q = Fraction(*a) / Fraction(*b)
    return (
        f"{fr(*a)} ÷ {fr(*b)} = ?",
        ff(q),
        [ff(Fraction(*a) * Fraction(*b)), ff(Fraction(*b) / Fraction(*a)), fr(a[0] * b[1], a[1] + b[0])],
    )


def g_dec_place(r: random.Random):
    n = r.randint(11, 98) / 100
    t = round(n * 100) // 10
    return (
        f"In {n:.2f}, what does the first digit after the point stand for?",
        f"{t} tenths",
        [f"{t} hundredths", f"{t} ones", f"{t} thousandths"],
    )


def g_dec_ops(r: random.Random):
    a, b = r.randint(11, 59) / 10, r.randint(11, 59) / 10
    return (
        f"{a} + {b} = ?",
        num(round(a + b, 1)),
        [num(round(a + b + 1, 1)), num(round(a * b, 2)), num(round(a + b - 0.9, 1))],
    )


def g_frac_dec(r: random.Random):
    n, d = r.choice([(1, 4), (3, 4), (1, 5), (2, 5), (3, 8), (1, 8)])
    return f"Write {fr(n, d)} as a decimal.", num(n / d), [num(n / d * 10), num(d / n), num(n + d / 10)]


def g_pct_meaning(r: random.Random):
    p = r.choice([5, 20, 25, 40, 75])
    return f"{p}% is the same as which fraction?", ff(Fraction(p, 100)), [fr(p, 10), fr(100, p), fr(1, p)]


def g_pct_of(r: random.Random):
    p, n = r.choice([10, 20, 25, 50]), r.choice([40, 60, 80, 120, 200])
    ans = n * p // 100
    return f"What is {p}% of {n}?", str(ans), [str(n - ans), str(n + ans), str(p * n // 10)]


def g_ratio(r: random.Random):
    a, b = r.randint(2, 7), r.randint(2, 7)
    while a == b:
        b = r.randint(2, 7)
    return (
        f"A class has {a} boys for every {b} girls. What is the ratio of boys to girls?",
        f"{a}:{b}",
        [f"{b}:{a}", f"{a}:{a + b}", f"{a + b}:{b}"],
    )


def g_unit_rate(r: random.Random):
    p, n = r.randint(3, 9), r.randint(3, 9)
    return (
        f"{n} notebooks cost {n * p} rupees. How much does one notebook cost?",
        str(p),
        [str(n), str(n * p - n), str(p + n)],
    )


def g_proportion(r: random.Random):
    a, k = r.randint(2, 6), r.randint(2, 5)
    return (
        f"If {a} pens cost {a * 5} rupees, how much do {a * k} pens cost?",
        str(a * k * 5),
        [str(a * 5 + k), str(a * k + 5), str(a * 5 * 2)],
    )


def g_pct_change(r: random.Random):
    old, p = r.choice([50, 80, 200, 400]), r.choice([10, 20, 25])
    new = old + old * p // 100
    return (
        f"A price rises from {old} to {new}. By what percent did it rise?",
        f"{p}%",
        [f"{new - old}%", f"{p * 2}%", f"{p // 2 or 1}%"],
    )


def g_variables(r: random.Random):
    k = r.randint(3, 9)
    return (
        f"A pencil costs {k} rupees. Which expression gives the cost of n pencils?",
        f"{k}n",
        [f"{k}+n", f"n/{k}", f"n−{k}"],
    )


def g_evaluate(r: random.Random):
    a, b, x = r.randint(2, 6), r.randint(1, 9), r.randint(2, 6)
    return (
        f"Evaluate {a}x + {b} when x = {x}.",
        str(a * x + b),
        [str(a + x + b), str(a * (x + b)), str(a * x * b)],
    )


def g_like_terms(r: random.Random):
    a, b, c = r.randint(2, 8), r.randint(2, 8), r.randint(2, 8)
    return (
        f"Simplify {a}x + {b}y + {c}x.",
        f"{a + c}x + {b}y",
        [f"{a + b + c}xy", f"{a + c}x + {b}", f"{a * c}x + {b}y"],
    )


def g_one_step(r: random.Random):
    x, a = r.randint(3, 15), r.randint(2, 9)
    return f"Solve x + {a} = {x + a}.", str(x), [str(x + 2 * a), str(a), str(x - a)]


def g_two_step(r: random.Random):
    x, a, b = r.randint(2, 9), r.randint(2, 6), r.randint(1, 9)
    return (
        f"Solve {a}x + {b} = {a * x + b}.",
        str(x),
        [str(a * x), str((a * x + b) // a if (a * x + b) % a == 0 else x + 1), str(x + b)],
    )


def g_plane(r: random.Random):
    x, y = r.randint(2, 8), r.randint(2, 8)
    while x == y:
        y = r.randint(2, 8)
    return (
        f"On a coordinate plane, where is the point {x} right and {y} up?",
        f"({x}, {y})",
        [f"({y}, {x})", f"({x}, −{y})", f"(−{x}, {y})"],
    )


def g_slope(r: random.Random):
    m, x1, y1 = r.randint(2, 5), r.randint(0, 3), r.randint(0, 3)
    dx = r.randint(1, 3)
    return (
        f"A line passes through ({x1}, {y1}) and ({x1 + dx}, {y1 + m * dx}). What is its slope?",
        str(m),
        [str(m * dx), str(dx), f"1/{m}"],
    )


def g_slope_int(r: random.Random):
    m, b = r.randint(2, 6), r.randint(1, 9)
    return (
        f"In y = {m}x + {b}, where does the line cross the y-axis?",
        f"y = {b}",
        [f"y = {m}", f"x = {b}", f"y = {m + b}"],
    )


def g_perimeter(r: random.Random):
    a, b = r.randint(3, 15), r.randint(3, 15)
    return (
        f"A rectangle is {a} cm by {b} cm. What is its perimeter?",
        f"{2 * (a + b)} cm",
        [f"{a * b} cm", f"{a + b} cm", f"{2 * a + b} cm"],
    )


def g_area_rect(r: random.Random):
    a, b = r.randint(3, 15), r.randint(3, 15)
    return (
        f"A rectangle is {a} cm by {b} cm. What is its area?",
        f"{a * b} cm²",
        [f"{2 * (a + b)} cm²", f"{a + b} cm²", f"{a * b * 2} cm²"],
    )


def g_area_tri(r: random.Random):
    b, h = 2 * r.randint(2, 9), r.randint(3, 11)
    return (
        f"A triangle has base {b} cm and height {h} cm. What is its area?",
        f"{b * h // 2} cm²",
        [f"{b * h} cm²", f"{b + h} cm²", f"{b * h // 4} cm²"],
    )


def g_angles(r: random.Random):
    a, b = r.randint(30, 80), r.randint(30, 80)
    return (
        f"Two angles of a triangle are {a}° and {b}°. What is the third?",
        f"{180 - a - b}°",
        [f"{360 - a - b}°", f"{90 - a}°", f"{a + b}°"],
    )


def g_exponents(r: random.Random):
    b, e = r.randint(2, 5), r.randint(2, 4)
    return f"{b}^{e} = ?", str(b**e), [str(b * e), str(b ** (e - 1)), str(e**b)]


def g_pyth(r: random.Random):
    a, b, c = r.choice([(3, 4, 5), (6, 8, 10), (5, 12, 13), (8, 15, 17)])
    return (
        f"A right triangle has legs {a} and {b}. How long is the hypotenuse?",
        str(c),
        [str(a + b), str(c * c), str(b - a)],
    )


def g_mean(r: random.Random):
    xs = [r.randint(2, 12) for _ in range(4)]
    xs[-1] += (4 - sum(xs) % 4) % 4
    m = sum(xs) // 4
    return f"What is the mean of {', '.join(map(str, xs))}?", str(m), [str(sum(xs)), str(max(xs)), str(m + 1)]


def g_median(r: random.Random):
    xs = sorted(r.sample(range(2, 30), 5))
    med = xs[2]
    shown = xs[:]
    r.shuffle(shown)
    return (
        f"What is the median of {', '.join(map(str, shown))}?",
        str(med),
        [str(shown[2]), str(sum(xs) // 5 + 1), str(xs[-1])],
    )


def g_prob(r: random.Random):
    red, blue = r.randint(2, 6), r.randint(2, 6)
    return (
        f"A bag has {red} red and {blue} blue marbles. What is the chance of picking red?",
        fr(red, red + blue),
        [fr(red, blue), fr(1, red + blue), fr(blue, red + blue)],
    )


# ---- concepts: id, name, strand, prerequisites, generator, definition, worked example ----------------
C: list[tuple[str, str, str, list[str], Gen, str, str]] = [
    (
        "counting",
        "Counting and ordering",
        "number",
        [],
        g_counting,
        "Counting names how many there are, and each number is one more than the one before it.",
        "After 47 comes 48, because 47 + 1 = 48.",
    ),
    (
        "place_value",
        "Place value",
        "number",
        ["counting"],
        g_place,
        "A digit's value depends on its place: ones, tens, hundreds, thousands.",
        "In 4,352 the 3 is in the hundreds place, so it is worth 300.",
    ),
    (
        "add_whole",
        "Adding whole numbers",
        "number",
        ["counting"],
        g_add,
        "Adding combines amounts; line up the places and carry when a column passes 9.",
        "256 + 178: 6 + 8 = 14 (write 4, carry 1); 5 + 7 + 1 = 13 (write 3, carry 1); 2 + 1 + 1 = 4. The sum is 434.",
    ),
    (
        "sub_whole",
        "Subtracting whole numbers",
        "number",
        ["add_whole"],
        g_sub,
        "Subtracting finds what is left or the difference; borrow from the next place when needed.",
        "52 − 27: borrow to make 12 − 7 = 5, then 4 − 2 = 2. The answer is 25.",
    ),
    (
        "mult_facts",
        "Multiplication facts",
        "number",
        ["add_whole"],
        g_mult_facts,
        "Multiplication is repeated addition: 6 × 7 means seven sixes added together.",
        "6 × 7 = 6 + 6 + 6 + 6 + 6 + 6 + 6 = 42.",
    ),
    (
        "div_facts",
        "Division facts",
        "number",
        ["mult_facts", "sub_whole"],
        g_div_facts,
        "Division splits into equal groups and undoes multiplication: if 6 × 7 = 42 then 42 ÷ 7 = 6.",
        "56 ÷ 8: ask what times 8 gives 56. It is 7, so 56 ÷ 8 = 7.",
    ),
    (
        "multi_digit_mult",
        "Multi-digit multiplication",
        "number",
        ["mult_facts", "place_value"],
        g_multi_mult,
        "Break a number by place value, multiply each part, then add the partial products.",
        "34 × 12 = 34 × 10 + 34 × 2 = 340 + 68 = 408.",
    ),
    (
        "long_division",
        "Long division",
        "number",
        ["div_facts", "multi_digit_mult"],
        g_long_div,
        "Divide one place at a time from the left, multiply back, subtract, and bring down the next digit.",
        "96 ÷ 4: 9 ÷ 4 = 2 (8), remainder 1; bring down 6 to make 16; 16 ÷ 4 = 4. The answer is 24.",
    ),
    (
        "factors",
        "Factors and multiples",
        "number",
        ["mult_facts", "div_facts"],
        g_factors,
        "A factor divides a number exactly; a multiple is what you get by multiplying it.",
        "The factors of 12 are 1, 2, 3, 4, 6 and 12, because each divides 12 with no remainder.",
    ),
    (
        "primes",
        "Prime numbers",
        "number",
        ["factors"],
        g_primes,
        "A prime has exactly two factors, 1 and itself.",
        "13 has only 1 and 13 as factors, so it is prime. 15 is divisible by 3, so it is not.",
    ),
    (
        "order_ops",
        "Order of operations",
        "number",
        ["add_whole", "sub_whole", "mult_facts"],
        g_order,
        "Brackets first, then multiplication and division, then addition and subtraction.",
        "3 + 4 × 2: multiply first (4 × 2 = 8), then add: 3 + 8 = 11.",
    ),
    (
        "negatives",
        "Negative numbers",
        "number",
        ["sub_whole"],
        g_neg,
        "Negative numbers sit below zero on the number line; the further left, the smaller.",
        "−7 is less than −2 because it is further to the left on the number line.",
    ),
    (
        "int_ops",
        "Integer operations",
        "number",
        ["negatives", "mult_facts"],
        g_int_ops,
        "Same signs multiply to a positive; different signs multiply to a negative.",
        "(−4) × (−3): both negative, so the answer is positive: 12.",
    ),
    (
        "exponents",
        "Exponents",
        "number",
        ["mult_facts"],
        g_exponents,
        "An exponent says how many times to multiply the base by itself.",
        "2^4 = 2 × 2 × 2 × 2 = 16.",
    ),
    (
        "frac_meaning",
        "What a fraction means",
        "fractions",
        ["div_facts"],
        g_frac_meaning,
        "A fraction a/b means a of b equal parts of a whole.",
        "A bar cut into 5 equal parts with 2 shaded shows 2/5.",
    ),
    (
        "equiv_frac",
        "Equivalent fractions",
        "fractions",
        ["frac_meaning", "factors"],
        g_equiv,
        "Multiply or divide top and bottom by the same number and the fraction keeps its value.",
        "2/3 = (2×4)/(3×4) = 8/12.",
    ),
    (
        "compare_frac",
        "Comparing fractions",
        "fractions",
        ["equiv_frac"],
        g_compare,
        "With the same top, the fraction with the smaller bottom is bigger because its parts are larger.",
        "1/3 is bigger than 1/5: thirds are larger pieces than fifths.",
    ),
    (
        "add_like_frac",
        "Adding fractions with the same denominator",
        "fractions",
        ["frac_meaning", "add_whole"],
        g_add_like,
        "Same-sized parts add by adding the tops and keeping the bottom.",
        "2/7 + 3/7 = 5/7. The sevenths stay sevenths.",
    ),
    (
        "add_unlike_frac",
        "Adding fractions with different denominators",
        "fractions",
        ["add_like_frac", "equiv_frac"],
        g_add_unlike,
        "First rewrite both fractions with a common denominator, then add the tops.",
        "1/2 + 1/3 = 3/6 + 2/6 = 5/6.",
    ),
    (
        "mixed_numbers",
        "Mixed numbers and improper fractions",
        "fractions",
        ["frac_meaning", "mult_facts"],
        g_mixed,
        "A mixed number is a whole plus a fraction; multiply the whole by the bottom and add the top to make an improper fraction.",
        "2 1/3 = (2×3 + 1)/3 = 7/3.",
    ),
    (
        "mult_frac",
        "Multiplying fractions",
        "fractions",
        ["frac_meaning", "mult_facts"],
        g_mult_frac,
        "Multiply the tops together and the bottoms together, then simplify.",
        "2/3 × 3/4 = 6/12 = 1/2.",
    ),
    (
        "div_frac",
        "Dividing fractions",
        "fractions",
        ["mult_frac"],
        g_div_frac,
        "Dividing by a fraction means multiplying by its reciprocal (flip it).",
        "1/2 ÷ 1/4 = 1/2 × 4/1 = 4/2 = 2.",
    ),
    (
        "dec_place",
        "Decimal place value",
        "decimals",
        ["place_value", "frac_meaning"],
        g_dec_place,
        "Places after the point are tenths, hundredths, thousandths, each ten times smaller.",
        "In 0.47 the 4 is 4 tenths and the 7 is 7 hundredths.",
    ),
    (
        "dec_ops",
        "Adding and multiplying decimals",
        "decimals",
        ["dec_place", "multi_digit_mult"],
        g_dec_ops,
        "Line up the decimal points to add; to multiply, ignore the points then place the point by counting decimal places.",
        "2.5 + 1.75: line up as 2.50 + 1.75 = 4.25.",
    ),
    (
        "frac_to_dec",
        "Fractions as decimals",
        "decimals",
        ["dec_place", "long_division"],
        g_frac_dec,
        "A fraction is a division: divide the top by the bottom to get the decimal.",
        "3/4 = 3 ÷ 4 = 0.75.",
    ),
    (
        "percent_meaning",
        "What a percent means",
        "percent",
        ["frac_to_dec"],
        g_pct_meaning,
        "Percent means out of 100, so 45% is 45/100 or 0.45.",
        "25% = 25/100 = 1/4.",
    ),
    (
        "percent_of",
        "Finding a percent of a number",
        "percent",
        ["percent_meaning", "dec_ops"],
        g_pct_of,
        "Turn the percent into a decimal or fraction and multiply.",
        "20% of 60 = 0.20 × 60 = 12.",
    ),
    (
        "percent_change",
        "Percent change",
        "percent",
        ["percent_of", "sub_whole"],
        g_pct_change,
        "Percent change is the change divided by the original value, times 100.",
        "A rise from 50 to 60 is 10 ÷ 50 = 0.2, which is 20%.",
    ),
    (
        "ratio_meaning",
        "Ratios",
        "ratio",
        ["frac_meaning"],
        g_ratio,
        "A ratio compares two quantities in a fixed order, written a:b.",
        "3 red to 5 blue is the ratio 3:5, which is not the same as 5:3.",
    ),
    (
        "unit_rate",
        "Unit rates",
        "ratio",
        ["ratio_meaning", "long_division"],
        g_unit_rate,
        "A unit rate is the amount for one unit; divide the total by the number of units.",
        "12 apples for 60 rupees: 60 ÷ 12 = 5 rupees each.",
    ),
    (
        "proportion",
        "Proportions",
        "ratio",
        ["unit_rate", "equiv_frac"],
        g_proportion,
        "Two ratios are in proportion when they are equivalent; scale both parts by the same factor.",
        "If 3 pens cost 15 rupees then 9 pens cost 45 rupees, because 9 is 3 × 3.",
    ),
    (
        "variables",
        "Variables and expressions",
        "algebra",
        ["order_ops"],
        g_variables,
        "A letter stands for an unknown or changing number; 5n means 5 times n.",
        "If n pencils cost 4 rupees each the cost is 4n rupees.",
    ),
    (
        "evaluate_expr",
        "Evaluating expressions",
        "algebra",
        ["variables", "int_ops"],
        g_evaluate,
        "Substitute the value for the letter, then follow the order of operations.",
        "3x + 2 when x = 4: 3 × 4 + 2 = 14.",
    ),
    (
        "like_terms",
        "Combining like terms",
        "algebra",
        ["variables", "int_ops"],
        g_like_terms,
        "Only terms with the same letter part can be added: 3x + 2x = 5x, but 3x + 2y stays as it is.",
        "4x + 3y + 2x = 6x + 3y.",
    ),
    (
        "one_step_eq",
        "One-step equations",
        "algebra",
        ["variables", "int_ops"],
        g_one_step,
        "Do the same operation to both sides to get the letter alone.",
        "x + 5 = 12: subtract 5 from both sides, so x = 7.",
    ),
    (
        "two_step_eq",
        "Two-step equations",
        "algebra",
        ["one_step_eq"],
        g_two_step,
        "Undo the adding or subtracting first, then undo the multiplying or dividing.",
        "2x + 3 = 11: subtract 3 to get 2x = 8, then divide by 2 so x = 4.",
    ),
    (
        "coord_plane",
        "The coordinate plane",
        "algebra",
        ["negatives"],
        g_plane,
        "A point (x, y) is x across and y up from the origin; x always comes first.",
        "(3, 5) is 3 to the right and 5 up.",
    ),
    (
        "slope",
        "Slope",
        "algebra",
        ["coord_plane", "unit_rate"],
        g_slope,
        "Slope is rise over run: how far up for each step across.",
        "From (1, 2) to (3, 8): rise 6, run 2, slope 3.",
    ),
    (
        "linear_eq",
        "Lines: y = mx + b",
        "algebra",
        ["slope", "two_step_eq"],
        g_slope_int,
        "In y = mx + b, m is the slope and b is where the line crosses the y-axis.",
        "y = 2x + 3 has slope 2 and crosses the y-axis at 3.",
    ),
    (
        "perimeter",
        "Perimeter",
        "geometry",
        ["add_whole"],
        g_perimeter,
        "Perimeter is the distance around a shape: add all the side lengths.",
        "A 4 cm by 6 cm rectangle has perimeter 4 + 6 + 4 + 6 = 20 cm.",
    ),
    (
        "area_rect",
        "Area of rectangles",
        "geometry",
        ["mult_facts", "perimeter"],
        g_area_rect,
        "Area is the space inside a shape; for a rectangle multiply length by width.",
        "A 4 cm by 6 cm rectangle has area 24 cm².",
    ),
    (
        "area_tri",
        "Area of triangles",
        "geometry",
        ["area_rect", "div_facts"],
        g_area_tri,
        "A triangle is half of a rectangle with the same base and height: area = base × height ÷ 2.",
        "Base 8, height 5: 8 × 5 ÷ 2 = 20 cm².",
    ),
    (
        "angles",
        "Angles in a triangle",
        "geometry",
        ["add_whole", "sub_whole"],
        g_angles,
        "The three angles of any triangle add up to 180°.",
        "If two angles are 50° and 60° the third is 180 − 110 = 70°.",
    ),
    (
        "pythagoras",
        "Pythagoras' theorem",
        "geometry",
        ["exponents", "area_rect", "angles"],
        g_pyth,
        "In a right triangle, a² + b² = c² where c is the longest side.",
        "Legs 3 and 4: 9 + 16 = 25, so the hypotenuse is 5.",
    ),
    (
        "mean",
        "Mean",
        "data",
        ["add_whole", "div_facts"],
        g_mean,
        "The mean is the total divided by how many values there are.",
        "Mean of 2, 4, 9: total 15 ÷ 3 = 5.",
    ),
    (
        "median",
        "Median",
        "data",
        ["place_value", "mean"],
        g_median,
        "The median is the middle value once the numbers are in order.",
        "Sorted 3, 7, 9, 12, 20: the middle value, 9, is the median.",
    ),
    (
        "probability",
        "Basic probability",
        "data",
        ["frac_meaning"],
        g_prob,
        "Probability is favourable outcomes over all equally likely outcomes.",
        "2 red among 5 marbles gives a chance of 2/5 of picking red.",
    ),
]
# Items 4 of these also need a prerequisite concept (noisy-AND in the Q-matrix).
MULTI = {
    "add_unlike_frac": "equiv_frac",
    "percent_of": "dec_ops",
    "two_step_eq": "one_step_eq",
    "area_tri": "div_facts",
    "proportion": "unit_rate",
    "linear_eq": "slope",
    "median": "place_value",
    "pythagoras": "exponents",
    "slope": "unit_rate",
}


def make_item(cid: str, gen: Gen, k: int) -> tuple[str, str, list[str]]:
    for attempt in range(50):
        rng = random.Random(f"{cid}:{k}:{attempt}")
        stem, ok, wrong = gen(rng)
        if len(set(wrong)) == 3 and ok not in wrong:
            return stem, ok, wrong
    raise ValueError(f"cannot build item {cid}.{k}")


def main() -> None:
    ids = [c[0] for c in C]
    assert len(set(ids)) == len(ids)
    parents = {c[0]: c[3] for c in C}
    depth: dict[str, int] = {}

    def d(cid: str) -> int:
        if cid not in depth:
            depth[cid] = 1 + max((d(p) for p in parents[cid]), default=0)
        return depth[cid]

    dependents: dict[str, list[str]] = {i: [] for i in ids}
    for cid, ps in parents.items():
        for p in ps:
            dependents[p].append(cid)
    name = {c[0]: c[1] for c in C}

    concepts, edges, items, links, atoms = [], [], [], [], []
    for cid, nm, strand, ps, gen, defn, ex in C:
        t = d(cid)
        concepts.append(
            {
                "id": cid,
                "name": nm,
                "description": defn,
                "strand": strand,
                "tier": t,
                "p_init": round(max(0.2, 0.55 - 0.05 * t), 2),
                "p_learn": 0.18 if t <= 3 else 0.15,
                "p_slip": 0.10,
                "p_guess": 0.25,
                "p_forget": 0.02,
                "half_life_days": 21.0,
            }
        )
        edges += [{"concept_id": cid, "prereq_id": p} for p in ps]
        for k in range(1, 5):
            stem, ok, wrong = make_item(cid, gen, k)
            choices = wrong[:]
            pos = random.Random(f"pos:{cid}:{k}").randint(0, 3)
            choices.insert(pos, ok)
            letters = "abcd"
            iid = f"i.{cid}.{k}"
            items.append(
                {
                    "id": iid,
                    "stem": stem,
                    "kind": "MCQ",
                    "answer": letters[pos],
                    "choices": [{"id": letters[j], "text": ch} for j, ch in enumerate(choices)],
                    "difficulty": [0.2, 0.35, 0.5, 0.65][k - 1],
                    "p_guess": 0.25,
                }
            )
            links.append({"item_id": iid, "concept_id": cid, "is_primary": True})
            if k == 4 and MULTI.get(cid):
                links.append({"item_id": iid, "concept_id": MULTI[cid], "is_primary": False})
        nxt = dependents[cid][0] if dependents[cid] else None
        bridge = (
            f"With {nm.lower()} secure, you are ready to go back to {name[nxt].lower()}."
            if nxt
            else f"With {nm.lower()} secure, go back to the question you missed."
        )
        base = {"concept_id": cid, "item_id": None}
        atoms += [
            {
                **base,
                "id": f"a.{cid}.def",
                "kind": "DEFINITION",
                "est_seconds": 40,
                "order_hint": 1,
                "body": defn,
            },
            {
                **base,
                "id": f"a.{cid}.ex",
                "kind": "WORKED_EXAMPLE",
                "est_seconds": 60,
                "order_hint": 1,
                "body": ex,
            },
            {
                **base,
                "id": f"a.{cid}.br",
                "kind": "BRIDGE",
                "est_seconds": 20,
                "order_hint": 1,
                "body": bridge,
            },
            {
                "id": f"a.{cid}.pr",
                "concept_id": cid,
                "kind": "PRACTICE",
                "est_seconds": 45,
                "order_hint": 1,
                "item_id": f"i.{cid}.1",
                "body": "",
            },
            {
                "id": f"a.{cid}.ck1",
                "concept_id": cid,
                "kind": "CHECK",
                "est_seconds": 30,
                "order_hint": 1,
                "item_id": f"i.{cid}.2",
                "body": "",
            },
            {
                "id": f"a.{cid}.ck2",
                "concept_id": cid,
                "kind": "CHECK",
                "est_seconds": 30,
                "order_hint": 2,
                "item_id": f"i.{cid}.3",
                "body": "",
            },
        ]
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, rows in [
        ("concepts", concepts),
        ("edges", edges),
        ("items", items),
        ("item_concepts", links),
        ("atoms", atoms),
    ]:
        (OUT / f"{fname}.json").write_text(
            json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(f"{len(concepts)} concepts, {len(edges)} edges, {len(items)} items, {len(atoms)} atoms")


if __name__ == "__main__":
    main()
