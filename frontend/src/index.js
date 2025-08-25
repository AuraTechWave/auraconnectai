import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import * as serviceWorker from './utils/serviceWorker';

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

serviceWorker.register({
  onUpdate: (registration) => {
    console.log('New content available; please refresh.');
  },
  onSuccess: (registration) => {
    console.log('Content cached for offline use.');
  },
});