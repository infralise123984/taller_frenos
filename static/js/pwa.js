if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function (error) {
      console.error("No se pudo registrar la aplicación PWA.", error);
    });
  });
}
