let map;
let directionsService;
let directionsRenderer;
let API_KEY = "";

// Map Initialization
async function initMapScript() {
    try {
        const response = await fetch('/api/maps-key');
        const data = await response.json();
        API_KEY = data.api_key;

        if (!API_KEY) {
            console.warn("No Google Maps API Key provided. Map will not load.");
            document.getElementById('map').innerHTML = "<div style='padding:40px;text-align:center;color:var(--text-muted);'>Map unavailable (No API key).</div>";
            return;
        }

        const script = document.createElement('script');
        script.src = `https://maps.googleapis.com/maps/api/js?key=${API_KEY}&callback=initMap`;
        script.defer = true;
        document.head.appendChild(script);
    } catch (err) {
        console.error("Failed to load map key", err);
    }
}

window.initMap = function() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: {lat: 43.651070, lng: -79.347015}, // Default to Toronto
        zoom: 12,
        styles: [
            { elementType: "geometry", stylers: [{ color: "#242f3e" }] },
            { elementType: "labels.text.stroke", stylers: [{ color: "#242f3e" }] },
            { elementType: "labels.text.fill", stylers: [{ color: "#746855" }] },
            {
              featureType: "administrative.locality",
              elementType: "labels.text.fill",
              stylers: [{ color: "#d59563" }],
            },
            {
              featureType: "poi",
              elementType: "labels.text.fill",
              stylers: [{ color: "#d59563" }],
            },
            {
              featureType: "poi.park",
              elementType: "geometry",
              stylers: [{ color: "#263c3f" }],
            },
            {
              featureType: "poi.park",
              elementType: "labels.text.fill",
              stylers: [{ color: "#6b9a76" }],
            },
            {
              featureType: "road",
              elementType: "geometry",
              stylers: [{ color: "#38414e" }],
            },
            {
              featureType: "road",
              elementType: "geometry.stroke",
              stylers: [{ color: "#212a37" }],
            },
            {
              featureType: "road",
              elementType: "labels.text.fill",
              stylers: [{ color: "#9ca5b3" }],
            },
            {
              featureType: "road.highway",
              elementType: "geometry",
              stylers: [{ color: "#746855" }],
            },
            {
              featureType: "road.highway",
              elementType: "geometry.stroke",
              stylers: [{ color: "#1f2835" }],
            },
            {
              featureType: "road.highway",
              elementType: "labels.text.fill",
              stylers: [{ color: "#f3d19c" }],
            },
            {
              featureType: "transit",
              elementType: "geometry",
              stylers: [{ color: "#2f3948" }],
            },
            {
              featureType: "transit.station",
              elementType: "labels.text.fill",
              stylers: [{ color: "#d59563" }],
            },
            {
              featureType: "water",
              elementType: "geometry",
              stylers: [{ color: "#17263c" }],
            },
            {
              featureType: "water",
              elementType: "labels.text.fill",
              stylers: [{ color: "#515c6d" }],
            },
            {
              featureType: "water",
              elementType: "labels.text.stroke",
              stylers: [{ color: "#17263c" }],
            },
        ],
    });
    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer({
        map: map,
        polylineOptions: {
            strokeColor: "#6366f1", // Match primary theme color
            strokeWeight: 5
        }
    });
};


document.addEventListener('DOMContentLoaded', () => {

    // Initialize Google Maps script
    initMapScript();

    const housesList = document.getElementById('houses-list');
    const addHouseBtn = document.getElementById('add-house-btn');
    const optimizeBtn = document.getElementById('optimize-btn');
    const resultSection = document.getElementById('result-section');
    const errorMessage = document.getElementById('error-message');

    // UI Elements for loader
    const btnText = optimizeBtn.querySelector('.btn-text');
    const loader = optimizeBtn.querySelector('.loader');

    // Initial Mock Data to populate
    const initialData = [
        { address: "756 Spadina Avenue, Toronto, ON", start: "13:00", end: "15:00" },
        { address: "123 Main St, Toronto, ON", start: "14:00", end: "16:00" },
        { address: "456 King St W, Toronto, ON", start: "13:30", end: "14:30" }
    ];

    // Initialize list
    initialData.forEach(data => addHouseInput(data.address, data.start, data.end));

    // Event Listeners
    addHouseBtn.addEventListener('click', () => addHouseInput("", "13:00", "15:00"));
    optimizeBtn.addEventListener('click', handleOptimize);

    function addHouseInput(address = "", start = "13:00", end = "15:00") {
        const item = document.createElement('div');
        item.className = 'house-item';

        item.innerHTML = `
            <div class="input-group flex-grow">
                <label>Address</label>
                <input type="text" class="house-address" placeholder="123 Example St" value="${address}">
            </div>
            <div class="input-group time-col">
                <label>Opens</label>
                <input type="time" class="house-start" value="${start}">
            </div>
            <div class="input-group time-col">
                <label>Closes</label>
                <input type="time" class="house-end" value="${end}">
            </div>
            <button class="btn-remove" aria-label="Remove Property" title="Remove Property">
                <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
            </button>
        `;

        item.querySelector('.btn-remove').addEventListener('click', () => {
            item.remove();
        });

        housesList.appendChild(item);
    }

    async function handleOptimize() {
        const currentLocation = document.getElementById('current-location').value;
        const houseElements = document.querySelectorAll('.house-item');

        // Collect Data
        const openHouses = [];
        let hasError = false;

        if (!currentLocation) hasError = true;

        houseElements.forEach(item => {
            const address = item.querySelector('.house-address').value;
            const start = item.querySelector('.house-start').value;
            const end = item.querySelector('.house-end').value;

            if (!address || !start || !end) {
                hasError = true;
            } else {
                openHouses.push({
                    address: address,
                    start_time: start,
                    end_time: end
                });
            }
        });

        if (hasError) {
            showError("Please fill out all location and time fields.");
            return;
        }

        if (openHouses.length === 0) {
            showError("Please add at least one open house to visit.");
            return;
        }

        // Prepare Request
        const requestData = {
            current_location: currentLocation,
            open_houses: openHouses
        };

        setLoading(true);
        hideError();
        resultSection.classList.add('hidden');

        try {
            const response = await fetch('/api/optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.detail || "Optimization failed.");
            }

            renderRoute(result);

        } catch (error) {
            showError(error.message);
        } finally {
            setLoading(false);
        }
    }

    function renderRoute(data) {
        document.getElementById('total-time-display').innerHTML = `Total Time: <span>${data.total_minutes} minutes</span> <span style="font-size:0.8rem; color:var(--text-muted); font-weight:400; margin-left:8px;">(Including 30 min viewings)</span>`;

        const timeline = document.getElementById('route-timeline');
        timeline.innerHTML = '';

        data.route.forEach((step, index) => {
            const stepDiv = document.createElement('div');
            stepDiv.className = `timeline-step ${step.is_start || step.is_end ? 'start-end' : ''}`;

            let label = '';
            if (step.is_start) label = 'Start location';
            else if (step.is_end) label = 'Return to start';
            else label = `Stop ${index}`;

            stepDiv.innerHTML = `
                <div class="step-time">Arrive ~ ${step.arrival_time}</div>
                <div class="step-address">${step.address}</div>
                <div class="step-label">${label}</div>
            `;
            timeline.appendChild(stepDiv);
        });

        resultSection.classList.remove('hidden');

        // Smooth scroll to results
        setTimeout(() => {
            resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);

        // Draw Map Route
        drawMapRoute(data.route);
    }

    function drawMapRoute(routeData) {
        if (!API_KEY || !directionsService) return;

        if (routeData.length < 2) return;

        const origin = routeData[0].address;
        const destination = routeData[routeData.length - 1].address;
        const waypoints = [];

        for (let i = 1; i < routeData.length - 1; i++) {
            waypoints.push({
                location: routeData[i].address,
                stopover: true
            });
        }

        directionsService.route({
            origin: origin,
            destination: destination,
            waypoints: waypoints,
            optimizeWaypoints: false, // We already optimized the order!
            travelMode: 'DRIVING'
        }, (response, status) => {
            if (status === 'OK') {
                directionsRenderer.setDirections(response);
            } else {
                console.error('Directions request failed due to ' + status);
            }
        });
    }

    function setLoading(isLoading) {
        optimizeBtn.disabled = isLoading;
        if (isLoading) {
            btnText.classList.add('hidden');
            loader.classList.remove('hidden');
        } else {
            btnText.classList.remove('hidden');
            loader.classList.add('hidden');
        }
    }

    function showError(msg) {
        errorMessage.textContent = msg;
        errorMessage.classList.remove('hidden');
    }

    function hideError() {
        errorMessage.classList.add('hidden');
    }
});
