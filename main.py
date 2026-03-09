from datetime import datetime
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def get_current_minutes():
    """Gets the current time and converts it to minutes from midnight."""
    now = datetime.now()
    # E.g., 1:29 PM -> 13 * 60 + 29 = 809 minutes
    current_minutes = (now.hour * 60) + now.minute
    return current_minutes

def create_data_model():
    """Stores the data for the open house routing problem."""
    data = {}
    current_time_mins = get_current_minutes()

    data['time_matrix'] = [
        [0, 15, 20, 10],  # From Current Location
        [15, 0, 12, 25],  # From House 1
        [20, 12, 0, 18],  # From House 2
        [10, 25, 18, 0],  # From House 3
    ]

    # 2. Open House Time Windows
    data['time_windows'] = [
        # DYNAMIC START: The user cannot start the route before "right now"
        (current_time_mins, 1440), # 0: Current Location (Available from NOW until end of day)
        (780, 900),   # 1: House 1 (Open 1:00 PM - 3:00 PM)
        (840, 960),   # 2: House 2 (Open 2:00 PM - 4:00 PM)
        (810, 870),   # 3: House 3 (Open 1:30 PM - 2:30 PM)
    ]

    data['service_time'] = [0, 30, 30, 30]
    data['num_vehicles'] = 1
    data['depot'] = 0
    return data

def main():
    # Instantiate the data problem.
    data = create_data_model()

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

def print_solution(manager, routing, solution, start_time_mins):
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
