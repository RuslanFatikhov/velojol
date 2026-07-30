document.addEventListener('DOMContentLoaded', () => {
    const data = window.infrastructureEditorData || {};
    const latitudeInput = document.getElementById('infrastructure-latitude');
    const longitudeInput = document.getElementById('infrastructure-longitude');
    const coordinatesLabel = document.getElementById('infrastructure-coordinates');
    const mapError = document.getElementById('infrastructure-map-error');
    const photoInput = document.getElementById('infrastructure-photos');
    const photoPreview = document.getElementById('infrastructure-photo-preview');
    const citySelect = document.getElementById('infrastructure-city');

    function updateAddObjectTabCities(selectedCity) {
        document.querySelectorAll('[data-add-object-type]').forEach((tab) => {
            const type = tab.dataset.addObjectType;
            const url = new URL('/add-bikelane', window.location.origin);
            if (type && type !== 'bikelane') {
                url.searchParams.set('type', type);
            }
            if (selectedCity) {
                url.searchParams.set('city', selectedCity);
            }
            tab.href = `${url.pathname}${url.search}`;
        });
    }

    function updateCoordinates(lngLat) {
        const longitude = Number(lngLat.lng);
        const latitude = Number(lngLat.lat);
        longitudeInput.value = longitude.toFixed(7);
        latitudeInput.value = latitude.toFixed(7);
        coordinatesLabel.textContent = `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
    }

    const initialCoordinates = Array.isArray(data.coordinates)
        ? data.coordinates.map(Number)
        : [];

    if (initialCoordinates.length === 2) {
        updateCoordinates({
            lng: initialCoordinates[0],
            lat: initialCoordinates[1]
        });
    }

    if (
        typeof L === 'undefined'
        || initialCoordinates.length !== 2
    ) {
        mapError.hidden = false;
    } else {
        const initialLatLng = [initialCoordinates[1], initialCoordinates[0]];
        const map = L.map('infrastructure-edit-map').setView(initialLatLng, 17);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap'
        }).addTo(map);

        const markerIcon = L.divIcon({
            className: 'infrastructure-editor__marker-host',
            html: `
                <div class="infrastructure-editor__marker">
                    <img src="${data.iconUrl}" alt="">
                </div>
            `,
            iconSize: [44, 44],
            iconAnchor: [22, 44]
        });
        const marker = L.marker(initialLatLng, {
            icon: markerIcon,
            draggable: true
        }).addTo(map);

        marker.on('dragend', () => {
            const latLng = marker.getLatLng();
            updateCoordinates({lng: latLng.lng, lat: latLng.lat});
        });
        map.on('click', (event) => {
            marker.setLatLng(event.latlng);
            updateCoordinates({
                lng: event.latlng.lng,
                lat: event.latlng.lat
            });
        });

        citySelect?.addEventListener('change', () => {
            updateAddObjectTabCities(citySelect.value);
            const option = citySelect.selectedOptions[0];
            const latitude = Number(option?.dataset.lat);
            const longitude = Number(option?.dataset.lng);
            if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
                return;
            }

            const latLng = L.latLng(latitude, longitude);
            marker.setLatLng(latLng);
            map.setView(latLng, 15);
            updateCoordinates({lng: longitude, lat: latitude});
        });
    }

    photoInput?.addEventListener('change', () => {
        photoPreview.innerHTML = '';
        Array.from(photoInput.files || []).slice(0, 10).forEach((file) => {
            if (!file.type.startsWith('image/')) {
                return;
            }
            const image = document.createElement('img');
            image.src = URL.createObjectURL(file);
            image.alt = `Новое фото ${file.name}`;
            image.addEventListener('load', () => URL.revokeObjectURL(image.src), {
                once: true
            });
            photoPreview.appendChild(image);
        });
    });
});
