from yamale.validators import Validator

_phase_indexes = []
_task_indexes = []
_solution_indexes = []
_leaderboard_indexes = []


class PhaseIndex(Validator):
    tag = 'phase_index'

    def _is_valid(self, value):
        unique = value not in _phase_indexes
        _phase_indexes.append(value)
        return isinstance(value, int) and unique


class TaskIndex(Validator):
    tag = 'task_index'

    def _is_valid(self, value):
        unique = value not in _task_indexes
        _task_indexes.append(value)
        return isinstance(value, int) and unique


class SolutionIndex(Validator):
    tag = 'solution_index'

    def _is_valid(self, value):
        unique = value not in _solution_indexes
        _solution_indexes.append(value)
        return isinstance(value, int) and unique


class LeaderboardIndex(Validator):
    tag = 'leaderboard_index'

    def _is_valid(self, value):
        unique = value not in _solution_indexes
        _leaderboard_indexes.append(value)
        return isinstance(value, int) and unique


class ColumnIndex(Validator):
    tag = 'column_index'

    def _is_valid(self, value):
        unique = value not in _solution_indexes
        _solution_indexes.append(value)
        return isinstance(value, int) and unique
