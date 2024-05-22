document.addEventListener('DOMContentLoaded', function() {
    mapboxgl.accessToken = 'pk.eyJ1IjoiZnV6bGFuIiwiYSI6ImNsc2N3dnhuNTBrZXYya28xeG1mb3k3N3AifQ.bLjMuXA5JfgBW0pwtjQxxA';

    const cityName = 'алматы'; // Замените на нужное название города или сделайте его динамическим
    const bikeLanesUrl = `https://velojol.kz/${cityName}.json`;

    var map = new mapboxgl.Map({
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

    window.closeCustomPopup = function() {
        document.getElementById('customPopup').style.display = 'none';
        setLayerOpacity();
        map.flyTo({center: initialCenter, zoom: initialZoom});
    };

    function createPopUpHtml(bikeLane) {
        let photosHtml = bikeLane.photos?.map(photo => `<img src="${photo}" data-imageview alt="Фото велодорожки">`).join('') || '';
        let ratingLabel = 'Неизвестно';
        if (typeof bikeLane.safetyLevel === 'number' && bikeLane.safetyLevel >= 1 && bikeLane.safetyLevel <= 5) {
            switch (bikeLane.safetyLevel) {
                case 5: ratingLabel = 'Отлично'; break;
                case 4: ratingLabel = 'Хорошо'; break;
                case 3: ratingLabel = 'Удовлетворительно'; break;
                case 2: ratingLabel = 'Плохо'; break;
                case 1: ratingLabel = 'Ужасно'; break;
                case 0: ratingLabel = 'Неизвестно'; break;
            }
        }
        return `
            <div class="popup-content">
                <h3>${bikeLane.name}</h3>
                <p>Уровень безопасности: ${ratingLabel}</p>
                <div class="photos">${photosHtml}</div>
            </div>
        `;
    }

    function handleBikeLaneClick(bikeLane) {
        const popup = document.getElementById('customPopup');
        popup.innerHTML = createPopUpHtml(bikeLane);
        popup.style.display = 'block';
        setLayerOpacity(`bikeLane-${bikeLane.id}`);
        map.flyTo({center: bikeLane.coordinates, zoom: 14});
    }

    console.log(`Attempting to fetch bike lanes from URL: ${bikeLanesUrl}`);
    fetch(bikeLanesUrl)
        .then(response => {
            console.log(`HTTP response status: ${response.status}`);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error(`Expected JSON, got ${contentType}`);
            }
            return response.json();
        })
        .then(data => {
            bikeLanesData = data;
            data.forEach(bikeLane => {
                const color = bikeLane.color || 'blue';
                map.addLayer({
                    'id': `bikeLane-${bikeLane.id}`,
                    'type': 'line',
                    'source': {
                        'type': 'geojson',
                        'data': bikeLane.geojson
                    },
                    'layout': {
                        'line-join': 'round',
                        'line-cap': 'round'
                    },
                    'paint': {
                        'line-color': color,
                        'line-width': 6,
                        'line-opacity': 0.5
                    }
                });

                const bikeLaneItem = document.createElement('div');
                bikeLaneItem.classList.add('bike-lane-item');
                bikeLaneItem.innerHTML = `
                    <img src="${bikeLane.photos[0]}" alt="${bikeLane.name}">
                    <span>
                        <div>
                            <h6 style="margin-bottom:8px;">${bikeLane.name}</h6>
                            <span style="background-color: ${color}; color: ${color === 'yellow' ? 'black' : 'white'}; padding: 0px 5px; border-radius: 4px;">${ratingLabel}</span>
                        </div>
                    </span>
                `;
                bikeLaneItem.onclick = function() {
                    handleBikeLaneClick(bikeLane);
                };
                bikeLanesList.appendChild(bikeLaneItem);
            });

            map.on('click', function(e) {
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
        .catch(error => console.error('Error loading bike lanes:', error));
});
