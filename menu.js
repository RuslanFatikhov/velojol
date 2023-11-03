document.querySelector('.MenuButton').addEventListener('click', function() {
    document.querySelector('.menu').classList.add('show');
});

document.querySelector('.close-menu').addEventListener('click', function() {
    document.querySelector('.menu').classList.remove('show');
});

document.querySelector('.menu').addEventListener('click', function(event) {
    if (event.target.classList.contains('menu')) {
        document.querySelector('.menu').classList.remove('show');
    }
});
