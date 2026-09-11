# Homepage

This directory owns `usdata.dev`: `public/` is the content and styling,
`src/` is the routing Worker, and `test/` verifies its behavior.

```sh
npm ci
npm run build
npm run check
npm run dev
```

`npm run deploy` publishes the homepage. Build output in `dist/` is disposable.
The homepage needs neither the Python environment nor documentation tooling.
Documentation has its own commands in `../docs/`.
