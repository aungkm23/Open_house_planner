from datetime import datetime
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List
import os

import geocoder

load_dotenv()

app = FastAPI()

# --- Pydantic Models ---
class OpenHouseInput(BaseModel):
    address: str
    start_time: str
    end_time: str

class OptimizationRequest(BaseModel):
    current_location: str
    open_houses: List[OpenHouseInput]

class RouteStep(BaseModel):
    location_index: int
    address: str
    arrival_time: str
    is_start: bool = False
    is_end: bool = False

class OptimizationResponse(BaseModel):
    total_minutes: int
    route: List[RouteStep]

# --- Core Logic ---
def get_current_minutes():
    """Gets the current time and converts it to minutes from midnight."""
    now = datetime.now()
    return (now.hour * 60) + now.minute

def parse_time_string(time_str):
    """Converts a time string like '14:00' to minutes from midnight."""
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes

def format_minutes_to_time(minutes):
    """Converts minutes from midnight back to 'HH:MM' string."""
    hours, mins = divmod(minutes, 60)
    return f"{hours:02d}:{mins:02d}"

def create_data_model(user_inputs, current_location):
    """Stores the data for the open house routing problem based on user inputs."""
    data = {}
    current_time_mins = get_current_minutes()

    addresses = [current_location] + [item.address for item in user_inputs]
    data['addresses'] = addresses

    # 1. Travel Time Matrix
    data['time_matrix'] = geocoder.get_distance_matrix(addresses)
    if not data['time_matrix']:
        raise ValueError("Could not get distance matrix. Please check your addresses or API key.")

    # 2. Open House Time Windows
    time_windows = [(current_time_mins, 1440)] # 0: Current Location (Available from NOW until end of day)

    for item in user_inputs:
        start_mins = parse_time_string(item.start_time)
        end_mins = parse_time_string(item.end_time)
        time_windows.append((start_mins, end_mins))

    data['time_windows'] = time_windows

    # 3. Service Time
    # Assuming 0 service time at current location, and 30 minutes at each house
    data['service_time'] = [0] + [30] * len(user_inputs)

    data['num_vehicles'] = 1
    data['depot'] = 0
    return data

def solve_routing_problem(data):
    """Runs OR-Tools solver and returns structured route data."""
    manager = pywrapcp.RoutingIndexManager(len(data['time_matrix']), data['num_vehicles'], data['depot'])
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['time_matrix'][from_node][to_node] + data['service_time'][from_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    time = 'Time'
    routing.AddDimension(
        transit_callback_index,
        30,  # allow waiting time
        1440, # maximum time per vehicle (extended to end of day)
        False,
        time)
    time_dimension = routing.GetDimensionOrDie(time)

    for location_idx, time_window in enumerate(data['time_windows']):
        if location_idx == data['depot']:
            continue
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(time_window[0], time_window[1])

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        return None

    # Extract Route
    route = []
    index = routing.Start(0)
    
    while not routing.IsEnd(index):
        time_var = time_dimension.CumulVar(index)
        node = manager.IndexToNode(index)
        min_time = solution.Min(time_var)
        
        route.append(RouteStep(
            location_index=node,
            address=data['addresses'][node],
            arrival_time=format_minutes_to_time(min_time),
            is_start=(node == 0)
        ))
        index = solution.Value(routing.NextVar(index))

    # Add the return to start node
    time_var = time_dimension.CumulVar(index)
    min_time = solution.Min(time_var)
    route.append(RouteStep(
        location_index=0,
        address=data['addresses'][0],
        arrival_time=format_minutes_to_time(min_time),
        is_end=True
    ))

    actual_start_time = solution.Min(time_dimension.CumulVar(routing.Start(0)))
    total_time = solution.Min(time_var) - actual_start_time

    return OptimizationResponse(total_minutes=total_time, route=route)


# --- API Routes ---
@app.post("/api/optimize", response_model=OptimizationResponse)
async def optimize_route(request: OptimizationRequest):
    try:
        data = create_data_model(request.open_houses, request.current_location)
        result = solve_routing_problem(data)
        
        if not result:
            raise HTTPException(status_code=400, detail="No valid route found. Time windows might be impossible to meet.")
            
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Serve static files for frontend
# Make sure the static directory exists before mounting
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
