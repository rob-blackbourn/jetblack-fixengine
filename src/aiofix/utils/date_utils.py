from datetime import time


def is_dow_in_range(start_dow: int, end_dow: int, target_dow: int) -> bool:
    if start_dow <= end_dow:
        return start_dow <= target_dow and target_dow <= end_dow
    else:
        return start_dow <= target_dow or target_dow <= end_dow


def is_time_in_range(start_time: time, end_time: time, target_time: time) -> bool:
    if start_time <= end_time:
        return start_time <= target_time and target_time <= end_time
    else:
        return start_time <= target_time or target_time <= end_time
