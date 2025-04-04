from datetime import datetime, date, timedelta

# Opening the content in the global.env file in a dictionary format
def read_env_file(file_path: str) -> dict:
    env_vars = {}
    with open(file_path, 'r') as file:
        for line in file:
            if '=' in line:
                key, value = line.strip().split('=', 1)
                env_vars[key] = value
    return env_vars

START_DATE = datetime.strptime(read_env_file('global.env').get('START_DATE', '2025-04-07'), '%Y-%m-%d').date()
END_DATE = datetime.strptime(read_env_file('global.env').get('END_DATE', '2026-12-31'), '%Y-%m-%d').date()

def get_all_saving_weeks(start_date: date = START_DATE, end_date: date = END_DATE) -> list[date]:
    start = start_date
    end = end_date 
    current = start
    weeks = []
    while current <= end:
        weeks.append(current)
        current += timedelta(days=7)
    return weeks

def compute_streaks(deposits: list[dict], saving_weeks: list[date]) -> int:
    weeks_with_deposits = set(d["date"] for d in deposits if d["amount"] > 0)

    streak = max_streak = 0
    for week in saving_weeks:
        iso = week.isoformat()
        if iso in weeks_with_deposits:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak
