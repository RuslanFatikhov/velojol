document.addEventListener('DOMContentLoaded', function() {
    mapboxgl.accessToken = 'pk.eyJ1IjoiZnV6bGFuIiwiYSI6ImNsc2N3dnhuNTBrZXYya28xeG1mb3k3N3AifQ.bLjMuXA5JfgBW0pwtjQxxA';
    
    var map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/dark-v11',
        center: cityCoordinates, // Установите реальные координаты центра карты
        zoom: 11
    });

    const initialCenter = cityCoordinates;
    const initialZoom = 12;

    let bikeLanesData = []; // Для хранения данных о велодорожках

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
        setLayerOpacity(); // Восстанавливаем прозрачность для всех слоев
        map.flyTo({center: initialCenter, zoom: initialZoom}); // Возвращаем карту к начальному виду
    };

    window.closeCustomPopup = function() {
        const customPopup = document.getElementById('customPopup');
        if (customPopup) {
            customPopup.style.display = 'none';
        }
        setLayerOpacity(); // Восстанавливаем прозрачность для всех слоев
        map.flyTo({center: initialCenter, zoom: initialZoom}); // Возвращаем карту к начальному виду
    };

    function createPopUpHtml(bikeLane) {
    let photosHtml = bikeLane.photos?.map(photo => `<img src="${photo}" data-imageview alt="Фото велодорожки">`).join('') || '';
    let ratingLabel = 'Неизвестно'; // Предварительное значение
    let color = 'gray'; // Цвет по умолчанию

    if (typeof bikeLane.safetyLevel === 'number' && bikeLane.safetyLevel >= 1 && bikeLane.safetyLevel <= 5) {
        switch (bikeLane.safetyLevel) {
            case 5: color = '#64C750'; ratingLabel = 'Отлично'; break;
            case 4: color = '#FFBD3F'; ratingLabel = 'Хорошо'; break;
            case 3: color = '#FF8552'; ratingLabel = 'Удовлетворительно'; break;
            case 2: color = '#E55D47'; ratingLabel = 'Плохо'; break;
            case 1: color = '#772613'; ratingLabel = 'Ужасно'; break;
        }
    }

    return `
        <div class="info">
            <h4 class="dark-prime-invert-200">${bikeLane.name}</h4>
            <p class="dark-prime-invert-200">${bikeLane.description}</p>
            <p style="background-color: ${color};color: #121212;padding: 2px 8px;border-radius: 8px; class="dark-prime-invert-300">${ratingLabel}</p>
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
        map.flyTo({center: bikeLane.coordinates[0], zoom: 14});
        const customPopup = document.getElementById('customPopup');
        if (customPopup) {
            customPopup.innerHTML = createPopUpHtml(bikeLane);
            initImageView(); // Инициализация обработчиков событий для новых изображений
            customPopup.style.display = 'block';
        }
        window.images = bikeLane.photos;
    }

    map.on('load', function() {
        fetch(`https://velojol.kz/${cityName}.json`)
            .then(response => response.json())
            .then(data => {
                bikeLanesData = data; // Сохраняем данные о велодорожках
                
                const bikeLanesList = document.getElementById('bikeLanesList');
                bikeLanesList.innerHTML = '';

                data.forEach(bikeLane => {
                        let color = 'gray', ratingLabel = 'Неизвестно';
                        switch (bikeLane.safetyLevel) {
                            case 5: color = '#64C750'; ratingLabel = 'Отлично'; break;
                            case 4: color = '#FFBD3F'; ratingLabel = 'Хорошо'; break;
                            case 3: color = '#FF8552'; ratingLabel = 'Удовлетворительно'; break;
                            case 2: color = '#E55D47'; ratingLabel = 'Плохо'; break;
                            case 1: color = '#772613'; ratingLabel = 'Ужасно'; break;
                        }

                    const layerId = `bikeLane-${bikeLane.id}`;
                        map.addLayer({
                            'id': layerId,
                            'type': 'line',
                            'source': {
                                'type': 'geojson',
                                'data': {
                                    'type': 'Feature',
                                    'properties': bikeLane,
                                    'geometry': {
                                        'type': 'LineString',
                                        'coordinates': bikeLane.coordinates
                                    }
                                }
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
                                    <span style="background-color: ${color}; color: #121212;font-weight:bold; letter-spacing:-2%; padding: 2px 8px 2px 8px; border-radius: 4px;">${ratingLabel}</span>
                                </div>
                            </span>
                        `;
                        bikeLaneItem.onclick = function() {
                            handleBikeLaneClick(bikeLane);
                        };
                        bikeLanesList.appendChild(bikeLaneItem);
                    });

                // Внешний клик для закрытия customPopup
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
});