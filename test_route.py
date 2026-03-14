import json
from main import create_data_model, solve_routing_problem
from pydantic import BaseModel

class DummyHouse:
    def __init__(self, address, date, start_time, end_time):
        self.address = address
        self.date = date
        self.start_time = start_time
        self.end_time = end_time

houses = [
    DummyHouse("456 King St W, Toronto, ON", "2026-03-14", "13:00", "15:00"), # day 1
    DummyHouse("123 Main St, Toronto, ON", "2026-03-15", "14:00", "16:00"), # day 2
]

# Test 1: Multi-day preference (false)
print("=== Test 1: Multi-day allowed ===")
try:
    data1 = create_data_model(houses, "CN Tower, Toronto, ON", "2026-03-14", "2026-03-15", False)
    res1 = solve_routing_problem(data1)
    if res1:
        print(f"Total time: {res1.total_minutes}")
        for step in res1.route:
            print(f"  {step.address} arriving at {step.arrival_time}")
    else:
        print("No route found!")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Single-day preference (true) - Should fail or route impossible
print("\n=== Test 2: Single-day preference (true) -> Should fail because dates are different ===")
try:
    data2 = create_data_model(houses, "CN Tower, Toronto, ON", "2026-03-14", "2026-03-15", True)
    res2 = solve_routing_problem(data2)
    if res2:
        print(f"Total time: {res2.total_minutes}")
        for step in res2.route:
            print(f"  {step.address} arriving at {step.arrival_time}")
    else:
        print("No route found! (Expected)")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Single-day preference (true) with same dates
print("\n=== Test 3: Single-day preference (true) -> Same dates, should succeed ===")
houses_same_day = [
    DummyHouse("456 King St W, Toronto, ON", "2026-03-14", "13:00", "15:00"),
    DummyHouse("123 Main St, Toronto, ON", "2026-03-14", "14:00", "16:00"),
]
try:
    data3 = create_data_model(houses_same_day, "CN Tower, Toronto, ON", "2026-03-14", "2026-03-15", True)
    res3 = solve_routing_problem(data3)
    if res3:
        print(f"Total time: {res3.total_minutes}")
        for step in res3.route:
            print(f"  {step.address} arriving at {step.arrival_time}")
    else:
        print("No route found!")
except Exception as e:
    print(f"Error: {e}")
