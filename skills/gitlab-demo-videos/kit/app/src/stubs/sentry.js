// No Sentry in the demo: swallow reports.
export const captureException = () => {};
export const captureMessage = () => {};
export const addBreadcrumb = () => {};
export const setTag = () => {};
export const setContext = () => {};
export default { captureException, captureMessage, addBreadcrumb, setTag, setContext };
