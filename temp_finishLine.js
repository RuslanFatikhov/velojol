    /**
     * Завершает рисование линии
     */
    function finishLine() {
        console.log('=== ЗАВЕРШЕНИЕ РИСОВАНИЯ ЛИНИИ ===');
        console.log('Количество точек:', currentPoints.length);
        console.log('Точки:', currentPoints);
        
        if (currentPoints.length < 2) {
            updateGeometryStatus('Линия должна содержать минимум 2 точки', 'invalid');
            console.log('ОШИБКА: Недостаточно точек');
            return;
        }
        
        isDrawing = false;
        
        // Создаем GeoJSON
        const coordinates = currentPoints.map(point => [point.lng, point.lat]);
        const geojson = {
            type: "LineString",
            coordinates: coordinates
        };
        
        console.log('Создан GeoJSON:', geojson);
        
        // Рассчитываем и отображаем дистанцию
        const distance = updateDistanceDisplay(coordinates);
        addDistanceField(distance);
        
        // Сохраняем в скрытое поле
        const geometryInput = document.getElementById('geometry');
        if (!geometryInput) {
            console.error('КРИТИЧЕСКАЯ ОШИБКА: Поле geometry не найдено!');
            return;
        }
        
        const geometryString = JSON.stringify(geojson);
        geometryInput.value = geometryString;
        
        console.log('ГЕОМЕТРИЯ СОХРАНЕНА:');
        console.log('- Поле найдено: ДА');
        console.log('- Значение установлено:', geometryString);
        console.log('- Проверяем значение поля сейчас:', geometryInput.value);
        console.log('- Длина:', geometryInput.value.length);
        console.log('- Дистанция:', distance.toFixed(2), 'м');
        
        // Делаем линию редактируемой
        if (currentPolyline && currentPolyline.editing) {
            currentPolyline.editing.enable();
            console.log('Редактирование линии включено');
            
            // Добавляем обработчик изменения линии
            currentPolyline.on('edit', function() {
                console.log('Линия отредактирована, обновляем геометрию и дистанцию');
                updateGeometryFromMapWithDistance();
            });
        }
        
        // Принудительно обновляем геометрию из карты
        setTimeout(() => {
            console.log('Принудительное обновление геометрии через 100мс');
            updateGeometryFromMapWithDistance();
        }, 100);
        
        // Обновляем статус
        validateGeometry();
        
        updateGeometryStatus(`Линия нарисована! Дистанция: ${formatDistance(distance)}. Можете перетаскивать точки для корректировки.`, 'valid');
        
        console.log('=== ЗАВЕРШЕНИЕ ОБРАБОТКИ ЛИНИИ ===');
    }
