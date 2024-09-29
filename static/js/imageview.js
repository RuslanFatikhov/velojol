// Предполагаем, что images - глобальная переменная, содержащая URL всех изображений
let currentImageIndex = 0; // Индекс текущего показываемого изображения

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация просмотра изображений
    initImageView();

    // Навешиваем обработчики на кнопки навигации
    document.querySelector('.prev').addEventListener('click', function() {
        updateImage(-1);
    });

    document.querySelector('.next').addEventListener('click', function() {
        updateImage(1);
    });

    // Закрытие модального окна по клику на кнопку закрытия
    const closeModalButton = document.querySelector('.modal .close');
    closeModalButton.addEventListener('click', function() {
        const modal = document.getElementById('imageModal');
        modal.classList.remove('visible');
    });

    // Закрытие модального окна по клику вне изображения
    const modal = document.getElementById('imageModal');
    window.addEventListener('click', function(event) {
        if (event.target === modal) {
            modal.classList.remove('visible');
        }
    });
});

function initImageView() {
    document.querySelectorAll('img[data-imageview]').forEach((img, index) => {
        img.addEventListener('click', function() {
            openModal(this.src);
            currentImageIndex = index; // Обновляем текущий индекс
        });
    });
}

function openModal(imageSrc) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.querySelector('.modal-image');
    const counter = document.querySelector('.image-counter');

    modal.style.display = "flex";
    modal.classList.add('visible');
    modalImg.src = imageSrc;
    counter.textContent = `${currentImageIndex + 1} / ${images.length}`;
}

function updateImage(step) {
    currentImageIndex += step;
    if (currentImageIndex >= images.length) {
        currentImageIndex = 0;
    } else if (currentImageIndex < 0) {
        currentImageIndex = images.length - 1;
    }
    const modalImg = document.querySelector('.modal-image');
    const counter = document.querySelector('.image-counter');
    modalImg.src = images[currentImageIndex];
    counter.textContent = `${currentImageIndex + 1} / ${images.length}`; // Обновление счётчика
}

