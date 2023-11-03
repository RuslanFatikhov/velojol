const photos = document.querySelectorAll('.photos img');
const photoview = document.querySelector('.photoview');
const photoContainer = document.querySelector('.photoview-container');
const photoCount = document.querySelector('.photoview-count');

let currentPhotoIndex = 0;

function showPhoto(index) {
    currentPhotoIndex = index;
    const currentPhoto = photos[currentPhotoIndex];
    photoContainer.style.backgroundImage = `url(${currentPhoto.src})`;
    updatePhotoCount();
}

function updatePhotoCount() {
    const totalPhotos = photos.length;
    const currentPhotoNumber = currentPhotoIndex + 1;
    photoCount.textContent = `${currentPhotoNumber}/${totalPhotos}`;
}

document.querySelector('.photoview-prev').addEventListener('click', () => {
    currentPhotoIndex = (currentPhotoIndex - 1 + photos.length) % photos.length;
    showPhoto(currentPhotoIndex);
});

document.querySelector('.photoview-next').addEventListener('click', () => {
    currentPhotoIndex = (currentPhotoIndex + 1) % photos.length;
    showPhoto(currentPhotoIndex);
});

document.querySelector('.photoview-close').addEventListener('click', () => {
    photoview.style.display = 'none';
});

document.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowLeft') {
        currentPhotoIndex = (currentPhotoIndex - 1 + photos.length) % photos.length;
        showPhoto(currentPhotoIndex);
    } else if (event.key === 'ArrowRight') {
        currentPhotoIndex = (currentPhotoIndex + 1) % photos.length;
        showPhoto(currentPhotoIndex);
    } else if (event.key === 'Escape') {
        photoview.style.display = 'none';
    }
});
