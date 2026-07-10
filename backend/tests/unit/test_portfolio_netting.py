"""OrderRepository.net_position 純函式單元測試（持倉淨額金額邏輯）。

取代原前端 computePositions 的客戶端測試——淨額已移到後端權威路徑，這裡以純函式嚴謹涵蓋
加碼加權均價、部分平倉 realized_pnl、全平、翻倉、回補等情境。
"""

from __future__ import annotations

from decimal import Decimal

from app.repos.order_repo import net_position

D = Decimal


def test_open_from_flat_weighted_is_price() -> None:
    # 從無部位 (old_qty=0) 加倉 → 均價即成交價
    qty, avg, realized, closed = net_position(
        old_qty=0, old_avg=D("0"), old_realized=D("0"), delta=1000, price=D("100")
    )
    assert (qty, avg, realized, closed) == (1000, D("100.000000"), D("0"), False)


def test_same_direction_weighted_average() -> None:
    # 多 1000@100 再買 500@110 → 1500 股、加權均價 103.333333、realized 不變
    qty, avg, realized, closed = net_position(
        old_qty=1000, old_avg=D("100"), old_realized=D("0"), delta=500, price=D("110")
    )
    assert qty == 1500
    assert avg == D("103.333333")
    assert realized == D("0")
    assert closed is False


def test_partial_close_long_realizes_pnl_keeps_avg() -> None:
    # 多 1000@100 賣 500@120 → 剩 500、均價維持 100、realized=500*(120-100)=10000
    qty, avg, realized, closed = net_position(
        old_qty=1000, old_avg=D("100"), old_realized=D("0"), delta=-500, price=D("120")
    )
    assert qty == 500
    assert avg == D("100")
    assert realized == D("10000.000000")
    assert closed is False


def test_full_close_long_sets_closed() -> None:
    qty, _avg, realized, closed = net_position(
        old_qty=1000, old_avg=D("100"), old_realized=D("0"), delta=-1000, price=D("120")
    )
    assert qty == 0
    assert realized == D("20000.000000")
    assert closed is True


def test_flip_long_to_short_uses_new_price_as_avg() -> None:
    # 多 1000@100 賣 1500@120 → 平掉 1000(realized=20000)、翻成 -500 空單、均價=120
    qty, avg, realized, closed = net_position(
        old_qty=1000, old_avg=D("100"), old_realized=D("0"), delta=-1500, price=D("120")
    )
    assert qty == -500
    assert avg == D("120")
    assert realized == D("20000.000000")
    assert closed is False


def test_partial_cover_short_realizes_pnl() -> None:
    # 空 -1000@100 買回 500@90 → 剩 -500、均價維持 100、realized=500*(100-90)=5000
    qty, avg, realized, closed = net_position(
        old_qty=-1000, old_avg=D("100"), old_realized=D("0"), delta=500, price=D("90")
    )
    assert qty == -500
    assert avg == D("100")
    assert realized == D("5000.000000")
    assert closed is False


def test_realized_pnl_accumulates() -> None:
    # 既有 realized 之上再累加
    qty, _avg, realized, closed = net_position(
        old_qty=1000,
        old_avg=D("100"),
        old_realized=D("3000"),
        delta=-1000,
        price=D("110"),
    )
    assert qty == 0
    assert realized == D("13000.000000")  # 3000 + 1000*(110-100)
    assert closed is True
