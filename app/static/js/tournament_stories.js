(function() {
    const STORY_IMAGE_EXT = 'jpg';
    const STORY_BASE_PATH = '/static/img/stories/';
    const STORY_LABELS = {
        how: 'Как это работает',
        why: 'Зачем это нужно',
        coins: 'Как получить монетки'
    };

    const buildStoryPaths = function(prefix) {
        return [1, 2, 3, 4].map(function(number) {
            return STORY_BASE_PATH + prefix + '-' + number + '.' + STORY_IMAGE_EXT;
        });
    };

    const TOURNAMENT_STORIES = {
        how: buildStoryPaths('s1'),
        why: buildStoryPaths('s2'),
        coins: buildStoryPaths('s3')
    };

    window.TOURNAMENT_STORIES = TOURNAMENT_STORIES;

    document.addEventListener('DOMContentLoaded', function() {
        const viewer = document.getElementById('tournamentStoriesViewer');
        const image = document.getElementById('tournamentStoryImage');
        const progress = document.getElementById('tournamentStoriesProgress');
        const closeButton = document.getElementById('closeTournamentStories');
        const storyButtons = document.querySelectorAll('[data-tournament-story]');
        const navButtons = document.querySelectorAll('[data-story-nav]');
        let currentGroup = '';
        let currentIndex = 0;

        if (!viewer || !image || !progress || !closeButton || !storyButtons.length) {
            return;
        }

        function renderProgress(slides) {
            progress.innerHTML = '';

            slides.forEach(function(_, index) {
                const segment = document.createElement('span');
                segment.className = 'tournament-stories-progress-segment';
                if (index === currentIndex) {
                    segment.classList.add('is-active');
                }
                progress.appendChild(segment);
            });
        }

        function preloadNext(slides) {
            const nextSlide = slides[currentIndex + 1];
            if (!nextSlide) {
                return;
            }

            const preloadImage = new Image();
            preloadImage.src = nextSlide;
        }

        function renderSlide() {
            const slides = TOURNAMENT_STORIES[currentGroup] || [];
            const slide = slides[currentIndex];
            if (!slide) {
                return;
            }

            image.src = slide;
            image.alt = STORY_LABELS[currentGroup] + ', слайд ' + (currentIndex + 1);
            renderProgress(slides);
            preloadNext(slides);
        }

        function openStories(group) {
            if (!TOURNAMENT_STORIES[group]) {
                return;
            }

            currentGroup = group;
            currentIndex = 0;
            renderSlide();
            viewer.classList.add('is-open');
            viewer.setAttribute('aria-hidden', 'false');
            document.body.classList.add('tournament-stories-lock');
            closeButton.focus();
        }

        function closeStories() {
            viewer.classList.remove('is-open');
            viewer.setAttribute('aria-hidden', 'true');
            document.body.classList.remove('tournament-stories-lock');
            image.removeAttribute('src');
            image.alt = '';
        }

        function goToPreviousSlide() {
            if (currentIndex === 0) {
                return;
            }

            currentIndex -= 1;
            renderSlide();
        }

        function goToNextSlide() {
            const slides = TOURNAMENT_STORIES[currentGroup] || [];
            if (currentIndex >= slides.length - 1) {
                return;
            }

            currentIndex += 1;
            renderSlide();
        }

        storyButtons.forEach(function(button) {
            button.addEventListener('click', function() {
                openStories(button.dataset.tournamentStory);
            });
        });

        navButtons.forEach(function(button) {
            button.addEventListener('click', function(event) {
                event.stopPropagation();

                if (button.dataset.storyNav === 'prev') {
                    goToPreviousSlide();
                    return;
                }

                goToNextSlide();
            });
        });

        closeButton.addEventListener('click', function(event) {
            event.stopPropagation();
            closeStories();
        });

        document.addEventListener('keydown', function(event) {
            if (!viewer.classList.contains('is-open')) {
                return;
            }

            if (event.key === 'Escape') {
                closeStories();
            }
        });
    });
})();
