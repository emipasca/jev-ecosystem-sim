"use strict";

// Api: the single channel between the UI and the backend. This is the only
// file that knows URLs/HTTP; everything else calls Api.* and gets plain data.
// All URLs are RELATIVE (no leading slash): the app is served behind a
// reverse-proxy path prefix, and relative paths keep working under any prefix.
const Api = (() => {
  async function getJSON(url) {
    return (await fetch(url)).json();
  }
  return {
    world: () => getJSON("api/world"),
    state: () => getJSON("api/state"),
    entity: (id) => getJSON(`api/entity?id=${encodeURIComponent(id)}`),
    control: (cmd, value) => {
      const q = value !== undefined ? `&value=${encodeURIComponent(value)}` : "";
      return getJSON(`api/control?cmd=${encodeURIComponent(cmd)}${q}`);
    },
  };
})();
