importScripts(
  "https://cdn.jsdelivr.net/npm/synclink@0.1.1/dist/esm/synclink.js"
);

async function fetch(url) {
  const resp = await fetch(url);
  return await resp.text();
}

Synclink.expose({
  fetch,
});
