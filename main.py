from datetime import datetime, timedelta
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
    date: str
    start_time: str
    end_time: str

class OptimizationRequest(BaseModel):
    current_location: str
    start_date: str
    end_date: str
    single_day_pref: bool
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

class ScrapeRequest(BaseModel):
    url: str

class ScrapeResponse(BaseModel):
    address: str
    start_time: str
    end_time: str

# --- Core Logic ---
def get_minutes_from_start(date_str, time_str, start_date_str):
    """Calculates minutes from midnight of start_date_str."""
    fmt = "%Y-%m-%d %H:%M"
    start_dt = datetime.strptime(f"{start_date_str} 00:00", fmt)
    target_dt = datetime.strptime(f"{date_str} {time_str}", fmt)
    delta = target_dt - start_dt
    return int(delta.total_seconds() // 60)

def format_minutes_to_datetime(minutes, start_date_str):
    """Converts minutes back to a datetime string."""
    fmt = "%Y-%m-%d %H:%M"
    start_dt = datetime.strptime(f"{start_date_str} 00:00", fmt)
    target_dt = start_dt + timedelta(minutes=minutes)
    return target_dt.strftime(fmt)

def create_data_model(user_inputs, current_location, start_date, end_date, single_day_pref):
    """Stores the data for the open house routing problem based on user inputs."""
    data = {}
    
    fmt = "%Y-%m-%d"
    s_dt = datetime.strptime(start_date, fmt)
    e_dt = datetime.strptime(end_date, fmt)
    num_days = (e_dt - s_dt).days + 1
    
    if num_days <= 0:
        raise ValueError("End Date must be on or after Start Date.")
        
    data['num_vehicles'] = num_days
    data['depot'] = 0
    data['start_date'] = start_date
    data['single_day_pref'] = single_day_pref

    addresses = [current_location] + [item.address for item in user_inputs]
    data['addresses'] = addresses

    # 1. Travel Time Matrix
    data['time_matrix'] = geocoder.get_distance_matrix(addresses)
    if not data['time_matrix']:
        raise ValueError("Could not get distance matrix. Please check your addresses or API key.")

    # 2. Open House Time Windows
    time_windows = []
    time_windows.append((0, num_days * 1440))  # Depot available at any time
    
    for item in user_inputs:
        try:
            start_mins = get_minutes_from_start(item.date, item.start_time, start_date)
            end_mins = get_minutes_from_start(item.date, item.end_time, start_date)
            
            if end_mins < 0 or start_mins > num_days * 1440:
                raise ValueError(f"Property {item.address} on {item.date} is outside the availability window.")
            time_windows.append((start_mins, end_mins))
        except ValueError as e:
            if "outside the availability window" in str(e):
                raise
            raise ValueError(f"Invalid date/time for property {item.address}.")

    data['time_windows'] = time_windows

    # 3. Service Time
    data['service_time'] = [0] + [30] * len(user_inputs)

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
    max_time = data['num_vehicles'] * 1440
    routing.AddDimension(
        transit_callback_index,
        1440,  # allow waiting time 
        max_time, # max time globally
        False,
        time)
    time_dimension = routing.GetDimensionOrDie(time)

    # Restrict vehicles to their respective days
    for v in range(data['num_vehicles']):
        day_start = v * 1440
        day_end = (v + 1) * 1440
        start_index = routing.Start(v)
        end_index = routing.End(v)
        time_dimension.CumulVar(start_index).SetRange(day_start, day_end)
        time_dimension.CumulVar(end_index).SetRange(day_start, day_end)
        
    # If they want everything in a single day, penalize using multiple vehicles
    if data['single_day_pref']:
        routing.SetFixedCostOfAllVehicles(1000000)

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

    # Check if multiple vehicles used when single_day wanted
    if data['single_day_pref']:
        used_vehicles = sum(1 for v in range(data['num_vehicles']) if not routing.IsEnd(solution.Value(routing.NextVar(routing.Start(v)))))
        if used_vehicles > 1:
            return None 

    route = []
    total_active_time = 0

    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        if routing.IsEnd(solution.Value(routing.NextVar(index))):
            continue
            
        while not routing.IsEnd(index):
            time_var = time_dimension.CumulVar(index)
            min_time = solution.Min(time_var)
            node = manager.IndexToNode(index)
            
            route.append(RouteStep(
                location_index=node,
                address=data['addresses'][node],
                arrival_time=format_minutes_to_datetime(min_time, data['start_date']),
                is_start=(node == 0),
                is_end=False
            ))
            index = solution.Value(routing.NextVar(index))
            
        # Add return to start node
        time_var = time_dimension.CumulVar(index)
        min_time = solution.Min(time_var)
        route.append(RouteStep(
            location_index=0,
            address=data['addresses'][0],
            arrival_time=format_minutes_to_datetime(min_time, data['start_date']),
            is_start=False,
            is_end=True
        ))
        
        actual_start_time = solution.Min(time_dimension.CumulVar(routing.Start(vehicle_id)))
        actual_end_time = solution.Min(time_dimension.CumulVar(routing.End(vehicle_id)))
        total_active_time += (actual_end_time - actual_start_time)

    return OptimizationResponse(total_minutes=total_active_time, route=route)


# --- API Routes ---
@app.post("/api/scrape", response_model=ScrapeResponse)
async def scrape_route(request: ScrapeRequest):
    try:
        from scraper import scrape_url
        result = scrape_url(request.url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/api/optimize", response_model=OptimizationResponse)
async def optimize_route(request: OptimizationRequest):
    try:
        data = create_data_model(
            request.open_houses, 
            request.current_location,
            request.start_date,
            request.end_date,
            request.single_day_pref
        )
        result = solve_routing_problem(data)
        
        if not result:
            raise HTTPException(status_code=400, detail="No valid route found. Time windows might be impossible to meet or 'Put everything in one day' cannot be satisfied.")
            
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Serve static files for frontend
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
