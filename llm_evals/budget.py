"""Local runner budget, not a provider-level key cap. No API calls in this module.

The default ledger lives in git's common directory and is shared by worktrees.
Request-start dates use America/Los_Angeles. Unresolved reservations also count
against every subsequent day, until trusted usage settles them. Never delete or
replace a ledger to clear charges; reconciliation requires independent evidence.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import tempfile
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

LA = ZoneInfo('America/Los_Angeles')


class BudgetError(RuntimeError):
    pass


def default_path():
    common = subprocess.check_output(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                                     cwd=Path(__file__).resolve().parent, text=True).strip()
    return Path(common) / 'llm-evals-budget' / 'ledger.json'


def ceiling_microusd(value):
    try:
        decimal = Decimal(str(value))
        scaled = decimal * 1_000_000
        if not decimal.is_finite() or decimal <= 0 or scaled != scaled.to_integral_value():
            raise ValueError
        return int(scaled)
    except (ValueError, InvalidOperation, TypeError):
        raise BudgetError('Daily limit must be a positive dollar amount with at most six decimals') from None


class Budget:
    def __init__(self, path, daily_limit, now=None):
        self.path = Path(path)
        self.ceiling = ceiling_microusd(daily_limit)
        self.now = now or (lambda: datetime.now(timezone.utc))

    def day(self):
        current = self.now()
        if current.tzinfo is None:
            raise BudgetError('Budget clock must have a timezone')
        return current.astimezone(LA).date().isoformat()

    @contextmanager
    def locked(self):
        if not self.path.parent.is_dir():
            raise BudgetError('Budget not initialized; paid call blocked')
        with open(self.path.with_suffix('.lock'), 'a') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _save(self, state):
        fd, tmp = tempfile.mkstemp(prefix='.ledger-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(state, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.locked():
            if self.path.exists() or self.path.with_suffix('.initialized').exists():
                raise BudgetError('Ledger already exists; initialization never resets spending')
            with self.path.with_suffix('.initialized').open('x') as marker:
                marker.write('llm-evals-budget-v1\n')
                marker.flush()
                os.fsync(marker.fileno())
            self._save(dict(version=1, timezone='America/Los_Angeles',
                            ceiling_microusd=self.ceiling, blocked=False, entries={}))

    def _load(self):
        try:
            if self.path.with_suffix('.initialized').read_text() != 'llm-evals-budget-v1\n':
                raise ValueError('Missing initialization marker')
            state = json.loads(self.path.read_text())
            if not (set(state) == {'version', 'timezone', 'ceiling_microusd', 'blocked', 'entries'}):
                raise ValueError("Invalid ledger state")
            if not (state['version'] == 1 and state['timezone'] == 'America/Los_Angeles'):
                raise ValueError("Invalid ledger state")
            if not (type(state['ceiling_microusd']) is int and state['ceiling_microusd'] == self.ceiling):
                raise ValueError("Invalid ledger state")
            if not (type(state['blocked']) is bool and type(state['entries']) is dict):
                raise ValueError("Invalid ledger state")
            for key, entry in state['entries'].items():
                if not (str(uuid.UUID(key)) == key):
                    raise ValueError("Invalid ledger state")
                if not (set(entry) == {'day', 'reserved', 'actual', 'model', 'input_bound', 'output_bound'}):
                    raise ValueError("Invalid ledger state")
                if not (date.fromisoformat(entry['day']).isoformat() == entry['day']):
                    raise ValueError("Invalid ledger state")
                if not (entry['day'] <= self.day()):
                    raise ValueError("Invalid ledger state")
                if not (isinstance(entry['model'], str) and entry['model']):
                    raise ValueError("Invalid ledger state")
                for field in ('reserved', 'input_bound', 'output_bound'):
                    if not (type(entry[field]) is int and entry[field] > 0):
                        raise ValueError("Invalid ledger state")
                if not (entry['actual'] is None or (type(entry['actual']) is int and entry['actual'] >= 0)):
                    raise ValueError("Invalid ledger state")
                if entry['actual'] is not None and entry['actual'] > entry['reserved']:
                    if not (state['blocked']):
                        raise ValueError("Invalid ledger state")
            return state
        except (OSError, ValueError, TypeError, KeyError, AssertionError):
            raise BudgetError('Missing/corrupt ledger, changed ceiling, or unexpected accounting state; paid call blocked') from None

    def change_ceiling(self, new_daily_limit):
        """Replace the daily ceiling in place. Every entry is kept; spending is never reset.
        The caller must state the current ceiling (self.ceiling) for the change to apply."""
        new = ceiling_microusd(new_daily_limit)
        with self.locked():
            state = self._load()
            if state['blocked']:
                raise BudgetError('Ledger blocked by an accounting anomaly; ceiling unchanged')
            state['ceiling_microusd'] = new
            self._save(state)
        self.ceiling = new

    def check(self):
        with self.locked():
            state = self._load()
            if state['blocked']:
                raise BudgetError('Ledger blocked by an accounting anomaly')
            return state

    def used(self, state):
        return sum(e['reserved'] if e['actual'] is None else e['actual']
                   for e in state['entries'].values()
                   if e['day'] == self.day() or e['actual'] is None)

    def reserve(self, amount, model, input_bound, output_bound):
        if any(type(v) is not int or v <= 0 for v in (amount, input_bound, output_bound)):
            raise BudgetError('Invalid reservation')
        with self.locked():
            state = self._load()
            if state['blocked'] or self.used(state) + amount > self.ceiling:
                raise BudgetError('Daily budget exhausted or blocked; no provider call made')
            rid = str(uuid.uuid4())
            state['entries'][rid] = dict(day=self.day(), reserved=amount, actual=None,
                                         model=model, input_bound=input_bound, output_bound=output_bound)
            self._save(state)
            return rid

    def settle(self, rid, actual, input_tokens, output_tokens):
        if any(type(v) is not int or v < 0 for v in (actual, input_tokens, output_tokens)):
            raise BudgetError('Untrusted usage; reservation retained')
        with self.locked():
            state = self._load()
            entry = state['entries'].get(rid)
            if entry is None or entry['actual'] is not None:
                raise BudgetError('Unknown/already-settled reservation')
            anomaly = (actual > entry['reserved'] or input_tokens > entry['input_bound']
                       or output_tokens > entry['output_bound'])
            if anomaly:
                state['blocked'] = True
                # Never release the conservative hold on a mismatched response.
                entry['reserved'] = max(entry['reserved'], actual)
            else:
                entry['actual'] = actual
            self._save(state)
            if anomaly:
                raise BudgetError('Usage exceeded reservation bounds; ledger blocked')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'status', 'set-ceiling'])
    parser.add_argument('--daily-limit-usd', required=True, help='the CURRENT ceiling')
    parser.add_argument('--new-daily-limit-usd', help='set-ceiling only: the replacement ceiling')
    args = parser.parse_args()
    budget = Budget(default_path(), args.daily_limit_usd)
    try:
        if args.action == 'init':
            budget.initialize()
        elif args.action == 'set-ceiling':
            if not args.new_daily_limit_usd:
                raise BudgetError('set-ceiling needs --new-daily-limit-usd')
            budget.change_ceiling(args.new_daily_limit_usd)
        state = budget.check()
        print(f'Ledger: {budget.path}\nDaily ceiling: ${budget.ceiling/1_000_000:.6f}\n'
              f'Committed/reserved today: ${budget.used(state)/1_000_000:.6f}')
        return 0
    except BudgetError as exc:
        print(exc)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
