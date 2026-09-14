from gqmrmed.db.models import CreditPack
from gqmrmed.services.credits import CREDIT_PACK_CATALOG


def test_credit_pack_catalog_has_exact_launch_prices() -> None:
    assert CREDIT_PACK_CATALOG == (
        ("DESIGN_5", 5, 50),
        ("DESIGN_12", 12, 100),
        ("DESIGN_20", 20, 150),
    )
    assert CreditPack.__tablename__ == "credit_packs"
    assert all(credits > 0 and stars > 0 for _, credits, stars in CREDIT_PACK_CATALOG)
