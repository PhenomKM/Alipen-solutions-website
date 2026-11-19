/**
 * Alipen Solutions Agency Ltd - Global Application Core Script
 * Brand: Alipen Solutions Agency Ltd ("--Empowering Health Solutions--")
 * Lead Contact: Peter Ogettoh | +254 712 272 463 | info@alipen.co.ke | Nairobi, Kenya
 */

const ALIPEN_CONTACT = {
  person: 'Peter Ogettoh',
  phone: '+254 712 272 463',
  phoneRaw: '254712272463',
  email: 'info@alipen.co.ke',
  location: 'Nairobi, Kenya',
  company: 'Alipen Solutions Agency Ltd',
  tagline: '--Empowering Health Solutions--'
};

const BASKET_STORAGE_KEY = 'alipen_quote_basket_v1';

// Quote Basket Manager
const QuoteBasket = {
  get() {
    try {
      const data = localStorage.getItem(BASKET_STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      console.error('Error loading quote basket:', e);
      return [];
    }
  },

  save(items) {
    try {
      localStorage.setItem(BASKET_STORAGE_KEY, JSON.stringify(items));
      this.updateBadges();
      window.dispatchEvent(new CustomEvent('quoteBasketUpdated', { detail: items }));
    } catch (e) {
      console.error('Error saving quote basket:', e);
    }
  },

  add(slug, quantity = 1) {
    const product = typeof getProductBySlug === 'function' ? getProductBySlug(slug) : null;
    if (!product) return false;

    const basket = this.get();
    const existingIndex = basket.findIndex(item => item.slug === slug);

    if (existingIndex > -1) {
      basket[existingIndex].quantity += quantity;
    } else {
      basket.push({
        slug: product.slug,
        name: product.name,
        shortName: product.shortName || product.name,
        category: product.categoryLabel,
        image: product.image,
        quantity: quantity
      });
    }

    this.save(basket);
    showToast(`Added ${product.shortName || product.name} to Quote Basket`);
    return true;
  },

  remove(slug) {
    let basket = this.get();
    basket = basket.filter(item => item.slug !== slug);
    this.save(basket);
  },

  updateQuantity(slug, newQty) {
    let basket = this.get();
    const item = basket.find(i => i.slug === slug);
    if (item) {
      if (newQty <= 0) {
        this.remove(slug);
      } else {
        item.quantity = newQty;
        this.save(basket);
      }
    }
  },

  clear() {
    this.save([]);
  },

  getCount() {
    const basket = this.get();
    return basket.reduce((total, item) => total + (item.quantity || 1), 0);
  },

  updateBadges() {
    const count = this.getCount();
    document.querySelectorAll('.quote-badge-count').forEach(el => {
      el.textContent = count;
      if (count > 0) {
        el.classList.remove('hidden');
        el.style.display = 'inline-flex';
      } else {
        el.classList.add('hidden');
        el.style.display = 'none';
      }
    });
    document.querySelectorAll('.mobile-quote-shortcut').forEach(el => {
      el.setAttribute('aria-label', count
        ? `Request a quote, ${count} item${count === 1 ? '' : 's'} in basket`
        : 'Request a quote, basket is empty');
    });
  }
};

// Toast notification helper
function showToast(message, type = 'success') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <div class="toast-content">
      <span class="toast-icon">✓</span>
      <span class="toast-text">${message}</span>
    </div>
    <button class="toast-close" aria-label="Close notification">&times;</button>
  `;

  container.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  const removeToast = () => {
    toast.classList.remove('show');
    setTimeout(() => {
      if (toast.parentElement) {
        toast.parentElement.removeChild(toast);
      }
    }, 300);
  };

  toast.querySelector('.toast-close').addEventListener('click', removeToast);
  setTimeout(removeToast, 3500);
}

// Generate structured WhatsApp enquiry message
function buildWhatsAppQuoteUrl(options = {}) {
  const { name, facility, phone, email, notes, items = QuoteBasket.get() } = options;

  let message = `Hello Peter Ogettoh (Alipen Solutions Agency Ltd),\n\n`;
  message += `I would like to request an official quotation for the following medical equipment / supplies:\n\n`;

  if (items && items.length > 0) {
    items.forEach((item, index) => {
      message += `${index + 1}. ${item.name || item.shortName} (Qty: ${item.quantity || 1})\n`;
    });
  } else {
    message += `[General Medical Equipment & Consumables Inquiry]\n`;
  }

  message += `\n--- Client / Facility Details ---\n`;
  if (name) message += `• Contact Person: ${name}\n`;
  if (facility) message += `• Facility / Organisation: ${facility}\n`;
  if (phone) message += `• Phone: ${phone}\n`;
  if (email) message += `• Email: ${email}\n`;
  if (notes) message += `• Requirements / Notes: ${notes}\n`;

  message += `\nPlease provide availability, delivery timeline to our location, and proforma invoice. Thank you!`;

  return `https://wa.me/${ALIPEN_CONTACT.phoneRaw}?text=${encodeURIComponent(message)}`;
}

// Global DOM initialization
document.addEventListener('DOMContentLoaded', () => {
  // Update quote badges
  QuoteBasket.updateBadges();

  // Mobile navigation drawer toggle
  const mobileToggle = document.querySelector('.mobile-nav-toggle');
  const mobileDrawer = document.querySelector('.mobile-drawer');
  const drawerOverlay = document.querySelector('.drawer-backdrop');
  const drawerClose = document.querySelector('.drawer-close');

  function openDrawer() {
    document.body.classList.add('mobile-drawer-open');
    if (mobileDrawer) {
      mobileDrawer.classList.add('active');
      mobileDrawer.setAttribute('aria-hidden', 'false');
    }
    if (drawerOverlay) drawerOverlay.classList.add('active');
    if (mobileToggle) mobileToggle.setAttribute('aria-expanded', 'true');
    document.body.style.overflow = 'hidden';
  }

  function closeDrawer() {
    document.body.classList.remove('mobile-drawer-open');
    if (mobileDrawer) {
      mobileDrawer.classList.remove('active');
      mobileDrawer.setAttribute('aria-hidden', 'true');
    }
    if (drawerOverlay) drawerOverlay.classList.remove('active');
    if (mobileToggle) mobileToggle.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  if (mobileToggle) {
    mobileToggle.setAttribute('aria-controls', 'mobile-navigation');
    mobileToggle.setAttribute('aria-expanded', 'false');
  }
  if (mobileDrawer) {
    mobileDrawer.id = 'mobile-navigation';
    mobileDrawer.setAttribute('aria-hidden', 'true');
  }

  if (mobileToggle) mobileToggle.addEventListener('click', openDrawer);
  if (drawerClose) drawerClose.addEventListener('click', closeDrawer);
  if (drawerOverlay) drawerOverlay.addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') closeDrawer();
  });

  // Active navigation link highlighting
  const currentPath = window.location.pathname.toLowerCase();
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href');
    if (!href) return;
    const cleanHref = href.toLowerCase().replace(/^\.\//, '').replace(/\.html$/, '');
    const cleanCurrent = currentPath.replace(/^\//, '').replace(/\.html$/, '') || 'index';

    if (
      (cleanCurrent === 'index' && (cleanHref === 'index' || cleanHref === '/' || cleanHref === '')) ||
      (cleanCurrent !== 'index' && cleanHref.includes(cleanCurrent))
    ) {
      link.classList.add('active');
    }
  });

  // Sticky Header on Scroll
  const header = document.querySelector('.site-header');
  if (header) {
    let scrollTicking = false;
    window.addEventListener('scroll', () => {
      if (scrollTicking) return;
      scrollTicking = true;
      window.requestAnimationFrame(() => {
        header.classList.toggle('scrolled', window.scrollY > 40);
        scrollTicking = false;
      });
    }, { passive: true });
  }

  // Setup click listeners for add-to-quote buttons with data-slug attribute
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-add-to-quote]');
    if (btn) {
      const slug = btn.getAttribute('data-add-to-quote');
      const qtyInput = document.querySelector(`[data-qty-for="${slug}"]`);
      const qty = qtyInput ? parseInt(qtyInput.value, 10) || 1 : 1;
      QuoteBasket.add(slug, qty);

      // Button feedback
      const originalText = btn.innerHTML;
      btn.innerHTML = `<span class="btn-icon">✓</span> Added!`;
      btn.classList.add('btn-added');
      setTimeout(() => {
        btn.innerHTML = originalText;
        btn.classList.remove('btn-added');
      }, 1800);
    }
  });

  // Global image fallback and lazy image optimization
  document.querySelectorAll('img').forEach((image) => {
    if (!image.hasAttribute('loading') && image !== document.querySelector('.hero-main-img')) {
      image.setAttribute('loading', 'lazy');
      image.setAttribute('decoding', 'async');
    }
    image.addEventListener('error', () => {
      if (!image.dataset.fallbackApplied) {
        image.dataset.fallbackApplied = 'true';
        image.src = 'public/images/logo.png';
      }
    }, { once: true });
  });

  // Scroll progress and segment entrance transitions
  const isCataloguePage = /(?:^\/products(?:\/|$)|products\.html)/.test(window.location.pathname);
  if (isCataloguePage) {
    document.body.classList.add('catalogue-page');
    document.documentElement.classList.remove('reveal-ready');
  } else {
    document.documentElement.classList.add('reveal-ready');
  }

  if (!isCataloguePage) {
    let progressBar = document.querySelector('.scroll-progress');
    if (!progressBar) {
      progressBar = document.createElement('div');
      progressBar.className = 'scroll-progress';
      progressBar.setAttribute('aria-hidden', 'true');
      document.body.prepend(progressBar);
    }

    let progressTicking = false;
    const updateScrollProgress = () => {
      const root = document.documentElement;
      const scrollable = root.scrollHeight - window.innerHeight;
      const progress = scrollable > 0 ? window.scrollY / scrollable : 0;
      progressBar.style.transform = `scaleX(${Math.min(1, Math.max(0, progress))})`;
      progressTicking = false;
    };
    window.addEventListener('scroll', () => {
      if (!progressTicking) {
        progressTicking = true;
        window.requestAnimationFrame(updateScrollProgress);
      }
    }, { passive: true });
    updateScrollProgress();
  }

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!isCataloguePage && !reduceMotion && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries, revealObserver) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          revealObserver.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.12,
      rootMargin: '0px 0px -8% 0px'
    });

    const staggerGroups = [
      '.product-grid',
      '.pillars-grid',
      '.visual-showcase-grid',
      '.contact-info-list',
      '.footer-grid'
    ];

    const prepareRevealTargets = () => {
      document.querySelectorAll('main section:not(.hero-section), .section:not(.hero-section), footer, .kenya-reach-panel, .complete-clinic-banner, .catalog-controls-bar, .quote-basket-card, .form-card, .contact-sidebar-card').forEach((element) => {
        if (!element.classList.contains('scroll-reveal') && !element.closest('.hero-section')) {
          element.classList.add('scroll-reveal');
          observer.observe(element);
        }
      });

      document.querySelectorAll('.section-header-center, .about-mission-grid, .visual-showcase-grid > *, .kenya-reach-content > *, .complete-clinic-banner > *, .quote-basket-header').forEach((element) => {
        if (!element.classList.contains('scroll-reveal')) {
          element.setAttribute('data-reveal', 'scale');
          element.classList.add('scroll-reveal');
          observer.observe(element);
        }
      });

      staggerGroups.forEach((selector) => {
        document.querySelectorAll(selector).forEach((group) => {
          Array.from(group.children).forEach((element, index) => {
            if (!element.classList.contains('stagger-reveal')) {
              element.style.setProperty('--reveal-index', String(index));
              element.classList.add('stagger-reveal');
              observer.observe(element);
            }
          });
        });
      });
    };

    prepareRevealTargets();

    const revealMutationObserver = new MutationObserver(() => prepareRevealTargets());
    revealMutationObserver.observe(document.body, { childList: true, subtree: true });
  }
});
