from allocator import Request, allocate


def test_fair_share_proportionality():
    # Фиксирует пропорциональное деление дефицита; при изменении клиенты
    # получат товар неравномерно (кто-то 100%, кто-то 0%)
    requests = [
        Request("R1", "DC_A", 1, demand_qty=100, min_lot=0, rounding_value=10),
        Request("R2", "DC_B", 1, demand_qty=50, min_lot=0, rounding_value=10),
    ]
    actual = allocate(60, requests)
    assert actual == {"R1": 40, "R2": 20}


def test_min_lot_starvation_bypass():
    # Фиксирует отсечение заявки при нехватке остатка до min_lot;
    # при изменении начнутся несуществующие отгрузки
    requests = [
        Request("R1", "DC_A", 1, demand_qty=100, min_lot=50, rounding_value=10),
        Request("R2", "DC_B", 1, demand_qty=100, min_lot=10, rounding_value=10),
    ]
    actual = allocate(40, requests)
    assert actual == {"R1": 0, "R2": 40}


def test_strict_down_rounding_no_over_allocation():
    # Фиксирует запрет на превышение спроса; при изменении начнутся
    # систематические перепоставки, затоваривающие склады получателей
    requests = [
        Request("R1", "DC_A", 1, demand_qty=48, min_lot=0, rounding_value=15),
    ]
    actual = allocate(1000, requests)
    assert actual == {"R1": 45}  # Строго 45, а не 60


def test_deterministic_tie_breaking():
    # Фиксирует разрешение ничьих по алфавиту (request_id);
    # при изменении расчет будет выдавать разные значения
    requests = [
        Request("R2", "DC_B", 1, demand_qty=40, min_lot=0, rounding_value=10),
        Request("R1", "DC_A", 1, demand_qty=40, min_lot=0, rounding_value=10),
    ]
    actual = allocate(10, requests)
    # Сток всего 10, доли равны. Товар должен уйти к R1 (т.к. "R1" < "R2")
    assert actual == {"R2": 0, "R1": 10}
