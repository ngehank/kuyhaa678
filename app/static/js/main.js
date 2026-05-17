// main.js — NF Manager global JS

// Auto-dismiss alerts
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity 0.5s';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 500);
  }, 4000);
});

// Active nav link highlight
const path = window.location.pathname;
document.querySelectorAll('.nav-link').forEach(link => {
  if (link.getAttribute('href') === path) link.classList.add('active');
});

// Mobile menu toggle
const mobileBtn = document.getElementById('mobile-menu-btn');
const sidebar = document.querySelector('.sidebar');
if (mobileBtn && sidebar) {
  mobileBtn.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    mobileBtn.textContent = sidebar.classList.contains('open') ? '✕' : '☰';
  });
}
