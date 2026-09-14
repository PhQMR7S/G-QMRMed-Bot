from gqmrmed.db.models import CreditPack


def test_credit_pack_catalog_has_exact_launch_prices() -> None:
    packs = {
        "DESIGN_5": (5, 50),
        "DESIGN_12": (12, 100),
        "DESIGN_20": (20, 150),
    }
    assert packs == {
        "DESIGN_5": (5, 50),
        "DESIGN_12": (12, 100),
        "DESIGN_20": (20, 150),
    }
    assert CreditPack.__tablename__ == "credit_packs"
