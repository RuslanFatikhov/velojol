document.addEventListener('DOMContentLoaded', function () {
    mapboxgl.accessToken = 'pk.eyJ1IjoiZnV6bGFuIiwiYSI6ImNsc2N3dnhuNTBrZXYya28xeG1mb3k3N3AifQ.bLjMuXA5JfgBW0pwtjQxxA';

    const map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/light-v10',
        center: [76.95, 43.24],  // Центр Алматы
        zoom: 9
    });

    function initializeMap(routeId) {
        fetch(`/static/gpx/${routeId}.gpx`)
            .then(response => response.text())
            .then(gpxData => {
                const gpx = new DOMParser().parseFromString(gpxData, 'text/xml');
                const geojson = toGeoJSON.gpx(gpx);

                const coordinates = geojson.features[0].geometry.coordinates;

                map.on('load', function () {
                    map.addSource('route', {
                        'type': 'geojson',
                        'data': geojson
                    });

                    map.addLayer({
                        'id': 'route',
                        'type': 'line',
                        'source': 'route',
                        'layout': {
                            'line-join': 'round',
                            'line-cap': 'round'
                        },
                        'paint': {
                            'line-color': '#30DB5B',
                            'line-width': 4
                        }
                    });

                    const bounds = coordinates.reduce(function (bounds, coord) {
                        return bounds.extend(coord);
                    }, new mapboxgl.LngLatBounds(coordinates[0], coordinates[0]));

                    map.fitBounds(bounds, {
                        padding: 20
                    });
                });
            })
            .catch(error => {
                console.error('Error loading GPX file:', error);
                alert('Error loading route: ' + error.message);
            });
    }

    window.initializeMap = initializeMap;
});
