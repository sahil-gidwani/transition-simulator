from pipeline.naming import acronyms, normalize_club_name, tokens_prefix_match


def test_transliteration_before_ascii_fold() -> None:
    assert normalize_club_name("Bayern München") == "bayern muenchen"
    assert normalize_club_name("1. FC Köln") == "koeln"
    assert normalize_club_name("Łódź") == "lodz"
    assert normalize_club_name("Başakşehir") == "basaksehir"


def test_stop_tokens_and_digits_dropped() -> None:
    assert normalize_club_name("FC Barcelona") == "barcelona"
    assert normalize_club_name("Real Betis Balompié SAD") == "real betis"
    assert normalize_club_name("1899 Hoffenheim") == "hoffenheim"


def test_dotted_legal_suffix_survives_as_letter_tokens() -> None:
    # Punctuation splits "S.A.D." into single-letter tokens that are NOT stop
    # tokens - such legal-name artifacts are what the manual fix CSV is for.
    assert normalize_club_name("Real Betis Balompié S.A.D.") == "real betis s a d"


def test_distinguishing_tokens_survive() -> None:
    # "sporting" and "sg" are club names, not legal forms - they must not drop.
    assert normalize_club_name("Sporting CP") == "sporting"
    assert "sg" in normalize_club_name("Paris SG")


def test_all_stop_tokens_yield_empty_string() -> None:
    assert normalize_club_name("FC Club de Futbol") == ""


def test_acronyms_are_contiguous_runs() -> None:
    assert acronyms(["paris", "saint", "germain"]) == {"ps", "sg", "psg"}
    assert acronyms(["ajax"]) == set()
    assert acronyms([]) == set()


def test_prefix_match_requires_every_elo_token_to_hit() -> None:
    assert tokens_prefix_match(frozenset({"bayern"}), frozenset({"bayern", "muenchen"}))
    assert not tokens_prefix_match(frozenset({"bayern", "berlin"}), frozenset({"bayern"}))


def test_prefix_match_needs_three_char_prefixes() -> None:
    # "dor" is a >=3-char prefix of "dortmund"; "do" is too short.
    assert tokens_prefix_match(frozenset({"dor"}), frozenset({"dortmund"}))
    assert not tokens_prefix_match(frozenset({"do"}), frozenset({"dortmund"}))
    # symmetric: a short TM token may prefix a longer Elo token
    assert tokens_prefix_match(frozenset({"dortmund"}), frozenset({"dor"}))


def test_prefix_match_empty_elo_tokens_is_false() -> None:
    assert not tokens_prefix_match(frozenset(), frozenset({"anything"}))
