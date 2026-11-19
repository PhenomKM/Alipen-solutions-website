const navToggle = document.querySelector('.nav-toggle');
const mainNav = document.querySelector('.main-nav');

if (navToggle && mainNav) {
  navToggle.addEventListener('click', () => {
    const isOpen = mainNav.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  });

  mainNav.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      mainNav.classList.remove('open');
      navToggle.setAttribute('aria-expanded', 'false');
    });
  });
}

const inquiryForm = document.getElementById('inquiryForm');
const formStatus = document.querySelector('.form-status');

if (inquiryForm) {
  inquiryForm.addEventListener('submit', (event) => {
    event.preventDefault();
    const formData = new FormData(inquiryForm);
    const name = (formData.get('name') || '').toString().trim();

    if (!name) {
      formStatus.textContent = 'Please fill in your details to send the inquiry.';
      formStatus.style.color = '#a63a3a';
      return;
    }

    formStatus.textContent = `Thank you, ${name}. Your inquiry has been received. Our team will contact you shortly.`;
    formStatus.style.color = '#1d8c5c';
    inquiryForm.reset();
  });
}
