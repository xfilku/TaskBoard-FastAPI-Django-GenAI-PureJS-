// Shared navigation, dialogs, form state and password visibility.
(() => {
  document.querySelectorAll("[data-today]").forEach((el) => {
    const now = new Date();
    el.dateTime = now.toISOString();
    el.querySelector("span").textContent = new Intl.DateTimeFormat("pl-PL", {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(now);
  });
  const menu = document.querySelector(".menu-toggle"),
    sidebar = document.querySelector(".sidebar"),
    shade = document.querySelector(".nav-shade"),
    mobile = matchMedia("(max-width:760px)");
  function nav(open) {
    document.body.classList.toggle("nav-open", open);
    if (menu) {
      menu.setAttribute("aria-expanded", String(open));
      menu.setAttribute(
        "aria-label",
        open ? "Zamknij nawigację" : "Otwórz nawigację",
      );
    }
    if (shade) shade.hidden = !open;
    if (sidebar) {
      sidebar.inert = mobile.matches && !open;
      document.querySelector(".app-main").inert = mobile.matches && open;
    }
    document.body.style.overflow = mobile.matches && open ? "hidden" : "";
  }
  if (menu) {
    menu.addEventListener("click", () => {
      const open = menu.getAttribute("aria-expanded") !== "true";
      nav(open);
      if (open) sidebar.querySelector("a").focus();
    });
    shade.addEventListener("click", () => {
      nav(false);
      menu.focus();
    });
    mobile.addEventListener("change", () => nav(false));
    nav(false);
  }
  document.addEventListener("keydown", (e) => {
    if (!document.body.classList.contains("nav-open")) return;
    if (e.key === "Escape") {
      nav(false);
      menu.focus();
    }
    if (e.key === "Tab") {
      const links = [...sidebar.querySelectorAll("a,button")],
        first = links[0],
        last = links[links.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });
  const help = document.getElementById("help-dialog");
  document.querySelectorAll("[data-open-help]").forEach((button) =>
    button.addEventListener("click", () => {
      nav(false);
      help.showModal();
    }),
  );
  document
    .querySelectorAll("[data-close-dialog]")
    .forEach((button) =>
      button.addEventListener("click", () => button.closest("dialog").close()),
    );
  document.querySelectorAll("dialog").forEach((dialog) =>
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) {
        const box = dialog.getBoundingClientRect();
        if (
          e.clientX < box.left ||
          e.clientX > box.right ||
          e.clientY < box.top ||
          e.clientY > box.bottom
        )
          dialog.close();
      }
    }),
  );
  const confirmDialog = document.getElementById("confirm-dialog");
  let pendingForm = null,
    pendingButton = null;
  document.addEventListener("submit", (e) => {
    const form = e.target;
    if (form.dataset.confirm && form.dataset.confirmed !== "true") {
      e.preventDefault();
      pendingForm = form;
      pendingButton = e.submitter;
      document.getElementById("confirm-description").textContent =
        form.dataset.confirm;
      confirmDialog.showModal();
      return;
    }
    form.dataset.submitting = "true";
    form.setAttribute("aria-busy", "true");
    if (e.submitter) {
      const button = e.submitter;
      setTimeout(() => (button.disabled = true), 0);
    }
  });
  document.getElementById("confirm-submit").addEventListener("click", () => {
    if (pendingForm) {
      pendingForm.dataset.confirmed = "true";
      confirmDialog.close();
      pendingForm.requestSubmit(pendingButton);
    }
  });
  document.querySelectorAll("[data-password-toggle]").forEach((button) =>
    button.addEventListener("click", () => {
      const input = document.getElementById(
          button.getAttribute("aria-controls"),
        ),
        show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-label", show ? "Ukryj hasło" : "Pokaż hasło");
      button.setAttribute("aria-pressed", String(show));
    }),
  );
  document.querySelectorAll("[data-dirty-guard]").forEach((form) => {
    let dirty = false;
    form.addEventListener("input", () => (dirty = true));
    window.addEventListener("beforeunload", (e) => {
      if (dirty && form.dataset.submitting !== "true") {
        e.preventDefault();
        e.returnValue = "";
      }
    });
  });
  const firstError = document.querySelector('[aria-invalid="true"]');
  if (firstError) firstError.focus();
})();

// Board search and view state.
(() => {
  const search = document.getElementById("board-search");
  if (!search) return;
  document.querySelector("[data-home-tools]").hidden = false;
  const grid = document.getElementById("boards-grid"),
    cards = [...document.querySelectorAll("[data-board-name]")],
    empty = document.getElementById("no-boards-found"),
    buttons = [...document.querySelectorAll("[data-view]")];
  function render() {
    const params = new URLSearchParams(location.search),
      q = params.get("q") || "",
      list = params.get("view") === "list";
    search.value = q;
    grid.classList.toggle("list-view", list);
    buttons.forEach((button) =>
      button.setAttribute(
        "aria-pressed",
        String((button.dataset.view === "list") === list),
      ),
    );
    let visible = 0;
    cards.forEach((card) => {
      card.hidden = !card.dataset.boardName
        .toLocaleLowerCase("pl")
        .includes(q.trim().toLocaleLowerCase("pl"));
      if (!card.hidden) visible++;
    });
    empty.hidden = visible !== 0;
  }
  function update(key, value) {
    const url = new URL(location.href);
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
    history.replaceState(null, "", url);
    render();
  }
  search.addEventListener("input", () => update("q", search.value));
  buttons.forEach((button) =>
    button.addEventListener("click", () =>
      update("view", button.dataset.view === "list" ? "list" : ""),
    ),
  );
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      search.focus();
    }
  });
  addEventListener("popstate", render);
  render();
})();

// Task filters and progress.
(() => {
  if (!document.getElementById("task-list")) return;
  document
    .querySelectorAll("[data-focus-task]")
    .forEach((link) =>
      link.addEventListener("click", () =>
        document.getElementById("id_title").focus(),
      ),
    );
  const rows = [...document.querySelectorAll("[data-task-state]")],
    done = rows.filter((row) => row.dataset.taskState === "done").length,
    todo = rows.length - done;
  document
    .querySelectorAll("[data-count-done]")
    .forEach((el) => (el.textContent = done));
  document
    .querySelectorAll("[data-count-todo]")
    .forEach((el) => (el.textContent = todo));
  const progress = document.querySelector("[data-progress]");
  if (progress) {
    const value = rows.length ? Math.round((done / rows.length) * 100) : 0;
    progress.hidden = false;
    progress
      .querySelector(".progress-ring")
      .style.setProperty("--progress", value);
    progress
      .querySelector("[role=progressbar]")
      .setAttribute("aria-valuenow", value);
    progress.querySelector("[data-progress-value]").textContent = value + "%";
  }
  const filters = document.querySelector("[data-task-filters]");
  if (!filters) return;
  filters.hidden = false;
  function render() {
    const selected =
        new URLSearchParams(location.search).get("status") || "all",
      filter = ["all", "todo", "done"].includes(selected) ? selected : "all";
    let visible = 0;
    rows.forEach((row) => {
      row.hidden = filter !== "all" && row.dataset.taskState !== filter;
      if (!row.hidden) visible++;
    });
    document
      .querySelectorAll("[data-filter]")
      .forEach((button) =>
        button.setAttribute(
          "aria-pressed",
          String(button.dataset.filter === filter),
        ),
      );
    const empty = document.getElementById("no-tasks-found");
    empty.hidden = visible !== 0 || rows.length === 0;
    document.getElementById("task-list").hidden =
      visible === 0 && rows.length !== 0;
  }
  document.querySelectorAll("[data-filter]").forEach((button) =>
    button.addEventListener("click", () => {
      const url = new URL(location.href);
      if (button.dataset.filter === "all") url.searchParams.delete("status");
      else url.searchParams.set("status", button.dataset.filter);
      history.replaceState(null, "", url);
      render();
    }),
  );
  addEventListener("popstate", render);
  render();
})();

// Shared live preview for board creation and task editing.
(() => {
  const panel = document.querySelector("[data-preview-input]");
  if (!panel) return;
  const input = document.getElementById(panel.dataset.previewInput);
  const preview = panel.querySelector("[data-name-preview]");
  const count = document.querySelector("[data-char-count]");
  function update() {
    preview.textContent = input.value.trim() || panel.dataset.previewEmpty;
    count.textContent = `${input.value.length} / ${input.maxLength}`;
  }
  input.addEventListener("input", update);
  update();
})();

// AI planning enhances server-rendered forms; generation and saving remain separate POSTs.
(() => {
  const form = document.querySelector("[data-ai-generate]");
  if (!form) return;
  const goal = form.querySelector("#id_goal");
  const minimum = form.querySelector("#id_min_elements");
  const maximum = form.querySelector("#id_max_elements");
  const counter = form.querySelector("[data-ai-char-count]");
  const examples = form.querySelector("[data-ai-examples]");
  const review = document.querySelector("[data-ai-review]");

  function updateGoal() {
    counter.textContent = goal.value.length + " / " + goal.maxLength;
  }
  function updateRange() {
    maximum.setCustomValidity(
      Number(minimum.value) > Number(maximum.value)
        ? "Maksimum nie może być mniejsze niż minimum."
        : "",
    );
  }
  function restoreForm() {
    form.dataset.submitting = "false";
    form.removeAttribute("aria-busy");
    form.querySelector("[data-ai-idle]").hidden = false;
    form.querySelector("[data-ai-busy]").hidden = true;
    form.querySelector("[data-ai-loading]").hidden = true;
    form.querySelector('button[type="submit"]').disabled = false;
    [goal, minimum, maximum].forEach((input) => (input.readOnly = false));
  }
  examples.hidden = false;
  examples.querySelectorAll("[data-ai-example]").forEach((button) => {
    button.addEventListener("click", () => {
      goal.value = button.dataset.aiExample;
      goal.dispatchEvent(new Event("input", { bubbles: true }));
      goal.focus();
    });
  });
  goal.addEventListener("input", updateGoal);
  [minimum, maximum].forEach((input) =>
    input.addEventListener("input", updateRange),
  );
  form.addEventListener("submit", () => {
    form.querySelector("[data-ai-idle]").hidden = true;
    form.querySelector("[data-ai-busy]").hidden = false;
    form.querySelector("[data-ai-loading]").hidden = false;
    [goal, minimum, maximum].forEach((input) => (input.readOnly = true));
    examples
      .querySelectorAll("button")
      .forEach((button) => (button.disabled = true));
  });
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) return;
    restoreForm();
    examples
      .querySelectorAll("button")
      .forEach((button) => (button.disabled = false));
    if (review) {
      review.dataset.submitting = "false";
      review.removeAttribute("aria-busy");
      review.querySelector("[data-ai-save]").disabled = false;
    }
  });
  updateGoal();
  updateRange();
  if (!review) return;
  const titles = [...review.querySelectorAll("textarea")];
  function fitTitle(input) {
    input.style.height = "auto";
    input.style.height = input.scrollHeight + "px";
  }
  titles.forEach((input) => {
    fitTitle(input);
    input.addEventListener("input", () => fitTitle(input));
  });
  window.addEventListener("resize", () => titles.forEach(fitTitle));
  function updateSelection() {
    let count = 0;
    review.querySelectorAll("[data-ai-suggestion]").forEach((row) => {
      const skipped = row.querySelector('input[type="checkbox"]').checked;
      row.classList.toggle("is-skipped", skipped);
      if (!skipped) count++;
    });
    review.querySelector("[data-ai-selected-count]").textContent = count;
  }
  review.addEventListener("change", updateSelection);
  updateSelection();
})();
