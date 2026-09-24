// The one page shell every generated website page uses: head, header, and footer.
// public/index.html, public/404.html, and public/datasets/index.html repeat the
// same head links and navigation by hand; test/layout.test.mjs keeps them equal.

export const escape = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"})[char]);

export const NAV = [
  ["Datasets", "/datasets/"],
  ["Studies", "/studies/"],
  ["Docs", "https://docs.usdata.dev/"],
  ["GitHub", "https://github.com/jakeryderv/usdata"],
];

export const FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono&display=swap";

export function nav(current) {
  const links = NAV.map(([label, href]) => `<a href="${href}"${href === current ? ' aria-current="page"' : ""}>${label}</a>`).join("");
  return `<header class="header wrap"><a class="brand" href="/" aria-label="usdata home"><img src="/logo.svg" alt="" width="30" height="30"> usdata</a>
<nav aria-label="Main navigation">${links}</nav></header>`;
}

export function page({title, description, canonical, content, current, styles = [], scripts = [], type = "article", mainClass = ""}) {
  const head = [
    `<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">`,
    `<meta name="description" content="${escape(description)}"><meta name="color-scheme" content="dark light">`,
    `<meta property="og:type" content="${type}"><meta property="og:site_name" content="usdata"><meta property="og:title" content="${escape(title)}"><meta property="og:description" content="${escape(description)}"><meta property="og:url" content="https://usdata.dev${canonical}"><meta property="og:image" content="https://usdata.dev/og.png"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta name="twitter:card" content="summary_large_image">`,
    `<title>${escape(title)} · usdata</title><link rel="canonical" href="https://usdata.dev${canonical}">`,
    `<link rel="icon" href="/logo.svg" type="image/svg+xml"><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="${FONTS}">`,
    `<link rel="stylesheet" href="/tokens.css"><link rel="stylesheet" href="/style.css">${styles.map(href => `<link rel="stylesheet" href="${href}">`).join("")}`,
    ...scripts.map(src => `<script type="module" src="${src}"></script>`),
  ].join("\n");
  return `<!doctype html>
<html lang="en"><head>
${head}
</head><body><a class="skip" href="#main">Skip to content</a>
${nav(current)}
<main class="wrap${mainClass ? ` ${mainClass}` : ""}" id="main">${content}</main>
<footer class="wrap"><span>usdata · Public scientific data, with provenance.</span><a href="https://docs.usdata.dev/">Read the documentation</a></footer>
</body></html>\n`;
}
