import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Request:
    request_id: str
    dest_location: str
    priority: int
    demand_qty: int
    min_lot: int
    rounding_value: int

    @property
    def step(self) -> int:
        """Отсутствие отрицательной отгрузки"""
        return self.rounding_value if self.rounding_value > 0 else 1

    @property
    def first_step(self) -> int:
        """Объем первой отгрузки с покрытием минимума и кратности."""
        if self.min_lot <= 0:
            return self.step
        multiplier = (self.min_lot + self.step - 1) // self.step
        return multiplier * self.step

    @property
    def max_valid_qty(self) -> int:
        """Максимальный объем без превышения спроса, округленный вниз."""
        if self.demand_qty <= 0:
            return 0
        return (self.demand_qty // self.step) * self.step


class SNPAllocator:
    def __init__(self, available_qty: int, requests: Iterable[Request]) -> None:
        self.available_qty = available_qty
        self.req_list: list[Request] = list(requests)
        self._validate_input()

    def _validate_input(self) -> None:
        """Валидация уникальности request_id и корректности параметров."""
        seen_ids: set[str] = set()
        for r in self.req_list:
            if r.request_id in seen_ids:
                raise ValueError(f"Duplicate request_id detected: {r.request_id}")
            seen_ids.add(r.request_id)

            if r.min_lot < 0 or r.rounding_value <= 0:
                logger.warning(
                    f"[{r.request_id}] Invalid constraints. Using fallbacks."
                )

    def allocate(self) -> dict[str, int]:
        """Распределение дефицита методом Two-Pass Apportionment."""
        result = {r.request_id: 0 for r in self.req_list}
        available = self.available_qty

        if available < 0:
            logger.warning(f"Negative stock {available} clamped to 0.")
            available = 0

        if available == 0 or not self.req_list:
            return result

        # Отсеивание заявок, по которым физически невозможно отгрузить товар
        valid_reqs = [
            r for r in self.req_list if r.max_valid_qty >= max(r.min_lot, r.step) > 0
        ]
        if not valid_reqs:
            return result

        # Сортировка приоритетов (исправлены C401 и C414 для ruff)
        priorities = sorted({r.priority for r in valid_reqs})

        for p in priorities:
            if available <= 0:
                break

            level_reqs = sorted(
                [r for r in valid_reqs if r.priority == p],
                key=lambda x: x.request_id,
            )
            total_level_demand = sum(r.max_valid_qty for r in level_reqs)

            # Закрытие потребности полностью, если стока хватает на всех
            if total_level_demand <= available:
                for r in level_reqs:
                    result[r.request_id] = r.max_valid_qty
                    available -= r.max_valid_qty
                continue

            # Расчет коэффициента пропорционального распределения
            fair_ratio = available / total_level_demand

            # Проход 1: Раздача базовых долей
            shortfalls: list[list[Any]] = []
            for r in level_reqs:
                theoretical_share = r.max_valid_qty * fair_ratio
                allocated_steps = int(theoretical_share) // r.step
                base_alloc = allocated_steps * r.step

                # Отмена расчета отгрузки, если не покрывает минимальное требование
                if base_alloc < r.min_lot:
                    base_alloc = 0

                result[r.request_id] = base_alloc
                available -= base_alloc

                # Остаток недополученного объема от округления
                if base_alloc < r.max_valid_qty:
                    error = theoretical_share - base_alloc
                    shortfalls.append([error, r.request_id, r])

            # Проход 2: Раздача остатков склада
            progress = True
            while available > 0 and progress:
                progress = False
                shortfalls.sort(key=lambda x: (-x[0], x[1]))

                for item in shortfalls:
                    if available <= 0:
                        break

                    error, req_id, r = item
                    current_alloc = result[req_id]
                    next_step = r.first_step if current_alloc == 0 else r.step

                    if (
                        available >= next_step
                        and current_alloc + next_step <= r.max_valid_qty
                    ):
                        result[req_id] += next_step
                        available -= next_step
                        item[0] -= next_step
                        progress = True

        return result


def allocate(available_qty: int, requests: Iterable[Request]) -> dict[str, int]:
    return SNPAllocator(available_qty, requests).allocate()
