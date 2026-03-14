// Theme controller for DaisyUI — enables theme switching with localStorage persistence.
document.addEventListener('DOMContentLoaded', function() {
  var themeController = {
    init: function() {
      this.setTheme(localStorage.getItem('theme') || 'fireman');
      document.querySelectorAll('[data-set-theme]').forEach(function(btn) {
        btn.addEventListener('click', function() {
          themeController.setTheme(btn.getAttribute('data-set-theme'));
        });
      });
    },
    setTheme: function(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('theme', theme);
    }
  };
  themeController.init();
});
