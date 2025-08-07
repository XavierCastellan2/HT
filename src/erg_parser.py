import csv

def parse_erg(file_path: str) -> list[tuple[int, int]]:
    """
    Parses an ERG file and returns a list of (time, power) tuples.

    Assumption: The ERG file is a simple text file where each line contains:
    time_offset_seconds,target_power_watts

    Lines starting with '#' are treated as comments and are ignored.
    """
    workout = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                try:
                    time_str, power_str = line.split(',')
                    time = int(time_str.strip())
                    power = int(power_str.strip())
                    workout.append((time, power))
                except ValueError:
                    print(f"Warning: Skipping invalid line in ERG file: {line}")
                    continue
    except FileNotFoundError:
        print(f"Error: ERG file not found at {file_path}")
        return []

    return workout
