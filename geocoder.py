import os
import googlemaps

def get_distance_matrix(addresses):
    """
    Given a list of addresses, returns a 2D array representing travel time
    in minutes from every address to every other address.
    """
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    if not api_key:
        print("Warning: GOOGLE_MAPS_API_KEY not found. Falling back to mock data.")
        # Fallback dummy data if no API key is provided
        # Dynamic dummy data based on length
        size = len(addresses)
        return [[15 if i != j else 0 for j in range(size)] for i in range(size)]

    gmaps = googlemaps.Client(key=api_key)

    # We use Google Maps Distance Matrix API
    # The matrix API returns durations in seconds, we convert to minutes
    matrix = []

    # Note: Google Maps Distance Matrix API has limits on elements per request.
    # For a small number of addresses, we can just send them all at once.
    try:
        response = gmaps.distance_matrix(origins=addresses, destinations=addresses, mode="driving")
        rows = response.get('rows', [])

        for row in rows:
            matrix_row = []
            for element in row.get('elements', []):
                # element format: {'distance': {'text': '...', 'value': ...}, 'duration': {'text': '...', 'value': ...}, 'status': 'OK'}
                if element.get('status') == 'OK':
                    duration_seconds = element.get('duration', {}).get('value', 0)
                    matrix_row.append(duration_seconds // 60)
                else:
                    # If route is impossible, append a very large number
                    matrix_row.append(999999)
            matrix.append(matrix_row)
        return matrix
    except Exception as e:
        print(f"Error fetching distance matrix from Google Maps API: {e}")
        return []
