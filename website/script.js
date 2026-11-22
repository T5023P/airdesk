/* AIRDESK site: nav, scroll reveal and the interactive Air Command wheel demo. */
(() => {
  "use strict";

  /* ── the twelve allow-listed sectors, same order as the desktop wheel ── */
  const COMMANDS = [
    "Open browser", "Calculator", "File manager", "Screenshot",
    "Virtual keyboard", "Air Mouse", "Air Keyboard", "Presentation",
    "Volume +", "Volume -", "Play / pause", "Pause tracking"
  ];

  const sectors = document.getElementById("sectors");
  const wheel = document.getElementById("wheelDemo");
  const hubLabel = document.getElementById("hubLabel");

  if (sectors && wheel) {
    COMMANDS.forEach((label, i) => {
      const node = document.createElement("span");
      node.className = "sector";
      node.textContent = label;
      // Sector 0 sits at twelve o'clock, clockwise — the desktop rule.
      node.style.setProperty("--rot", `${i * 30}deg`);
      node.addEventListener("mouseenter", () => {
        wheel.style.setProperty("--a", `${i * 30}deg`);
        [...sectors.children].forEach((child) => child.classList.remove("active"));
        node.classList.add("active");
        if (hubLabel) hubLabel.textContent = label;
      });
      sectors.appendChild(node);
    });

    wheel.addEventListener("mouseleave", () => {
      wheel.style.setProperty("--a", "0deg");
      [...sectors.children].forEach((child) => child.classList.remove("active"));
      if (hubLabel) hubLabel.textContent = "Hover a sector";
    });

    // keyboard parity: tab through sectors and reuse the hover behaviour
    [...sectors.children].forEach((node) => {
      node.setAttribute("tabindex", "0");
      node.addEventListener("focus", () => node.dispatchEvent(new Event("mouseenter")));
    });
  }

  /* ── mobile navigation ── */
  const toggle = document.getElementById("navToggle");
  const nav = document.getElementById("nav");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    nav.addEventListener("click", (event) => {
      if (event.target.tagName === "A") {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
  }

  /* ── reveal on scroll ── */
  const revealables = document.querySelectorAll(
    ".section-head, .card, .compare-col, .pipeline li, .steps li, .commands, .table-wrap"
  );
  revealables.forEach((el) => el.classList.add("reveal"));

  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );
    revealables.forEach((el) => io.observe(el));
  } else {
    revealables.forEach((el) => el.classList.add("in"));
  }

  /* ── active nav link ── */
  const links = [...document.querySelectorAll(".nav a[href^='#']")];
  const sections = links
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if ("IntersectionObserver" in window && sections.length) {
    const spy = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          links.forEach((link) =>
            link.classList.toggle("active", link.getAttribute("href") === `#${entry.target.id}`)
          );
        });
      },
      { rootMargin: "-45% 0px -50% 0px" }
    );
    sections.forEach((section) => spy.observe(section));
  }
})();
