// Use the deployed API only for the published website. Local development is
// served by FastAPI, so an empty base URL keeps API requests on the same origin.
const DEPLOYED_FRONTEND_HOSTS = new Set([
  "jamesonthehill.com",
  "www.jamesonthehill.com",
  "jamesonthehill.github.io",
]);

const deployed = DEPLOYED_FRONTEND_HOSTS.has(window.location.hostname);
const hostedRoot = `${window.location.origin}/Socratic-Chat/`;

window.SOCRATIC_CONFIG = {
  API_BASE_URL: deployed ? "https://socratic-chat-api.onrender.com" : "",
  SOCRATIC_URL: deployed ? hostedRoot : "/",
  PLATFORM_URL: deployed ? `${hostedRoot}platform/` : "/platform/",
};
