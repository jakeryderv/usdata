// Turn a [data-tabs] block into tabs and give each code block a copy button.
// Without script every panel shows, labelled, one after another.
for (const block of document.querySelectorAll("[data-tabs]")) {
  const tabs = [...block.querySelectorAll('[role="tab"]')];
  const panels = tabs.map(tab => document.getElementById(tab.getAttribute("aria-controls")));
  const select = index => tabs.forEach((tab, i) => {
    tab.setAttribute("aria-selected", String(i === index));
    tab.tabIndex = i === index ? 0 : -1;
    panels[i].hidden = i !== index;
  });
  block.classList.add("enhanced");
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => select(index));
    tab.addEventListener("keydown", event => {
      const step = {ArrowRight: 1, ArrowLeft: -1}[event.key];
      if (!step) return;
      const next = (index + step + tabs.length) % tabs.length;
      select(next);
      tabs[next].focus();
    });
  });
  select(0);
}

for (const pre of document.querySelectorAll("pre.code")) {
  if (!navigator.clipboard) break;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy";
  button.textContent = "Copy";
  button.addEventListener("click", async () => {
    await navigator.clipboard.writeText(pre.querySelector("code").innerText);
    button.textContent = "Copied";
    setTimeout(() => { button.textContent = "Copy"; }, 1500);
  });
  pre.append(button);
}
