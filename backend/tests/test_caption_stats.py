from app.services.caption_stats import caption_names, fold_name


def test_caption_names_keep_scorer_and_assist() -> None:
    assert caption_names("1-0  Gol: Erbil · Asist: Ümit") == ("Erbil", "Ümit")
    assert caption_names("6-4  Gol: Talha") == ("Talha", None)
    assert caption_names("7-7  Gol: Mustafa Gökalp (4) · Asist: Bülent (4)") == (
        "Mustafa Gökalp",
        "Bülent",
    )
    assert caption_names("6-5  Gol: Cetin · Asist: Bülent (3)") == ("Cetin", "Bülent")


def test_cedilla_folds_onto_the_lineup_spelling() -> None:
    assert fold_name("Cetin") == fold_name("Çetin")
    assert fold_name("Fatih Olgun") != fold_name("Fatih Ö.")
    assert fold_name("Mustafa Gökalp") != fold_name("Mustafa C.")
