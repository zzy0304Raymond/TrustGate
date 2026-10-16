"""Conservative per-worker reservation; allocations sum to the overall study budget."""
import math

class BudgetExceeded(RuntimeError):
    pass

class Budget:
    def __init__(self, limit, reservation=0.05):
        if not math.isfinite(limit) or not math.isfinite(reservation) or min(limit, reservation) <= 0:
            raise ValueError('Budget and per-request reservation must be finite positive numbers.')
        self.limit, self.reservation = limit, reservation
        self.reported = self.uncertain = self.pending = 0.0
        self.halted = False

    def reserve(self):
        if self.pending or self.halted or self.reported+self.uncertain+self.reservation > self.limit+1e-12:
            raise BudgetExceeded('Insufficient remaining allocation, unresolved request, or halted budget.')
        self.pending = self.reservation

    def reconcile(self, cost):
        if not isinstance(cost, (float, int)) or isinstance(cost, bool) or not math.isfinite(cost) or cost < 0:
            self.unknown()
            raise BudgetExceeded('Missing/invalid usage.cost: retain reservation and stop.')
        if not self.pending:
            raise RuntimeError('Request had no budget reservation.')
        reserved = self.pending
        self.reported += cost
        self.pending = 0.0
        if cost > reserved:
            self.halted = True
            raise BudgetExceeded('Reported request cost exceeded its reservation; stop and review pricing.')

    def unknown(self):
        self.uncertain += self.pending
        self.pending = 0.0
        self.halted = True

    def snapshot(self):
        return dict(limit_usd=self.limit, per_request_reservation_usd=self.reservation,
                    reported_cost_usd=self.reported, uncertain_reserved_usd=self.uncertain,
                    pending_reserved_usd=self.pending, halted=self.halted)
