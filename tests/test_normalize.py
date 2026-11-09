from fineval.normalize import gold_key, numbers_in, parse_number, strip_enum, text_key


def test_text_key_variants_collapse():
    a = text_key('1. "What is the NPV of $1,000 at 5%?"')
    b = text_key("what is the  NPV of 1000 at 5 % ?")
    c = text_key("What is the NPV of $1000.00 at 5%")
    assert a == c
    assert a.replace("%", "") == b.replace(" %", "").replace("%", "")


def test_text_key_keeps_meaningful_words():
    assert text_key("Due from Related Parties, Current") != text_key("Due to Related Parties, Current")
    assert text_key("Assets, Current") != text_key("Assets, Noncurrent")


def test_parse_number():
    assert parse_number("$1,577.00") == 1577.0
    assert parse_number("(12.5)") == -12.5
    assert parse_number("-3") == -3.0
    assert parse_number("41%") == 41.0
    assert parse_number(".5") == 0.5
    assert parse_number("12 apples") is None
    assert parse_number("(12") is None


def test_numbers_in_distinguishes_templates():
    assert numbers_in("$6,000 for 4 years at 8%") != numbers_in("$4,500 for 6 years at 7%")
    assert numbers_in("$6,000 for 4 years") == numbers_in("6000 for 4 years")


def test_strip_enum():
    assert strip_enum('12. "Compute the ratio."') == "Compute the ratio."


def test_gold_key_percent_equals_fraction():
    assert gold_key({"answer": "2.8%"}) == gold_key({"answer": "0.028"})
    assert gold_key({"answer": "$1577.00"}) == gold_key({"answer": "1577"})
    assert gold_key({"concepts": ["us-gaap:B", "us-gaap:A"]}) == gold_key({"concepts": ["us-gaap:a", "us-gaap:b"]})
