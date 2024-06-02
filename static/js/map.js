document.addEventListener('DOMContentLoaded', function () {
    mapboxgl.accessToken = 'pk.eyJ1IjoiZnV6bGFuIiwiYSI6ImNsc2N3dnhuNTBrZXYya28xeG1mb3k3N3AifQ.bLjMuXA5JfgBW0pwtjQxxA';

    const map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/dark-v11',
        center: cityCoordinates,
        zoom: 11
    });

    const initialCenter = cityCoordinates;
    const initialZoom = 12;
    let bikeLanesData = [];

    function setLayerOpacity(exceptId = "") {
        const mapStyle = map.getStyle();
        if (mapStyle && mapStyle.layers) {
            mapStyle.layers.forEach(layer => {
                if (layer.id.startsWith('bikeLane-')) {
                    map.setPaintProperty(layer.id, 'line-opacity', exceptId === layer.id ? 1 : 0.5);
                }
            });
        }
    }

    function closeCustomPopup() {
        const customPopup = document.getElementById('customPopup');
        if (customPopup) {
            customPopup.style.display = 'none';
        }
        setLayerOpacity();
        map.flyTo({ center: initialCenter, zoom: initialZoom });
    }

    window.closeCustomPopup = closeCustomPopup;

    function getSafetyLevelDetails(safetyLevel) {
        const safetyLevels = {
            5: { color: '#64C750', label: 'Отлично' },
            4: { color: '#FFBD3F', label: 'Хорошо' },
            3: { color: '#FF8552', label: 'Удовлетворительно' },
            2: { color: '#E55D47', label: 'Плохо' },
            1: { color: '#772613', label: 'Ужасно' }
        };
        return safetyLevels[safetyLevel] || { color: 'gray', label: 'Неизвестно' };
    }

    function createPopUpHtml(bikeLane) {
        const { color, label } = getSafetyLevelDetails(bikeLane.safetyLevel);
        const photosHtml = bikeLane.photos?.map(photo => `<img src="${photo}" data-imageview alt="Фото велодорожки">`).join('') || '';
        
        return `
            <div class="info">
                <h4 class="dark-prime-invert-200">${bikeLane.name}</h4>
                <p class="dark-prime-invert-200">${bikeLane.description}</p>
                <p style="background-color: ${color};color: #121212;padding: 2px 8px;border-radius: 8px;" class="dark-prime-invert-300">${label}</p>
                <div class="photogrid">${photosHtml}</div>
                <span class="hstack sb">
                    <p class="dark-prime-invert-50">Источник: ${bikeLane.source}</p>
                    <p class="dark-prime-invert-50">${bikeLane.date}</p>
                </span>
                <button class="size_s absolute_rt" onclick="closeCustomPopup();">
                    <img src="../static/images/icon/close.svg" alt="Закрыть">
                </button>
            </div>
        `;
    }

    function handleBikeLaneClick(bikeLane) {
        setLayerOpacity(`bikeLane-${bikeLane.id}`);
        map.flyTo({ center: bikeLane.coordinates[0], zoom: 14 });
        const customPopup = document.getElementById('customPopup');
        if (customPopup) {
            customPopup.innerHTML = createPopUpHtml(bikeLane);
            initImageView();
            customPopup.style.display = 'block';
        }
        window.images = bikeLane.photos;
    }

    function createBikeLaneLayer(bikeLane) {
        const { color } = getSafetyLevelDetails(bikeLane.safetyLevel);
        const layerId = `bikeLane-${bikeLane.id}`;
        
        map.addLayer({
            id: layerId,
            type: 'line',
            source: {
                type: 'geojson',
                data: {
                    type: 'Feature',
                    properties: bikeLane,
                    geometry: {
                        type: 'LineString',
                        coordinates: bikeLane.coordinates
                    }
                }
            },
            layout: {
                'line-join': 'round',
                'line-cap': 'round'
            },
            paint: {
                'line-color': color,
                'line-width': 6,
                'line-opacity': 0.5
            }
        });
    }

    function createBikeLaneListItem(bikeLane) {
        const { color, label } = getSafetyLevelDetails(bikeLane.safetyLevel);
        const bikeLaneItem = document.createElement('div');
        bikeLaneItem.classList.add('bike-lane-item');
        bikeLaneItem.innerHTML = `
            <img src="${bikeLane.photos[0]}" alt="${bikeLane.name}">
            <span>
                <div>
                    <h6 style="margin-bottom:8px;">${bikeLane.name}</h6>
                    <span style="background-color: ${color}; color: #121212;font-weight:bold; letter-spacing:-2%; padding: 2px 8px 2px 8px; border-radius: 4px;">${label}</span>
                </div>
            </span>
        `;
        bikeLaneItem.onclick = function () {
            handleBikeLaneClick(bikeLane);
        };
        return bikeLaneItem;
    }

    function populateBikeLanesList(data) {
        const bikeLanesList = document.getElementById('bikeLanesList');
        bikeLanesList.innerHTML = '';
        data.sort((a, b) => a.name.localeCompare(b.name)).forEach(bikeLane => {
            createBikeLaneLayer(bikeLane);
            const bikeLaneItem = createBikeLaneListItem(bikeLane);
            bikeLanesList.appendChild(bikeLaneItem);
        });
    }

    map.on('load', function () {
        fetch(`https://velojol.kz/${cityName}.json`)
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok ' + response.statusText);
                }
                return response.json();
            })
            .then(data => {
                if (typeof data !== 'object') {
                    throw new Error('Invalid JSON response');
                }
                bikeLanesData = data;
                populateBikeLanesList(data);

                map.on('click', function (e) {
                    const features = map.queryRenderedFeatures(e.point, { layers: data.map(bikeLane => `bikeLane-${bikeLane.id}`) });
                    if (features.length) {
                        const clickedBikeLaneId = features[0].properties.id;
                        const clickedBikeLane = bikeLanesData.find(bikeLane => bikeLane.id === clickedBikeLaneId);
                        if (clickedBikeLane) {
                            handleBikeLaneClick(clickedBikeLane);
                        }
                    }
                });
            })
            .catch(error => {
                console.error('Error loading bike lanes:', error);
                alert('Error loading bike lanes: ' + error.message);
            });
    });

    function initializeZoomControls() {
        const zoomInButton = document.getElementById('zoomIn');
        const zoomOutButton = document.getElementById('zoomOut');

        if (zoomInButton && zoomOutButton) {
            zoomInButton.addEventListener('click', function () {
                map.zoomIn();
            });

            zoomOutButton.addEventListener('click', function () {
                map.zoomOut();
            });
        } else {
            console.error('Zoom buttons not found in the DOM.');
        }
    }

    // Initialize zoom controls after a short delay to ensure DOM elements are loaded
    setTimeout(initializeZoomControls, 1000);
});
