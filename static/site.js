// Videos: se reproducen solos solo mientras están en pantalla y si la persona
// no pidió movimiento reducido. Sin este script los videos siguen funcionando
// con sus controles; nada del contenido depende de JavaScript.
(function () {
  "use strict";
  var videos = document.querySelectorAll("video[data-autoplay]");
  if (!videos.length || !("IntersectionObserver" in window)) return;

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var visible = new Set();
  var state = new Map();

  function play(video) {
    var s = state.get(video);
    if (reduce.matches || s.userPaused || !video.paused) return;
    var p = video.play();
    if (p && p.catch) p.catch(function () {});
  }

  function pause(video) {
    if (video.paused) return;
    state.get(video).ownPause = true;
    video.pause();
  }

  videos.forEach(function (video) {
    var s = { userPaused: false, ownPause: false };
    state.set(video, s);
    // Si la persona pausa con los controles, no se vuelve a reproducir solo.
    video.addEventListener("pause", function () {
      if (s.ownPause) s.ownPause = false;
      else if (visible.has(video)) s.userPaused = true;
    });
    video.addEventListener("play", function () {
      s.userPaused = false;
    });
  });

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          visible.add(entry.target);
          play(entry.target);
        } else {
          visible.delete(entry.target);
          pause(entry.target);
        }
      });
    },
    { threshold: 0.4 }
  );
  videos.forEach(function (video) {
    observer.observe(video);
  });

  function onMotionChange() {
    videos.forEach(function (video) {
      if (reduce.matches) pause(video);
      else if (visible.has(video)) play(video);
    });
  }
  if (reduce.addEventListener) reduce.addEventListener("change", onMotionChange);
  else if (reduce.addListener) reduce.addListener(onMotionChange);
})();
