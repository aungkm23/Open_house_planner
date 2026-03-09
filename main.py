from datetime import datetime
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from dotenv import load_dotenv

import geocoder

load_dotenv()

def get_current_minutes():
    """Gets the current time and converts it to minutes from midnight."""
    now = datetime.now()
    # E.g., 1:29 PM -> 13 * 60 + 29 = 809 minutes
    current_minutes = (now.hour * 60) + now.minute
    return current_minutes

def parse_time_string(time_str):
    """Converts a time string like '14:00' to minutes from midnight."""
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes

def create_data_model(user_inputs, current_location):
    """Stores the data for the open house routing problem based on user inputs."""
    data = {}
    current_time_mins = get_current_minutes()

    addresses = [current_location] + [item['address'] for item in user_inputs]

    # 1. Travel Time Matrix
    data['time_matrix'] = geocoder.get_distance_matrix(addresses)
    if not data['time_matrix']:
        raise ValueError("Could not get distance matrix. Please check your addresses or API key.")

    # 2. Open House Time Windows
    time_windows = [(current_time_mins, 1440)] # 0: Current Location (Available from NOW until end of day)

    for item in user_inputs:
        start_mins = parse_time_string(item['start_time'])
        end_mins = parse_time_string(item['end_time'])
        time_windows.append((start_mins, end_mins))

    data['time_windows'] = time_windows

    # 3. Service Time
    # Assuming 0 service time at current location, and 30 minutes at each house
    data['service_time'] = [0] + [30] * len(user_inputs)

    data['num_vehicles'] = 1
    data['depot'] = 0
    return data

def main():
    # Sample Mock Inputs. In a real application, these will be passed directly from the frontend/scraper
    user_inputs = [
        {"address": "756 Spadina Avenue, Toronto, ON", "start_time": "13:00", "end_time": "15:00"},
        {"address": "123 Main St, Toronto, ON", "start_time": "14:00", "end_time": "16:00"},
        {"address": "456 King St W, Toronto, ON", "start_time": "13:30", "end_time": "14:30"}
    ]
    current_location = "CN Tower, Toronto, ON"

    try:
        data = create_data_model(user_inputs, current_location)
    except ValueError as e:
        print(e)
        return

    # Create the Routing Index Manager and Routing Model.
    manager = pywrapcp.RoutingIndexManager(len(data['time_matrix']), data['num_vehicles'], data['depot'])
    routing = pywrapcp.RoutingModel(manager)

    # Create and register a transit callback.
    def time_callback(from_index, to_index):
        """Returns the travel time + service time between the two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['time_matrix'][from_node][to_node] + data['service_time'][from_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add Time Windows constraint.
    time = 'Time'
    routing.AddDimension(
        transit_callback_index,
        30,  # allow waiting time (e.g., arriving early before it opens)
        1200, # maximum time per vehicle (end of day)
        False,  # Don't force start to be exactly at 0
        time)
    time_dimension = routing.GetDimensionOrDie(time)

    # Add time window constraints for each location
    for location_idx, time_window in enumerate(data['time_windows']):
        if location_idx == data['depot']:
            continue
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])

    # Setting search parameters.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    # Solve the problem.
    solution = routing.SolveWithParameters(search_parameters)

    # Print solution on console.
    if solution:
        print_solution(manager, routing, solution, data['time_windows'][0][0])
    else:
        print("No solution found! The time windows might be impossible to meet.")

def print_solution(manager, routing, solution):
    """Prints solution to console."""
    print('✅ Optimal Route Found:')
    time_dimension = routing.GetDimensionOrDie('Time')
    index = routing.Start(0)
    plan_output = ''

    while not routing.IsEnd(index):
        time_var = time_dimension.CumulVar(index)
        node = manager.IndexToNode(index)

        # Convert minutes back to standard time format (HH:MM)
        min_time = solution.Min(time_var)
        hours, mins = divmod(min_time, 60)
        time_str = f"{hours:02d}:{mins:02d}"

        plan_output += f'Location {node} (Arrive ~ {time_str}) -> '
        index = solution.Value(routing.NextVar(index))

    time_var = time_dimension.CumulVar(index)
    min_time = solution.Min(time_var)
    hours, mins = divmod(min_time, 60)
    plan_output += f'Return to Start (Arrive ~ {hours:02d}:{mins:02d})'

    print(plan_output)
    actual_start_time = solution.Min(time_dimension.CumulVar(routing.Start(0)))
    print(f'Total travel and viewing time: {solution.Min(time_var) - actual_start_time} minutes')

if __name__ == '__main__':
    main()
