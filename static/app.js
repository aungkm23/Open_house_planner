document.addEventListener('DOMContentLoaded', () => {
    
    const housesList = document.getElementById('houses-list');
    const addHouseBtn = document.getElementById('add-house-btn');
    const addLinkBtn = document.getElementById('add-link-btn');
    const optimizeBtn = document.getElementById('optimize-btn');
    const linkModal = document.getElementById('link-modal');
    const cancelLinkBtn = document.getElementById('cancel-link-btn');
    const submitLinkBtn = document.getElementById('submit-link-btn');
    const propertyLinkInput = document.getElementById('property-link-input');
    const linkErrorMessage = document.getElementById('link-error-message');
    const resultSection = document.getElementById('result-section');
    const errorMessage = document.getElementById('error-message');
    
    // Map Variables
    let map;
    let markers = [];
    let routeLine = null;
    const exportGmapsBtn = document.getElementById('export-gmaps-btn');

    // Initialize map
    initMap();

    function initMap() {
        // Default center (Toronto roughly)
        map = L.map('map').setView([43.651070, -79.347015], 13);

        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(map);
    }
    
    // UI Elements for loader
    const btnText = optimizeBtn.querySelector('.btn-text');
    const loader = optimizeBtn.querySelector('.loader');

    // Helper for dates
    function getUpcomingDay(dayOfWeek) {
        const d = new Date();
        const diff = (dayOfWeek + 7 - d.getDay()) % 7;
        d.setDate(d.getDate() + (diff === 0 ? 0 : diff));
        return d.toISOString().split('T')[0];
    }
    const saturdayDate = getUpcomingDay(6);
    const sundayDate = getUpcomingDay(0);

    // Set default user availability window
    document.getElementById('start-date').value = saturdayDate;
    document.getElementById('end-date').value = sundayDate;

    // Initial Mock Data to populate
    const initialData = [
        { address: "756 Spadina Avenue, Toronto, ON", date: saturdayDate, start: "13:00", end: "15:00" },
        { address: "123 Main St, Toronto, ON", date: saturdayDate, start: "14:00", end: "16:00" },
        { address: "456 King St W, Toronto, ON", date: sundayDate, start: "13:30", end: "14:30" }
    ];

    // Initialize list
    initialData.forEach(data => addHouseInput(data.address, data.date, data.start, data.end));

    // Plot initial locations on map
    plotUnoptimizedLocations();

    // Event Listeners
    addHouseBtn.addEventListener('click', () => {
        addHouseInput("", saturdayDate, "13:00", "15:00");
    });

    document.getElementById('current-location').addEventListener('change', plotUnoptimizedLocations);

    addLinkBtn.addEventListener('click', () => {
        linkModal.classList.remove('hidden');
        propertyLinkInput.value = '';
        linkErrorMessage.classList.add('hidden');
        propertyLinkInput.focus();
    });

    cancelLinkBtn.addEventListener('click', () => {
        linkModal.classList.add('hidden');
    });

    submitLinkBtn.addEventListener('click', handleScrapeLink);

    optimizeBtn.addEventListener('click', handleOptimize);

    async function handleScrapeLink() {
        const url = propertyLinkInput.value.trim();
        if (!url) {
            linkErrorMessage.textContent = "Please enter a valid link.";
            linkErrorMessage.classList.remove('hidden');
            return;
        }

        const btnText = submitLinkBtn.querySelector('.btn-text');
        const loader = submitLinkBtn.querySelector('.loader');

        submitLinkBtn.disabled = true;
        btnText.classList.add('hidden');
        loader.classList.remove('hidden');
        linkErrorMessage.classList.add('hidden');

        try {
            const response = await fetch('/api/scrape', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: url })
            });

            if (!response.ok) {
                throw new Error("Failed to extract property details.");
            }

            const data = await response.json();
            addHouseInput(data.address, saturdayDate, data.start_time, data.end_time);
            linkModal.classList.add('hidden');
        } catch (error) {
            linkErrorMessage.textContent = error.message;
            linkErrorMessage.classList.remove('hidden');
        } finally {
            submitLinkBtn.disabled = false;
            btnText.classList.remove('hidden');
            loader.classList.add('hidden');
        }
    }

    function addHouseInput(address = "", date = "", start = "13:00", end = "15:00") {
        const item = document.createElement('div');
        item.className = 'house-item';
        
        item.innerHTML = `
            <div class="input-group flex-grow">
                <label>Address</label>
                <input type="text" class="house-address" placeholder="123 Example St" value="${address}">
            </div>
            <div class="input-group time-col">
                <label>Date</label>
                <input type="date" class="house-date" value="${date}">
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
            plotUnoptimizedLocations();
        });

        item.querySelector('.house-address').addEventListener('change', plotUnoptimizedLocations);

        housesList.appendChild(item);
        if (address) {
            plotUnoptimizedLocations();
        }
    }

    function collectFormData() {
        const currentLocation = document.getElementById('current-location').value;
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;
        const singleDayPref = document.getElementById('single-day-pref').checked;
        const houseElements = document.querySelectorAll('.house-item');
        
        const openHouses = [];
        let hasError = false;

        if (!currentLocation || !startDate || !endDate) hasError = true;

        houseElements.forEach(item => {
            const address = item.querySelector('.house-address').value;
            const houseDate = item.querySelector('.house-date').value;
            const start = item.querySelector('.house-start').value;
            const end = item.querySelector('.house-end').value;

            if (!address || !houseDate || !start || !end) {
                hasError = true;
            } else {
                openHouses.push({
                    address: address,
                    date: houseDate,
                    start_time: start,
                    end_time: end
                });
            }
        });

        return {
            current_location: currentLocation,
            start_date: startDate,
            end_date: endDate,
            single_day_pref: singleDayPref,
            open_houses: openHouses,
            hasError: hasError
        };
    }

    async function handleOptimize() {
        const data = collectFormData();

        if (data.hasError) {
            showError("Please fill out all location and time fields.");
            return;
        }

        if (data.open_houses.length === 0) {
            showError("Please add at least one open house to visit.");
            return;
        }

        const requestData = {
            current_location: data.current_location,
            start_date: data.start_date,
            end_date: data.end_date,
            single_day_pref: data.single_day_pref,
            open_houses: data.open_houses
        };

        setLoading(true);
        hideError();
        resultSection.classList.add('hidden');
        exportGmapsBtn.classList.add('hidden');

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

    async function geocodeAddress(address) {
        // Quick local Nominatim check to translate addresses to lat/lon for the Map
        const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address)}`;
        try {
            const response = await fetch(url);
            const data = await response.json();
            if (data && data.length > 0) {
                return [parseFloat(data[0].lat), parseFloat(data[0].lon)];
            }
        } catch (e) {
            console.warn("Geocoding failed for: ", address);
        }
        return null;
    }

    function clearMap() {
        markers.forEach(m => map.removeLayer(m));
        markers = [];
        if (routeLine) {
            map.removeLayer(routeLine);
            routeLine = null;
        }
    }

    async function plotUnoptimizedLocations() {
        // Debounce slightly if called multiple times rapidly via input
        clearTimeout(plotUnoptimizedLocations.timeout);
        plotUnoptimizedLocations.timeout = setTimeout(async () => {
            
            const formData = collectFormData();
            if (formData.hasError) return; // Don't try plotting if incomplete

            clearMap();

            const allAddresses = [formData.current_location, ...formData.open_houses.map(h => h.address)];
            let boundsData = [];

            for (let i = 0; i < allAddresses.length; i++) {
                const address = allAddresses[i];
                if (!address) continue;

                const latlng = await geocodeAddress(address);
                if (latlng) {
                    boundsData.push(latlng);
                    
                    const isStart = (i === 0);
                    const markerColor = isStart ? '#8b5cf6' : '#94a3b8'; // Purple for start, subtle gray for others
                    const iconText = isStart ? 'S' : '';

                    const htmlIcon = L.divIcon({
                        className: 'custom-div-icon',
                        html: `<div style="background-color:${markerColor}; width:24px; height:24px; border-radius:12px; display:flex; justify-content:center; align-items:center; color:white; font-size:12px; font-weight:bold; border: 2px solid #1e293b; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">${iconText}</div>`,
                        iconSize: [24, 24],
                        iconAnchor: [12, 12]
                    });

                    const marker = L.marker(latlng, { icon: htmlIcon }).addTo(map);
                    marker.bindPopup(`<b>${isStart ? 'Starts at: ' : 'Open House: '}${address}</b>`);
                    markers.push(marker);
                }
            }

            if (boundsData.length > 0) {
                const bounds = L.latLngBounds(boundsData);
                map.fitBounds(bounds, { padding: [50, 50], maxZoom: 15 });
            }

        }, 500); // 500ms debounce
    }

    async function renderRoute(data) {
        document.getElementById('total-time-display').innerHTML = `Total Time: <span>${data.total_minutes} minutes</span> <span style="font-size:0.8rem; color:var(--text-muted); font-weight:400; margin-left:8px;">(Including 30 min viewings)</span>`;
        
        const timeline = document.getElementById('route-timeline');
        timeline.innerHTML = '';

        clearMap();

        let routeCoordinates = [];
        
        // GMaps URL generation Variables
        let gmapsOrigin = "";
        let gmapsDestination = "";
        let gmapsWaypoints = [];

        for (let index = 0; index < data.route.length; index++) {
            const step = data.route[index];

            // Render Timeline
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

            // Populate GMaps Variables
            if (step.is_start) {
                gmapsOrigin = encodeURIComponent(step.address);
            } else if (step.is_end) {
                gmapsDestination = encodeURIComponent(step.address);
            } else {
                gmapsWaypoints.push(encodeURIComponent(step.address));
            }

            // Let's geocode to plot on Map
            // Optimization: Since 'return to start' is the same address as 'start location', 
            // no need to re-geocode the final step if it's identical
            if (step.is_end) {
                if (routeCoordinates.length > 0) {
                    routeCoordinates.push(routeCoordinates[0]); // Loop back
                }
                continue;
            }

            const latlng = await geocodeAddress(step.address);
            if (latlng) {
                routeCoordinates.push(latlng);
                
                // Create custom icons depending on type
                let markerColor = step.is_start ? '#8b5cf6' : '#6366f1';
                
                const htmlIcon = L.divIcon({
                    className: 'custom-div-icon',
                    html: `<div style="background-color:${markerColor}; width:30px; height:30px; border-radius:15px; display:flex; justify-content:center; align-items:center; color:white; font-weight:bold; border: 3px solid #1e293b; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">${step.is_start ? 'S' : index}</div>`,
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                });

                const marker = L.marker(latlng, { icon: htmlIcon }).addTo(map);
                marker.bindPopup(`<b>${step.address}</b><br>Arr: ${step.arrival_time}`);
                markers.push(marker);
            }
        }

        // Generate Google Maps Link
        if (gmapsOrigin && gmapsDestination) {
            let gmapsUrl = `https://www.google.com/maps/dir/?api=1&origin=${gmapsOrigin}&destination=${gmapsDestination}`;
            if (gmapsWaypoints.length > 0) {
                gmapsUrl += `&waypoints=${gmapsWaypoints.join('|')}`;
            }
            exportGmapsBtn.href = gmapsUrl;
            exportGmapsBtn.classList.remove('hidden');
        }

        // Draw line between markers on map
        if (routeCoordinates.length > 1) {
            routeLine = L.polyline(routeCoordinates, {
                color: '#8b5cf6', 
                weight: 4, 
                opacity: 0.8, 
                dashArray: '10, 10'
            }).addTo(map);
            map.fitBounds(routeLine.getBounds(), { padding: [50, 50], maxZoom: 15 });
        }

        resultSection.classList.remove('hidden');
        
        // Smooth scroll to results
        setTimeout(() => {
            resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
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
