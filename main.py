import csv
import logging
import sys
from collections import defaultdict

from allocator import Request, allocate

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class CSVDataLoader:
    def __init__(self, supply_path: str, requests_path: str) -> None:
        self.supply_path = supply_path
        self.requests_path = requests_path

    def read_supply(self) -> dict[str, int]:
        supply: dict[str, int] = defaultdict(int)
        try:
            with open(self.supply_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        case_id = row["case_id"]
                        qty = int(row["available_qty"])

                        if qty < 0:
                            logger.warning(
                                f"Row {row_idx}: Negative qty {qty}. Clamped to 0."
                            )
                            qty = 0

                        if case_id in supply:
                            logger.warning(
                                f"Row {row_idx}: Multiple supply rows for "
                                f"{case_id}. Aggregating."
                            )

                        # Суммирование доступного стока внутри одного кейса
                        supply[case_id] += qty
                    except (ValueError, KeyError) as e:
                        logger.error(f"Malformed supply data at row {row_idx}: {e}")
        except FileNotFoundError:
            logger.critical(f"File not found: {self.supply_path}")
            sys.exit(1)

        return dict(supply)

    def read_requests(self) -> dict[str, list[Request]]:
        cases: dict[str, list[Request]] = defaultdict(list)
        try:
            with open(self.requests_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row_idx, row in enumerate(reader, start=2):
                    try:
                        req_id = row["request_id"]
                        demand = int(row["demand_qty"])
                        min_lot = int(row["min_lot"])
                        rv = int(row["rounding_value"])

                        req = Request(
                            request_id=req_id,
                            dest_location=row["dest_location"],
                            priority=int(row["priority"]),
                            demand_qty=demand,
                            min_lot=min_lot,
                            rounding_value=rv,
                        )
                        cases[row["case_id"]].append(req)
                    except (ValueError, KeyError) as e:
                        logger.error(
                            f"Malformed request data at row {row_idx}: {e}. Skipping."
                        )
        except FileNotFoundError:
            logger.critical(f"File not found: {self.requests_path}")
            sys.exit(1)

        return dict(cases)


class SNPRunner:
    def __init__(self, loader: CSVDataLoader) -> None:
        self.loader = loader

    def run(self) -> None:
        supply_data = self.loader.read_supply()
        requests_data = self.loader.read_requests()

        all_case_ids = sorted(set(supply_data.keys()).union(requests_data.keys()))

        for case_id in all_case_ids:
            available_qty = supply_data.get(case_id, 0)
            reqs = requests_data.get(case_id, [])

            if case_id not in supply_data:
                logger.warning(f"Case {case_id} has requests but NO supply. Assumed 0.")
            if not reqs:
                logger.info(f"Case {case_id} has supply but NO requests. Skipping.")
                continue

            try:
                allocations = allocate(available_qty, reqs)
            except ValueError as e:
                logger.error(f"Failed to allocate {case_id}: {e}")
                continue

            allocated_total = sum(allocations.values())
            print(f"\n--- {case_id} ---")
            print(
                f"Available: {available_qty} | Allocated: {allocated_total} | "
                f"Leftover: {available_qty - allocated_total}"
            )

            for r in sorted(reqs, key=lambda x: x.priority):
                print(
                    f"[{r.priority}] {r.request_id} (Need: {r.demand_qty}, "
                    f"Min: {r.min_lot}, Step: {r.rounding_value}) -> "
                    f"Got: {allocations[r.request_id]}"
                )


def main() -> None:
    loader = CSVDataLoader("data/supply.csv", "data/requests.csv")
    runner = SNPRunner(loader)
    runner.run()


if __name__ == "__main__":
    main()
